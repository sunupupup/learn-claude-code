"""本地网页服务：JSON 控制接口 + SSE 事件，复用阶段 1 的核心循环。"""

import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import sys
from time import monotonic
from urllib.parse import urlsplit

from .business import Session, WEB_TOOLS
from .config import DEMO_USER_ID, PROJECT_ROOT, load_settings
from .loop import run_turn
from .model import DeepSeekModel


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, model, settings):
        super().__init__(address, Handler)
        self.model = model
        self.settings = settings
        self.sessions = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 不记录消息正文、模型请求或凭证。
        return

    def json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/health":
            return self.json_response({"status": "ok", "stage": 2, "model": self.server.settings.model})
        match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})", path)
        if match:
            session = self.server.sessions.get(match[1])
            return self.json_response(session.snapshot() if session else {"error": "会话已失效，后端可能已重启，请新建会话。"}, 200 if session else 404)
        if path.startswith("/api/"):
            return self.json_response({"error": "接口不存在。"}, 404)
        # 只暴露构建产物，不能通过 URL 读取项目 .env 或 Python 文件。
        root = (PROJECT_ROOT / "frontend" / "dist").resolve()
        file = (root / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            return self.json_response({"error": "页面未构建或资源不存在，请运行 start.py。"}, 404)
        body = file.read_bytes()
        self.send_response(200)
        mime = {".js": "text/javascript", ".css": "text/css"}.get(file.suffix) or mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") else ""))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        # JSON 与自定义请求头阻止其他站点用普通表单驱动本地业务接口。
        origin = self.headers.get("Origin")
        allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if (origin and origin not in allowed) or self.headers.get("X-Agent-Client") != "web":
            raise ValueError("请求来源不受支持。")
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise ValueError("请求必须是 JSON。")
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 16384:
            raise ValueError("请求内容为空或过长。")
        body = json.loads(self.rfile.read(size))
        if not isinstance(body, dict):
            raise ValueError("请求必须是 JSON 对象。")
        return body

    def do_POST(self):
        try:
            body = self.read_body()
        except (ValueError, UnicodeError):
            return self.json_response({"error": "请求格式或来源无效。"}, 400)
        path = urlsplit(self.path).path
        if path == "/api/sessions":
            if len(self.server.sessions) >= 100:
                return self.json_response({"error": "本地演示会话过多，请重启服务清理。"}, 429)
            today = datetime.now(timezone(timedelta(hours=8))).date()
            session = Session(today)
            self.server.sessions[session.id] = session
            return self.json_response(session.snapshot(), 201)
        match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/(messages|select|decide)", path)
        if not match or match[1] not in self.server.sessions:
            return self.json_response({"error": "会话不存在，请新建会话。"}, 404)
        session = self.server.sessions[match[1]]
        action = match[2]
        if not session.lock.acquire(blocking=False):
            return self.json_response({"error": "上一条请求仍在处理，请稍后重试。"}, 409)
        try:
            if action == "decide":
                if set(body) != {"operation_id", "approved"} or not isinstance(body["operation_id"], str) or type(body["approved"]) is not bool:
                    raise ValueError("确认请求必须包含操作标识和布尔决定，不能提供金额。")
                session.decide(body["operation_id"], body["approved"], lambda event, data: None)
                snapshot = session.snapshot()
                session.lock.release()
                return self.json_response(snapshot)
            if session.pending:
                raise ValueError("请先确认或取消卡片中的操作。")
            if action == "select":
                if set(body) != {"order_id"} or body["order_id"] not in session.candidates:
                    raise ValueError("请选择当前候选订单。")
                text = f"我选择订单 {body['order_id']}，请继续。"
            else:
                if set(body) != {"text"} or not isinstance(body["text"], str) or not 1 <= len(body["text"].strip()) <= 2000:
                    raise ValueError("请输入 1～2000 字的问题。")
                if session.candidates:
                    raise ValueError("请先选择卡片中的订单，或新建会话。")
                text = body["text"].strip()
        except ValueError as exc:
            session.lock.release()
            return self.json_response({"error": str(exc)}, 400)
        # JSON 分支已释放锁；流式分支统一在 finally 释放。
        session.busy = True
        disconnected = False
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def send(event, data):
            nonlocal disconnected
            if disconnected:
                return
            try:
                self.wfile.write(f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                disconnected = True

        tools = {}
        started = {}
        try:
            if action == "select":
                text = session.select(body["order_id"], send)
            session.item("user", send, text=text)
            send("state", {"busy": True, "pending": session.pending, "candidates": session.candidates, "selected": session.selected})

            def log(event, data):
                if event == "model_request":
                    session.active_assistant = session.item("assistant", send, text="", status="streaming")
                elif event == "model_response":
                    session.emit("patch", {"id": session.active_assistant, "status": "complete"}, send)
                elif event == "tool_start":
                    call_id = data["tool_call_id"]
                    tools[call_id] = session.item("tool", send, name=data["tool"], arguments=data["arguments"], status="running")
                    started[call_id] = monotonic()
                elif event == "tool_result":
                    call_id = data["tool_call_id"]
                    result = data["result"]
                    session.emit("patch", {"id": tools[call_id], "status": "failed" if result.get("status") == "error" else "complete",
                                          "result": result, "duration_ms": round((monotonic() - started[call_id]) * 1000)}, send)
                elif event == "model_error" and session.active_assistant:
                    session.emit("patch", {"id": session.active_assistant, "status": "interrupted"}, send)

            result = run_turn(text, context=session.context, model=self.server.model,
                              user_id=DEMO_USER_ID, orders=session.orders,
                              max_model_calls=self.server.settings.max_model_calls,
                              tool_definitions=WEB_TOOLS, executor=lambda call: session.dispatch(call, send),
                              on_delta=lambda text: session.emit("delta", {"id": session.active_assistant, "text": text}, send),
                              log=log)
            if result.status in ("model_error", "budget_exhausted"):
                session.item("notice", send, text=result.text, status="error")
        except Exception:
            # 不把内部堆栈传给浏览器；请求最终状态始终明确收尾。
            if session.active_assistant:
                session.emit("patch", {"id": session.active_assistant, "status": "interrupted"}, send)
            session.item("notice", send, text="本轮处理异常，请重试或联系人工。", status="error")
        finally:
            session.busy = False
            session.active_assistant = None
            send("done", session.snapshot())
            session.lock.release()
            self.close_connection = True


def main():
    parser = argparse.ArgumentParser(description="订单客服网页服务")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    settings = load_settings()
    server = AppServer(("127.0.0.1", args.port), DeepSeekModel(settings), settings)
    print(f"订单客服已启动：http://127.0.0.1:{args.port}（Ctrl+C 停止）", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
