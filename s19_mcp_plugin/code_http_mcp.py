"""不使用 MCP SDK 的最小 Streamable HTTP MCP 实验。

这个文件故意只使用 Python 标准库，目的是把 MCP 的 JSON-RPC 方法暴露出来：

    connect()                 本地 Client 辅助函数，不是 MCP method
    initialize               协议版本、能力和 Server 信息协商
    notifications/initialized 通知 Server：Client 已完成初始化
    tools/list                获取 Tool definitions
    tools/call                调用某个 Tool
    DELETE /mcp               结束 legacy HTTP session

启动服务端：
    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\code_http_mcp.py server

启动原始 HTTP Client：
    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\code_http_mcp.py client

启动最小 Agent Loop（MCP 仍然不用 SDK）：
    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\code_http_mcp.py agent

客户端会打印每一次 HTTP 请求和 JSON-RPC method。交互时输入：
    list
    search MCP
    stats
    q

agent 命令只使用 Anthropic SDK 请求模型；MCP Server、MCP Client、
initialize、tools/list 和 tools/call 仍然全部由本文件手写。

协议版本固定为 2025-11-25，方便观察 initialize + session 的 legacy lifecycle。
这不是生产级 HTTP Server，而是为了学习协议边界的最小实现；SDK 对照版本保存在
同目录的 code_http_mcp_sdk.py。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from anthropic import AsyncAnthropic
from dotenv import load_dotenv


load_dotenv(override=True)


PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "raw-code-http-demo"
SERVER_VERSION = "0.1.0"
MCP_PATH = "/mcp"

# 这份脚本同时包含 Server、Raw Client 和 Agent Loop。学习时可以沿着
# “模型 -> Host -> RawMCPClient -> HTTP -> RawMCPHandler -> Tool”这条线阅读。
CODE_INDEX = [
    {
        "path": "agent_loop.py",
        "summary": "Agent loop reads model output and executes tool calls.",
    },
    {
        "path": "mcp_client.py",
        "summary": "MCP client connects to a server, lists tools, and calls a tool.",
    },
    {
        "path": "context_compiler.py",
        "summary": "Context compiler progressively loads capability metadata.",
    },
]

TOOLS = [
    {
        "name": "search_code",
        "title": "Search code examples",
        "description": "Search the fixed read-only code index.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "code_index_stats",
        "title": "Get code index statistics",
        "description": "Return the number of indexed files.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]

# legacy Streamable HTTP 的 session 是 Server 侧状态；生产环境需要考虑过期、
# 并发、分布式路由和恢复，这里只保留一个进程内字典帮助理解 Mcp-Session-Id。
SESSIONS: dict[str, dict[str, Any]] = {}
SESSIONS_LOCK = threading.Lock()


def json_bytes(value: Any) -> bytes:
    # HTTP body 传输的是 UTF-8 字节；JSON-RPC envelope 仍然只是普通 JSON 对象。
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def jsonrpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    # JSON-RPC 的 result/error 外壳和 Tool 本身的业务结果是两层概念。
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def call_local_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """执行两个本地 Tool；这里模拟 MCP Server 的业务层。"""

    # Handler 只负责协议路由；到了这里，才进入 Tool 的参数校验和业务逻辑。
    if name == "search_code":
        query = arguments.get("query")
        limit = arguments.get("limit", 5)
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not isinstance(limit, int) or not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        needle = query.lower()
        matches = [
            item
            for item in CODE_INDEX
            if needle in item["path"].lower() or needle in item["summary"].lower()
        ][:limit]
        return {"matches": matches}

    if name == "code_index_stats":
        return {"indexed_files": len(CODE_INDEX)}

    raise KeyError(f"unknown tool: {name}")


class RawMCPHandler(BaseHTTPRequestHandler):
    """只实现本实验需要的 POST/DELETE；响应使用单条 SSE message。"""

    server_version = "RawMCP/0.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[server] {self.command} {self.path} - {format % args}", flush=True)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        # MCP 在本实验中使用一个 HTTP endpoint；具体要做什么由 JSON-RPC method 决定。
        if self.path != MCP_PATH:
            self.send_error(404, "MCP endpoint is /mcp")
            return

        try:
            # Content-Length 告诉 HTTP Server 本次 JSON body 有多少字节。
            length = int(self.headers.get("Content-Length", "0"))
            message = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(400, jsonrpc_error(None, -32700, f"invalid JSON: {exc}"))
            return

        method = message.get("method")
        request_id = message.get("id")
        session_id = self.headers.get("Mcp-Session-Id")

        if method == "initialize":
            # initialize 是第一个真正的 MCP method；connect() 只是 Client 本地函数。
            session_id = str(uuid.uuid4())
            with SESSIONS_LOCK:
                SESSIONS[session_id] = {"initialized": False}
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                # capabilities 只声明 Server 能做什么，不等于已经把所有 Tool
                # definition 放进模型上下文；Tool 仍要通过 tools/list 发现。
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
                "instructions": (
                    "Use this read-only server for the demo code index. "
                    "It does not execute arbitrary code."
                ),
            }
            self._send_sse(jsonrpc_result(request_id, result), session_id)
            return

        if not session_id:
            self._send_json(
                400,
                jsonrpc_error(request_id, -32000, "Mcp-Session-Id is required"),
            )
            return

        with SESSIONS_LOCK:
            session = SESSIONS.get(session_id)

        if session is None:
            self._send_json(404, jsonrpc_error(request_id, -32001, "unknown session"))
            return

        if method == "notifications/initialized":
            with SESSIONS_LOCK:
                session["initialized"] = True
            # notification 没有 id，也不需要 JSON-RPC response body。
            self._send_accepted(session_id)
            return

        if not session["initialized"]:
            self._send_json(
                400,
                jsonrpc_error(request_id, -32002, "send notifications/initialized first"),
            )
            return

        # 通过 method 分支把 JSON-RPC 请求分派到 MCP primitive 或业务函数。
        if method == "tools/list":
            self._send_sse(
                jsonrpc_result(request_id, {"tools": TOOLS}),
                session_id,
            )
            return

        if method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            try:
                data = call_local_tool(name, arguments)
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(data, ensure_ascii=False, indent=2),
                        }
                    ],
                    "structuredContent": data,
                    "isError": False,
                }
            except (KeyError, TypeError, ValueError) as exc:
                # Tool 业务错误放在 result.isError，而不是 JSON-RPC protocol error。
                result = {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                }
            self._send_sse(jsonrpc_result(request_id, result), session_id)
            return

        self._send_sse(
            jsonrpc_error(request_id, -32601, f"method not found: {method}"),
            session_id,
        )

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        # 客户端主动结束 legacy session；这不是 Tool 调用，也不进入模型循环。
        session_id = self.headers.get("Mcp-Session-Id")
        if session_id:
            with SESSIONS_LOCK:
                SESSIONS.pop(session_id, None)
        self.send_response(204)
        self.end_headers()

    def _send_accepted(self, session_id: str) -> None:
        self.send_response(202)
        self.send_header("Mcp-Session-Id", session_id)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, payload: dict[str, Any], session_id: str) -> None:
        # Streamable HTTP 允许 POST 返回 application/json 或 text/event-stream。
        # 这里选择单条 SSE event，让 response 的“流式外壳”清晰可见。
        body = f"event: message\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode(
            "utf-8"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Mcp-Session-Id", session_id)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        # GET 是服务端主动推送通知的可选通道；本 Demo 把一条 SSE 放在每个 POST
        # 响应里，因此不额外维护一个长期 GET stream。
        if self.path == MCP_PATH:
            self.send_response(405)
            self.send_header("Allow", "POST, DELETE")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_error(404, "MCP endpoint is /mcp")


def run_server(host: str, port: int) -> None:
    # ThreadingHTTPServer 为每个 HTTP 请求提供线程；serve_forever() 就是服务端主循环。
    server = ThreadingHTTPServer((host, port), RawMCPHandler)
    print(f"raw MCP server: http://{host}:{port}{MCP_PATH}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


class RawMCPClient:
    """用 urllib 直接发送 MCP JSON-RPC，不依赖 mcp Python SDK。"""

    def __init__(self, url: str) -> None:
        self.url = url
        # Session ID 由 initialize 的响应分配，后续请求通过 Header 带回去。
        self.session_id: str | None = None
        # JSON-RPC request id 用来把异步/并发响应对应回原请求。
        self._next_id = 1

    def connect(self) -> dict[str, Any]:
        """connect 是本地编排函数；它内部发起 initialize 和 initialized。"""

        print("[client] connect() -> initialize")
        initialized = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "raw-python-client", "version": "0.1.0"},
            },
        )
        print("[client] initialize -> notifications/initialized")
        self._request("notifications/initialized", None, notification=True)
        return initialized["result"]

    def list_tools(self) -> list[dict[str, Any]]:
        # 这里只拿到 Server 的声明；Host 后面还要决定筛选哪些给模型。
        response = self._request("tools/list", {})
        return response["result"]["tools"]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        # name 是 Server 侧原始 Tool 名称；Host 的 mcp__... 命名空间不传给 Server。
        response = self._request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        return response["result"]

    def close(self) -> None:
        # finally 中调用 close，保证交互退出或异常时尽量释放 session。
        if not self.session_id:
            return
        request = Request(
            self.url,
            method="DELETE",
            headers={"Mcp-Session-Id": self.session_id},
        )
        try:
            with urlopen(request, timeout=10) as response:
                print(f"[wire] DELETE /mcp -> HTTP {response.status}")
        except (HTTPError, URLError) as exc:
            print(f"[client] session close failed: {exc}")
        finally:
            self.session_id = None

    def _request(
        self,
        method: str,
        params: dict[str, Any] | None,
        *,
        notification: bool = False,
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not notification:
            # notification 没有 id，因此服务端只确认接收，不返回 JSON-RPC result。
            payload["id"] = self._next_id
            self._next_id += 1
        if params is not None:
            payload["params"] = params

        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            # initialize 后的所有请求复用同一个 MCP session 标识。
            headers["Mcp-Session-Id"] = self.session_id

        request = Request(self.url, data=json_bytes(payload), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=10) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    # 只有 initialize 或 Server 更新 session 时才需要覆盖本地值。
                    self.session_id = session_id
                content_type = response.headers.get("Content-Type", "")
                status = response.status
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"cannot reach MCP server: {exc.reason}") from exc

        print(
            f"[wire] POST {method} -> HTTP {status}, "
            f"{content_type.split(';', 1)[0]}, session={self.session_id}"
        )
        if notification or status == 202:
            return None
        if "text/event-stream" in content_type:
            # 本实验每个 POST 只返回一个 SSE message；真实流可能有多事件/持续连接。
            return self._parse_sse(body)
        return json.loads(body)

    @staticmethod
    def _parse_sse(body: str) -> dict[str, Any]:
        data_lines = [line[5:] for line in body.splitlines() if line.startswith("data:")]
        if not data_lines:
            raise RuntimeError(f"SSE response has no data event: {body!r}")
        return json.loads("\n".join(data_lines))


def print_tools(tools: list[dict[str, Any]]) -> None:
    # 这是 Host 观察 tools/list 的调试输出，不是模型调用本身。
    print("=== tools/list result ===")
    for tool in tools:
        print(f"- {tool['name']}: {tool['description']}")
        print(f"  inputSchema={json.dumps(tool['inputSchema'], ensure_ascii=False)}")


def to_model_tools(
    tools: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """把 MCP Tool definitions 转成模型工具，同时保存反向映射。"""

    model_tools: list[dict[str, Any]] = []
    name_map: dict[str, str] = {}
    for tool in tools:
        # 命名空间由 Host 添加，避免多个 MCP Server 的 Tool 重名。
        model_name = f"mcp__raw_code_http__{tool['name']}"
        model_tools.append(
            {
                "name": model_name,
                "description": tool["description"],
                "input_schema": tool["inputSchema"],
            }
        )
        name_map[model_name] = tool["name"]
    return model_tools, name_map


def mcp_result_to_text(result: dict[str, Any]) -> str:
    """把 MCP Tool result 编译成下一轮模型上下文中的文本。"""

    structured = result.get("structuredContent")
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False, indent=2)
    return "\n".join(
        block.get("text", "")
        for block in result.get("content", [])
        if block.get("type") == "text"
    ) or "<empty MCP tool result>"


def build_agent_system(initialize_result: dict[str, Any]) -> str:
    """把 initialize.instructions 放进模型可见的 System Prompt。"""

    server_info = initialize_result.get("serverInfo", {})
    instructions = initialize_result.get("instructions", "")
    return (
        "You are a small MCP learning agent.\n"
        f"Connected MCP server: {server_info.get('name', SERVER_NAME)}\n"
        f"Server instructions: {instructions}\n"
        "Use the namespaced MCP tools when the user's question needs the demo "
        "code index. If the question does not need the index, answer directly. "
        "After tool results arrive, answer the user in Chinese."
    )


async def run_agent(url: str, model: str | None, max_tokens: int) -> None:
    """运行最小模型 Loop；只有模型调用使用 SDK，MCP 仍走 RawMCPClient。"""

    if not model:
        raise RuntimeError(
            "agent 需要 MODEL_ID；请在 .env 中设置 MODEL_ID，或传入 --model。"
        )

    mcp_client = RawMCPClient(url)
    model_client = AsyncAnthropic(base_url=os.getenv("ANTHROPIC_BASE_URL") or None)
    try:
        # 这三步不是模拟：每一步都会穿过真实 HTTP MCP endpoint。
        initialize_result = mcp_client.connect()
        tool_defs = mcp_client.list_tools()
        model_tools, name_map = to_model_tools(tool_defs)
        system = build_agent_system(initialize_result)
        history: list[dict[str, Any]] = []

        print(f"[agent] connected to {url}")
        print("[agent] model-visible tools:", ", ".join(name_map))
        print("输入自然语言问题；输入 q/exit 退出。\n")

        while True:
            try:
                query = input("agent >> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if query.lower() in {"q", "exit"}:
                return
            if not query:
                continue

            history.append({"role": "user", "content": query})

            # 一个用户问题可能触发多轮：模型提出 Tool → Host 执行 → 结果回模型。
            while True:
                # 这一轮模型只看到 Host 编译后的 tools；它不知道 urllib 或 MCP session。
                response = await model_client.messages.create(
                    model=model,
                    system=system,
                    messages=history,
                    tools=model_tools,
                    max_tokens=max_tokens,
                )
                history.append({"role": "assistant", "content": response.content})

                if response.stop_reason != "tool_use":
                    # 模型没有继续提出 Tool，当前用户问题的 Agent Loop 结束。
                    for block in response.content:
                        if getattr(block, "type", None) == "text":
                            print(block.text)
                    break

                tool_results: list[dict[str, Any]] = []
                for block in response.content:
                    if getattr(block, "type", None) != "tool_use":
                        continue

                    original_name = name_map.get(block.name)
                    if original_name is None:
                        output = f"Unknown model tool: {block.name}"
                        is_error = True
                    else:
                        # 这里是 Host 的反向路由：模型名 -> Server 原始 Tool 名 -> MCP call。
                        print(f"[agent] model requested {block.name}({block.input})")
                        result = mcp_client.call_tool(original_name, block.input)
                        output = mcp_result_to_text(result)
                        is_error = bool(result.get("isError"))
                        print(f"[agent] MCP tools/call {original_name}, isError={is_error}")

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output,
                            "is_error": is_error,
                        }
                    )
                history.append({"role": "user", "content": tool_results})
    finally:
        mcp_client.close()
        await model_client.close()


def run_client(url: str, query: str | None) -> None:
    # client 命令只观察 MCP 协议；agent 命令才把协议调用接到模型循环。
    client = RawMCPClient(url)
    try:
        initialize_result = client.connect()
        print("=== initialize result ===")
        print(json.dumps(initialize_result, ensure_ascii=False, indent=2))

        tools = client.list_tools()
        print_tools(tools)

        if query is not None:
            result = client.call_tool("search_code", {"query": query, "limit": 5})
            print("=== tools/call search_code result ===")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        print("输入 list、search <query>、stats 或 q：")
        while True:
            command = input("raw-mcp >> ").strip()
            if command.lower() in {"q", "exit"}:
                return
            if command == "list":
                print_tools(client.list_tools())
                continue
            if command == "stats":
                print(json.dumps(client.call_tool("code_index_stats", {}), ensure_ascii=False, indent=2))
                continue
            if command.startswith("search "):
                print(
                    json.dumps(
                        client.call_tool("search_code", {"query": command[7:], "limit": 5}),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                continue
            print("未知命令：list、search <query>、stats、q")
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    server = subparsers.add_parser("server")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8765)

    client = subparsers.add_parser("client")
    client.add_argument("--url", default="http://127.0.0.1:8765/mcp")
    client.add_argument("--query", help="run one search and exit instead of entering the loop")

    agent = subparsers.add_parser("agent")
    agent.add_argument("--url", default="http://127.0.0.1:8765/mcp")
    agent.add_argument("--model", default=os.getenv("MODEL_ID"))
    agent.add_argument("--max-tokens", type=int, default=2000)

    args = parser.parse_args()
    if args.command == "server":
        run_server(args.host, args.port)
    elif args.command == "agent":
        asyncio.run(run_agent(args.url, args.model, args.max_tokens))
    else:
        run_client(args.url, args.query)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMCP client/server stopped.")
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
