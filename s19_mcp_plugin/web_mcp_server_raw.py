"""不使用 MCP SDK 的 Web MCP Server。

这个版本只使用 Python 标准库，把一个 MCP Server 直接实现成 HTTP 服务，方便
观察“装饰器背后到底做了什么”：

    initialize               建立 session、协商协议版本和能力
    notifications/initialized 完成初始化通知
    tools/list                获取 Tool definitions
    tools/call                调用 Tool
    resources/list            获取静态 Resource
    resources/templates/list  获取 Resource template
    resources/read            读取 Resource 内容
    prompts/list              获取 Prompt 定义
    prompts/get               生成一个 Prompt
    DELETE /mcp               结束 HTTP session

启动服务端：
    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\web_mcp_server_raw.py server

启动原始 HTTP Client 探测三类 Primitive：
    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\web_mcp_server_raw.py probe

它不是生产级 HTTP Server：session 只保存在进程内，鉴权、租户隔离、限流、审计、
分布式路由和完整的 Streamable HTTP 长连接能力都没有实现。目标是让每个 JSON-RPC
method 和 HTTP 响应都能被看到。
"""

from __future__ import annotations

import argparse
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "web-demo-raw"
SERVER_VERSION = "0.1.0"
MCP_PATH = "/mcp"
PUBLIC_BASE_URL = "http://127.0.0.1:8781"
PAGE_INDEX_URI = f"{PUBLIC_BASE_URL}/pages/index"
PAGE_URI_TEMPLATE = f"{PUBLIC_BASE_URL}/pages/{{slug}}"


PAGES: dict[str, str] = {
    "home": "# Home\n\nThis is the home page of the demo web site.",
    "about": "# About\n\nThis site demonstrates Tools, Resources, and Prompts.",
    "mcp": "# MCP\n\nMCP connects a Host to tools and data through a standard protocol.",
}
# 先固定一个很小的数据集，让注意力集中在 MCP 协议；业务数据源可以以后替换。


# Tool definition 会被 tools/list 返回给 Host；真正的函数仍由 Server 侧执行。
TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_pages",
        "title": "Search web pages",
        "description": "Search the demo site's pages by slug or content.",
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
        "name": "page_stats",
        "title": "Get web page statistics",
        "description": "Return deterministic statistics for the demo site.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


RESOURCES: list[dict[str, Any]] = [
    {
        "uri": PAGE_INDEX_URI,
        "name": "page_index",
        "title": "Web page index",
        "description": "A list of pages exposed by this demo web server.",
        "mimeType": "text/markdown",
    }
]

RESOURCE_TEMPLATES: list[dict[str, Any]] = [
    {
        "uriTemplate": PAGE_URI_TEMPLATE,
        "name": "page_content",
        "title": "Web page content",
        "description": "Read one page by its slug.",
        "mimeType": "text/markdown",
    }
]

PROMPTS: list[dict[str, Any]] = [
    {
        "name": "summarize_page",
        "title": "Summarize a web page",
        "description": "Create a reusable prompt for summarizing a page Resource.",
        "arguments": [
            {
                "name": "slug",
                "description": "The page slug, such as mcp.",
                "required": True,
            },
            {
                "name": "focus",
                "description": "What the summary should focus on.",
                "required": False,
            },
        ],
    }
]


# 为了让学习者看到 session 的作用，这里显式保存初始化状态。生产环境不能只靠
# 这个进程内字典：需要 TTL、并发控制、分布式路由和断线恢复策略。
SESSIONS: dict[str, dict[str, Any]] = {}
SESSIONS_LOCK = threading.Lock()


def json_bytes(value: Any) -> bytes:
    # JSON-RPC payload 需要先序列化成 JSON，再编码为 HTTP body 的 UTF-8 字节。
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def jsonrpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    # result 是 JSON-RPC 外层；其中的 result 才是 MCP primitive 的返回结构。
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def call_local_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """执行 Tool 的业务函数；JSON-RPC 只负责把调用路由到这里。"""

    if name == "search_pages":
        query = arguments.get("query")
        limit = arguments.get("limit", 5)
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        needle = query.lower()
        return {
            "matches": [
                {"slug": slug, "preview": text[:120]}
                for slug, text in PAGES.items()
                if needle in slug.lower() or needle in text.lower()
            ][:limit]
        }

    if name == "page_stats":
        return {"page_count": len(PAGES)}

    raise KeyError(f"unknown tool: {name}")


def read_local_resource(uri: str) -> str:
    """根据 Resource URI 返回文本；Resource 是被读取的数据，不是 RPC 函数。"""

    # Resource 通过 URI 寻址；读取数据不需要伪装成一个 Tool call。
    if uri == PAGE_INDEX_URI:
        return "\n".join(f"- {slug}" for slug in sorted(PAGES))

    prefix = f"{PUBLIC_BASE_URL}/pages/"
    if uri.startswith(prefix):
        slug = uri[len(prefix) :]
        if slug in PAGES:
            return PAGES[slug]

    raise KeyError(f"unknown resource: {uri}")


def get_local_prompt(name: str, arguments: dict[str, Any]) -> str:
    """根据 Prompt 名称和参数生成可复用的消息文本。"""

    # Prompt 是客户端/用户选择后获取的消息模板，和模型自动触发的 Tool 不同。
    if name != "summarize_page":
        raise KeyError(f"unknown prompt: {name}")
    slug = arguments.get("slug")
    focus = arguments.get("focus", "main points")
    if not isinstance(slug, str) or slug not in PAGES:
        raise ValueError("slug must be an existing page slug")
    if not isinstance(focus, str) or not focus.strip():
        raise ValueError("focus must be a non-empty string")
    return (
        f"Read resource {PUBLIC_BASE_URL}/pages/{slug}, then summarize the page "
        f"with a focus on {focus} "
        "in Chinese with three concise bullet points."
    )


class RawWebMCPHandler(BaseHTTPRequestHandler):
    """把 HTTP POST 映射到 MCP JSON-RPC，并用一条 SSE 返回响应。"""

    server_version = "RawWebMCP/0.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[server] {self.command} {self.path} - {format % args}", flush=True)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        # HTTP 只负责把 body 送到这里；MCP method 决定后续走 Tool、Resource 还是 Prompt。
        if self.path.split("?", 1)[0] != MCP_PATH:
            self.send_error(404, "MCP endpoint is /mcp")
            return

        try:
            # 这里手写 SDK 通常隐藏的“读取 HTTP body -> 解析 JSON”步骤。
            length = int(self.headers.get("Content-Length", "0"))
            message = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(400, jsonrpc_error(None, -32700, f"invalid JSON: {exc}"))
            return

        method = message.get("method")
        request_id = message.get("id")
        session_id = self.headers.get("Mcp-Session-Id")

        if method == "initialize":
            # initialize 创建 session；客户端的 connect() 只是本地编排函数名。
            session_id = str(uuid.uuid4())
            with SESSIONS_LOCK:
                SESSIONS[session_id] = {"initialized": False}
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                # capabilities 表示本 Server 会提供哪几类 primitive；具体定义还要
                # 通过 tools/list、resources/list、prompts/list 再分别取得。
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    f"Use search_pages for page lookup, read {PUBLIC_BASE_URL}/pages/{{slug}} "
                    "for page content, and summarize_page for a reusable prompt."
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
            # 通知没有 id，也不返回 JSON-RPC result。
            self._send_accepted(session_id)
            return

        if not session["initialized"]:
            self._send_json(
                400,
                jsonrpc_error(request_id, -32002, "send notifications/initialized first"),
            )
            return

        try:
            # 这段 if/elif 就是 SDK 内部“按 method 查注册表并调用处理器”的简化版。
            if method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                result = self._call_tool(message)
            elif method == "resources/list":
                result = {"resources": RESOURCES}
            elif method == "resources/templates/list":
                result = {"resourceTemplates": RESOURCE_TEMPLATES}
            elif method == "resources/read":
                result = self._read_resource(message)
            elif method == "prompts/list":
                result = {"prompts": PROMPTS}
            elif method == "prompts/get":
                result = self._get_prompt(message)
            else:
                self._send_sse(
                    jsonrpc_error(request_id, -32601, f"method not found: {method}"),
                    session_id,
                )
                return
        except (KeyError, TypeError, ValueError) as exc:
            # 参数或 URI 错误属于 JSON-RPC 请求错误；Tool 的业务失败则由
            # _call_tool 转成 result.isError，方便模型看到工具结果。
            self._send_sse(jsonrpc_error(request_id, -32602, str(exc)), session_id)
            return

        self._send_sse(jsonrpc_result(request_id, result), session_id)

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path.split("?", 1)[0] != MCP_PATH:
            self.send_error(404, "MCP endpoint is /mcp")
            return
        session_id = self.headers.get("Mcp-Session-Id")
        if session_id:
            with SESSIONS_LOCK:
                SESSIONS.pop(session_id, None)
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", 1)[0]

        # Resource URI 现在是真实 HTTP 地址，因此浏览器/curl 也可以直接读取页面。
        if path == "/pages/index":
            self._send_page(200, "\n".join(f"- {slug}" for slug in sorted(PAGES)))
            return
        page_prefix = "/pages/"
        if path.startswith(page_prefix):
            slug = path[len(page_prefix) :]
            if slug in PAGES:
                self._send_page(200, PAGES[slug])
                return
            self._send_json(404, {"error": f"unknown page slug: {slug}"})
            return

        # MCP 的 GET 推送流在本学习版没有单独维护；每个 POST 响应已经包含一条 SSE。
        if path == MCP_PATH:
            self.send_response(405)
            self.send_header("Allow", "POST, DELETE")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_error(404, "MCP endpoint is /mcp")

    def _send_page(self, status: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _call_tool(self, message: dict[str, Any]) -> dict[str, Any]:
        # tools/call 的 arguments 进入业务函数；Tool 失败保留在 result.isError。
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            data = call_local_tool(name, arguments)
        except (KeyError, TypeError, ValueError) as exc:
            return {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            }
        return {
            "content": [
                {"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}
            ],
            "structuredContent": data,
            "isError": False,
        }

    def _read_resource(self, message: dict[str, Any]) -> dict[str, Any]:
        # Resource 的返回值使用 contents + uri/mimeType/text（也可以是 blob）。
        params = message.get("params") or {}
        uri = params.get("uri")
        if not isinstance(uri, str):
            raise ValueError("resources/read requires a string uri")
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": read_local_resource(uri),
                }
            ]
        }

    def _get_prompt(self, message: dict[str, Any]) -> dict[str, Any]:
        # prompts/get 返回 messages，Host 可以将它们编译进下一轮模型上下文。
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        text = get_local_prompt(name, arguments)
        return {
            "description": "A reusable prompt for summarizing a page Resource.",
            "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
        }

    def _send_accepted(self, session_id: str) -> None:
        self.send_response(202)
        self.send_header("Mcp-Session-Id", session_id)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, payload: dict[str, Any], session_id: str) -> None:
        # 为了看清 Streamable HTTP 的“流式外壳”，每个请求只发一条 SSE message。
        body = (
            f"event: message\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Mcp-Session-Id", session_id)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()


def run_server(host: str, port: int) -> None:
    # serve_forever() 是这个 Web Server 的主循环；它与 Agent Loop 是两种不同循环。
    server = ThreadingHTTPServer((host, port), RawWebMCPHandler)
    print(f"raw web MCP server: http://{host}:{port}{MCP_PATH}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


class RawWebMCPClient:
    """用 urllib 直接走 HTTP，不依赖 MCP Python SDK。"""

    def __init__(self, url: str) -> None:
        self.url = url
        # initialize 响应中的 session id 会被后续 HTTP 请求复用。
        self.session_id: str | None = None
        # 每个有响应的 JSON-RPC request 都需要唯一 id；通知不分配 id。
        self._next_id = 1

    def connect(self) -> dict[str, Any]:
        # connect 是本地便利方法，内部仍然是两个真实 MCP 请求。
        print("[client] connect() -> initialize")
        initialized = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "raw-web-client", "version": "0.1.0"},
            },
        )
        print("[client] initialize -> notifications/initialized")
        self._request("notifications/initialized", None, notification=True)
        return initialized["result"]

    def list_tools(self) -> list[dict[str, Any]]:
        # 发现定义，不执行 Tool。
        return self._request("tools/list", {})["result"]["tools"]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        # Server 侧使用原始 name；Host 命名空间只存在于模型工具池一侧。
        return self._request(
            "tools/call", {"name": name, "arguments": arguments}
        )["result"]

    def list_resources(self) -> list[dict[str, Any]]:
        # 先发现静态 URI，再用 read_resource 读取具体内容。
        return self._request("resources/list", {})["result"]["resources"]

    def list_resource_templates(self) -> list[dict[str, Any]]:
        # template 让 Client 知道 URI 参数的形状，例如 http://127.0.0.1:8781/pages/{slug}。
        return self._request("resources/templates/list", {})["result"][
            "resourceTemplates"
        ]

    def read_resource(self, uri: str) -> dict[str, Any]:
        # 这是数据读取 method，返回 contents，不会产生 Tool use。
        return self._request("resources/read", {"uri": uri})["result"]

    def list_prompts(self) -> list[dict[str, Any]]:
        # 发现可供用户选择的 Prompt 模板。
        return self._request("prompts/list", {})["result"]["prompts"]

    def get_prompt(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        # 参数填充发生在 Server；Client 得到最终 messages。
        return self._request(
            "prompts/get", {"name": name, "arguments": arguments}
        )["result"]

    def close(self) -> None:
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
            # notification 没有 id，也就没有对应的 response body。
            payload["id"] = self._next_id
            self._next_id += 1
        if params is not None:
            payload["params"] = params

        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            # 同一 session 让 Server 能关联 initialize 与后续请求。
            headers["Mcp-Session-Id"] = self.session_id

        request = Request(self.url, data=json_bytes(payload), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=10) as response:
                returned_session = response.headers.get("Mcp-Session-Id")
                if returned_session:
                    # 首次 initialize 会返回它；后续请求继续沿用。
                    self.session_id = returned_session
                status = response.status
                content_type = response.headers.get("Content-Type", "")
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
            # 学习版每个 POST 只有一条 SSE；解析后还原成 JSON-RPC 对象。
            return self._parse_sse(body)
        return json.loads(body)

    @staticmethod
    def _parse_sse(body: str) -> dict[str, Any]:
        data_lines = [line[5:] for line in body.splitlines() if line.startswith("data:")]
        if not data_lines:
            raise RuntimeError(f"SSE response has no data event: {body!r}")
        return json.loads("\n".join(data_lines))


def print_probe_result(client: RawWebMCPClient) -> None:
    # 按“发现 -> 使用”的顺序调用三类 primitive，输出就是学习用的观察记录。
    initialize_result = client.connect()
    print("\n=== initialize result ===")
    print(json.dumps(initialize_result, ensure_ascii=False, indent=2))

    tools = client.list_tools()
    print("\n=== tools/list ===")
    print(json.dumps(tools, ensure_ascii=False, indent=2))
    print("\n=== tools/call search_pages ===")
    print(json.dumps(client.call_tool("search_pages", {"query": "MCP"}), ensure_ascii=False, indent=2))

    print("\n=== resources/list ===")
    print(json.dumps(client.list_resources(), ensure_ascii=False, indent=2))
    print("\n=== resources/templates/list ===")
    print(json.dumps(client.list_resource_templates(), ensure_ascii=False, indent=2))
    print(f"\n=== resources/read {PUBLIC_BASE_URL}/pages/mcp ===")
    print(json.dumps(client.read_resource(f"{PUBLIC_BASE_URL}/pages/mcp"), ensure_ascii=False, indent=2))

    print("\n=== prompts/list ===")
    print(json.dumps(client.list_prompts(), ensure_ascii=False, indent=2))
    print("\n=== prompts/get summarize_page ===")
    print(
        json.dumps(
            client.get_prompt(
                "summarize_page", {"slug": "mcp", "focus": "the protocol boundary"}
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    # server 长驻监听；probe 连接、探测、关闭 session 后退出。
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    server = subparsers.add_parser("server")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8781)

    probe = subparsers.add_parser("probe")
    probe.add_argument("--url", default="http://127.0.0.1:8781/mcp")

    args = parser.parse_args()
    if args.command == "server":
        run_server(args.host, args.port)
        return

    client = RawWebMCPClient(args.url)
    try:
        print_probe_result(client)
    finally:
        client.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nRaw web MCP server/client stopped.")
