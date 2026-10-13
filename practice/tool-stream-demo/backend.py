"""后端：stdin 接命令，stdout 只发送 JSONL；一个进程独占一个会话。"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from uuid import uuid4

from model import chat, ROOT
from state import empty, reduce, stable

DURABLE = {"task_start", "message_end", "tool_execution_start", "tool_execution_end", "task_end"}


class Session:
    def __init__(self, session_id, directory, fault=None, delay=0.4):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", session_id):
            raise ValueError("sessionId 只能使用字母、数字、下划线和短横线")
        self.session_id, self.fault, self.delay = session_id, fault, delay
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / (session_id + ".jsonl")
        self.seq, self.state = 0, empty()
        self.records = []
        self.warning = None
        if self.path.exists():
            data = self.path.read_bytes()
            # 仅忽略没有换行的尾部碎片；完整行损坏必须报错，不能悄悄跳过历史。
            complete = data[:data.rfind(b"\n") + 1]
            if complete != data:
                self.warning = "忽略未完成尾行；会话只读，不能继续任务"
            for line in complete.splitlines():
                event = json.loads(line)
                if event["sessionId"] != session_id or event["seq"] <= self.seq:
                    raise ValueError("会话 ID 或事件顺序损坏")
                self.seq = event["seq"]
                self.records.append(event)
                reduce(self.state, event)

    def emit(self, kind, **fields):
        self.seq += 1
        event = dict(type=kind, sessionId=self.session_id, seq=self.seq,
                     durable=kind in DURABLE, **fields)
        if kind in DURABLE:
            # 教学选择：先 append + flush + fsync，再发 stdout；两者仍不是原子事务。
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self.records.append(event)
        reduce(self.state, event)
        if self.fault == "after-persist" and kind == "tool_execution_end":
            os._exit(72)  # 已落盘但客户端没收到结束，用来演示两个事实并不等价。
        print(json.dumps(event, ensure_ascii=False), flush=True)

    def tool(self, call):
        function = call["function"]
        name = function["name"]
        try:
            arguments = json.loads(function["arguments"])
        except json.JSONDecodeError:
            arguments = {"invalidJSON": function["arguments"]}
        call_id = call["id"]
        self.emit("tool_execution_start", toolCallId=call_id, name=name, arguments=arguments)
        try:
            # 工具白名单与参数验证属于后端，模型声明本身不提供执行权限。
            if name != "demo_steps" or not isinstance(arguments, dict) or set(arguments) != {"fail"} or type(arguments["fail"]) is not bool:
                raise ValueError("工具名或参数非法：只允许 demo_steps(fail: boolean)")
            for step in range(1, 4):
                time.sleep(self.delay)
                self.emit("tool_execution_update", toolCallId=call_id,
                          output=f"步骤 {step}/3：模拟检查完成")
                if self.fault == "interrupt" and step == 2:
                    os._exit(71)
            if arguments["fail"]:
                raise ValueError("模拟测试失败：用例 3 未通过")
            output, error = "3/3 模拟检查通过", False
        except ValueError as exc:
            output, error = str(exc), True
        self.emit("tool_execution_end", toolCallId=call_id, output=output, isError=error)
        message = {"role": "tool", "tool_call_id": call_id, "content": output}
        self.emit("message_end", message=message)
        return message

    def run(self, mode, fail):
        # 一个 session 只跑一次。恢复仅回放；已有完成/中断历史绝不会再次执行。
        if self.records or self.warning:
            self.emit("rpc_error", error="会话已有历史，请 restore 或使用新的 sessionId")
            return
        self.emit("task_start", mode=mode)
        user = {"role": "user", "content": "调用 demo_steps，fail=" + str(fail).lower() + "，然后用中文一句话总结结果。"}
        self.emit("message_end", message=user)
        try:
            if mode == "live":
                assistant = chat([user], self.emit, first=True)
                if len(assistant.get("tool_calls", [])) != 1:
                    raise ValueError("真实模型未返回预期的单次工具调用")
            else:
                self.emit("message_update", delta="我将执行三步模拟检查。")
                assistant = {"role": "assistant", "content": "我将执行三步模拟检查。",
                    "tool_calls": [{"id": "call_" + uuid4().hex, "type": "function",
                        "function": {"name": "demo_steps", "arguments": json.dumps({"fail": fail})}}]}
            self.emit("message_end", message=assistant)
            tool_message = self.tool(assistant["tool_calls"][0])
            if mode == "live":
                final = chat([user, assistant, tool_message], self.emit)
            else:
                final = {"role": "assistant", "content": "最终结果：" + tool_message["content"]}
                self.emit("message_update", delta=final["content"])
            self.emit("message_end", message=final)
            failed = any(t["isError"] for t in self.state["tools"].values())
            self.emit("task_end", status="failed" if failed else "completed")
        except (RuntimeError, ValueError) as exc:
            self.emit("message_end", message={"role": "system", "content": str(exc)})
            self.emit("task_end", status="failed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--fault", choices=["interrupt", "after-persist"])
    parser.add_argument("--delay", type=float, default=0.4)
    args = parser.parse_args()
    # O_EXCL 防止两个后端同时写同一会话；硬退出遗留锁须在确认进程已停止后手动删除。
    args.data_dir.mkdir(parents=True, exist_ok=True)
    lock = args.data_dir / (args.session + ".lock")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", args.session):
        parser.error("非法 sessionId")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        parser.error("会话已被锁定；确认旧进程停止后删除对应 .lock")
    try:
        os.write(fd, str(os.getpid()).encode())
        session = Session(args.session, args.data_dir, args.fault, args.delay)
        session.emit("session_ready", state=stable(session.state, disconnected=True), warning=session.warning)
        for line in sys.stdin:
            try:
                command = json.loads(line)
                if command["command"] == "start":
                    mode = command.get("mode", "offline")
                    fail = command.get("fail", False)
                    if mode not in ("offline", "live") or type(fail) is not bool:
                        raise ValueError("非法 mode/fail")
                    session.run(mode, fail)
                elif command["command"] == "restore":
                    session.emit("restored", state=stable(session.state, disconnected=True), warning=session.warning)
                elif command["command"] == "quit":
                    break
                else:
                    raise ValueError("未知 command")
            except (ValueError, KeyError) as exc:
                session.emit("rpc_error", error=str(exc))
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
