"""使用 Python MCP SDK 的 Web MCP Server。

启动：
    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\web_mcp_server_sdk.py server

另一个终端探测三类 Primitive：
    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\web_mcp_server_sdk.py probe

这个文件重点展示 SDK 装饰器：
    @mcp.tool()       -> tools/list / tools/call
    @mcp.resource()   -> resources/list / resources/read
    @mcp.prompt()     -> prompts/list / prompts/get
"""

from __future__ import annotations

import argparse
import asyncio
from mcp import Client
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import TextContent, TextResourceContents
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response


PAGES: dict[str, str] = {
    "home": "# Home\n\nThis is the home page of the demo web site.",
    "about": "# About\n\nThis site demonstrates Tools, Resources, and Prompts.",
    "mcp": "# MCP\n\nMCP connects a Host to tools and data through a standard protocol.",
}
# PAGES 是这个学习 Server 的“下游数据源”。真实项目里这里可以换成数据库、
# Figma API 或内部 HTTP 服务，MCP 层负责把它们整理成统一 primitive。

# 这次故意使用真正的 HTTP URI：它既是 MCP Resource 的标识，也能被浏览器直接 GET。
# 端口与默认 server 端口保持一致；如果改端口，需要同步修改这个教学常量。
PUBLIC_BASE_URL = "http://127.0.0.1:8780"
PAGE_INDEX_URI = f"{PUBLIC_BASE_URL}/pages/index"
PAGE_URI_TEMPLATE = f"{PUBLIC_BASE_URL}/pages/{{slug}}"


mcp = MCPServer(
    name="web-demo-sdk",
    title="Web MCP SDK Demo",
    description="A tiny web-site MCP server exposing all three MCP primitives.",
    instructions=(
        "Use search_pages when the user asks to find a page. "
        f"Read {PUBLIC_BASE_URL}/pages/{{slug}} for page content. "
        "Use summarize_page to prepare a summarization prompt."
    ),
    version="0.1.0",
)
# Server instructions 是能力使用建议；Host 可以把它放进上下文，实际 Tool/Resource
# 列表仍由对应的 list method 发现。


@mcp.tool(title="Search web pages")
def search_pages(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Search the demo site's pages by slug or content."""

    # 装饰器负责注册 definition，函数体负责真正执行和校验参数。
    if not query.strip():
        raise ToolError("query must not be empty")
    if not 1 <= limit <= 10:
        raise ToolError("limit must be between 1 and 10")
    needle = query.lower()
    return [
        {"slug": slug, "preview": text[:120]}
        for slug, text in PAGES.items()
        if needle in slug.lower() or needle in text.lower()
    ][:limit]


@mcp.tool(title="Get web page statistics")
def page_stats() -> dict[str, int]:
    """Return deterministic statistics for the demo site."""

    return {"page_count": len(PAGES)}


@mcp.resource(PAGE_INDEX_URI)
def page_index() -> str:
    """A static Resource containing the site's page index."""

    # 静态 URI 没有参数，Client 读取该 URI 时 SDK 调用这个函数。
    return "\n".join(f"- {slug}" for slug in sorted(PAGES))


@mcp.resource(PAGE_URI_TEMPLATE)
def page_content(slug: str) -> str:
    """A Resource template that reads one page by slug."""

    # {slug} 是 Resource template 的路径参数；它不是 tools/call 的 arguments。
    try:
        return PAGES[slug]
    except KeyError as exc:
        raise ValueError(f"unknown page slug: {slug}") from exc


@mcp.prompt(title="Summarize a web page")
def summarize_page(slug: str, focus: str = "main points") -> str:
    """Return a reusable prompt that asks an agent to summarize a page Resource."""

    # Prompt 返回的是消息模板，供客户端/用户选择后放入模型上下文。
    if slug not in PAGES:
        raise ValueError(f"unknown page slug: {slug}")
    return (
        f"Read resource {PUBLIC_BASE_URL}/pages/{slug}, then summarize the page "
        f"with a focus on {focus} "
        "in Chinese with three concise bullet points."
    )


@mcp.custom_route("/pages/index", methods=["GET"])
async def page_index_http(request: Request) -> Response:
    """普通 HTTP 路由：浏览器可以直接 GET 这个 Resource 的 URI。"""

    return PlainTextResponse(page_index(), media_type="text/markdown")


@mcp.custom_route("/pages/{slug}", methods=["GET"])
async def page_content_http(request: Request) -> Response:
    """普通 HTTP 路由：把 Resource template 的 slug 映射到页面内容。"""

    slug = request.path_params["slug"]
    try:
        return PlainTextResponse(page_content(slug), media_type="text/markdown")
    except ValueError:
        return JSONResponse({"error": f"unknown page slug: {slug}"}, status_code=404)


def run_server(host: str, port: int) -> None:
    """SDK 负责 HTTP、JSON-RPC、session 和三类 primitive 的协议分发。"""

    # mcp.run() 内部启动 HTTP/ASGI 事件循环，并持续阻塞监听请求。
    print(f"SDK web MCP server: http://{host}:{port}/mcp", flush=True)
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        streamable_http_path="/mcp",
        stateless_http=False,
    )


async def probe(url: str) -> None:
    """用 SDK Client 依次访问 Tools、Resources、Prompts。"""

    # 这个 Client 只做协议探测，不调用 LLM；每个 primitive 都在这里单独展示。
    async with Client(url) as client:
        print("server_info=", client.server_info)
        print("instructions=", client.instructions)

        tools = await client.list_tools()
        print("\n=== tools/list ===")
        for tool in tools.tools:
            print(tool.name, "->", tool.description)

        called = await client.call_tool("search_pages", {"query": "MCP", "limit": 5})
        print("\n=== tools/call search_pages ===")
        for block in called.content:
            if isinstance(block, TextContent):
                print(block.text)
        print("structured=", called.structured_content)

        # Resources 是 Client 主动读取的数据，不会自动变成模型 Tool。
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        print("\n=== resources/list ===")
        print([resource.uri for resource in resources.resources])
        print("=== resources/templates/list ===")
        print([template.uri_template for template in templates.resource_templates])

        read = await client.read_resource(f"{PUBLIC_BASE_URL}/pages/mcp")
        print(f"=== resources/read {PUBLIC_BASE_URL}/pages/mcp ===")
        for content in read.contents:
            if isinstance(content, TextResourceContents):
                print(content.text)

        # Prompt 也要先发现，再按名称和参数取得最终 messages。
        prompts = await client.list_prompts()
        print("\n=== prompts/list ===")
        print([prompt.name for prompt in prompts.prompts])
        prompt = await client.get_prompt(
            "summarize_page", {"slug": "mcp", "focus": "the protocol boundary"}
        )
        print("=== prompts/get summarize_page ===")
        for message in prompt.messages:
            print(message.role, message.content)


def main() -> None:
    # server 是长驻进程；probe 是一次性 Client。拆开后更容易观察网络边界。
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    server = subparsers.add_parser("server")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8780)

    client = subparsers.add_parser("probe")
    client.add_argument("--url", default="http://127.0.0.1:8780/mcp")

    args = parser.parse_args()
    if args.command == "server":
        run_server(args.host, args.port)
    else:
        asyncio.run(probe(args.url))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSDK web MCP server stopped.")
