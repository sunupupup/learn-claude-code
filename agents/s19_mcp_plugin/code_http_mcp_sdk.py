"""一个可运行的 Streamable HTTP MCP Server/Client 教学实验。

依赖：
    ..\\.venv\\Scripts\\python.exe -m pip install "mcp==2.2.0"

启动服务端（终端一）：
    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\code_http_mcp_sdk.py server

启动客户端（终端二）：
    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\code_http_mcp_sdk.py client

启动带有真实 MCP Tool Calling Loop 的客户端（终端二）：
    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\code_http_mcp_sdk.py agent

客户端会实际完成：
    Client(URL) -> tools/list -> tools/call(search_code)

agent 命令会在每次用户输入后运行一轮模型循环：
    用户问题 -> 模型选择 mcp__code_http_demo__* -> MCP tools/call -> 下一轮模型上下文

这里使用有会话的 Streamable HTTP（stateless_http=False），便于观察 MCP
Client 如何复用一次 HTTP MCP 会话。生产环境是否使用有状态会话，需要结合
负载均衡、会话亲和、断线恢复和部署拓扑单独决定。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from mcp import Client
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import TextContent


load_dotenv(override=True)


mcp = MCPServer(
    name="code-http-demo",
    title="Code HTTP Demo MCP",
    description="A small MCP server that searches a fixed code-example index.",
    # 这是 Server 级别的使用提示；Client 可以把它整理进模型上下文，
    # 但 initialize 本身不会自动把所有工具定义直接塞进模型。
    instructions=(
        "Use this server when the user asks to search the demo code index. "
        "The server is read-only and does not execute arbitrary code."
    ),
    version="0.1.0",
)
# MCPServer 对象保存 Server 元数据和注册表；下面的装饰器会把 Python 函数
# 转成 SDK 可暴露的 Tool definition，运行时再由 SDK 负责协议分发。


CODE_INDEX: list[dict[str, str]] = [
    {
        "path": "agent_loop.py",
        "summary": "Agent loop reads model output, executes tool calls, and appends results.",
    },
    {
        "path": "mcp_client.py",
        "summary": "MCP client connects to a server, lists tools, and calls a selected tool.",
    },
    {
        "path": "tool_registry.py",
        "summary": "Tool registry stores namespaced tool definitions before model invocation.",
    },
    {
        "path": "context_compiler.py",
        "summary": "Context compiler progressively loads only the capability metadata needed by a task.",
    },
]


@mcp.tool(title="Search code examples")
def search_code(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Search the read-only demo code index by path or summary text."""

    # SDK 根据函数签名生成 inputSchema；这里仍然要在业务层做边界校验。
    normalized_query = query.strip().lower()
    if not normalized_query:
        raise ToolError("query must not be empty")
    if not 1 <= limit <= 10:
        raise ToolError("limit must be between 1 and 10")

    matches = [
        item
        for item in CODE_INDEX
        if normalized_query in item["path"].lower()
        or normalized_query in item["summary"].lower()
    ]
    return matches[:limit]


@mcp.tool(title="Get code index statistics")
def code_index_stats() -> dict[str, int]:
    """Return small deterministic statistics for the demo index."""

    return {"indexed_files": len(CODE_INDEX)}


def run_server(args: argparse.Namespace) -> None:
    """Run the real HTTP MCP server; this process blocks until Ctrl+C."""

    print(
        f"MCP server listening on http://{args.host}:{args.port}{args.path}",
        flush=True,
    )
    # false 保留会话生命周期，适合本章观察 initialize/list/call 的连续交互。
    # 将来可用 --stateless-http 对比无状态部署模型。
    mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        streamable_http_path=args.path,
        stateless_http=args.stateless_http,
    )


async def run_client(args: argparse.Namespace) -> None:
    """Connect over HTTP, list definitions, then invoke a real remote tool."""

    # Client 上下文管理器负责连接/初始化/关闭；代码只显式保留 list 和 call。
    async with Client(args.url, read_timeout_seconds=30) as client:
        tool_result = await client.list_tools()
        print("=== tools/list ===")
        for tool in tool_result.tools:
            print(
                json.dumps(
                    {
                        "name": tool.name,
                        "title": tool.title,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                    },
                    ensure_ascii=False,
                )
            )

        call_result = await client.call_tool(
            "search_code",
            {"query": args.query, "limit": args.limit},
        )
        print("=== tools/call search_code ===")
        print(f"is_error={call_result.is_error}")
        if call_result.structured_content is not None:
            print(
                "structured_content="
                + json.dumps(call_result.structured_content, ensure_ascii=False)
            )
        for block in call_result.content:
            if isinstance(block, TextContent):
                print(f"text={block.text}")


def mcp_result_to_text(result: Any) -> str:
    """把 MCP ToolResult 转成下一轮模型能消费的文本。"""

    parts: list[str] = []
    if result.structured_content is not None:
        parts.append(
            json.dumps(result.structured_content, ensure_ascii=False, default=str)
        )
    for block in result.content:
        if isinstance(block, TextContent):
            parts.append(block.text)
    if not parts:
        parts.append("<empty MCP tool result>")
    return "\n".join(parts)


def build_anthropic_tools(
    tool_result: Any,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """把 MCP 的 Tool definitions 转成模型工具，并保留反向映射。"""

    model_tools: list[dict[str, Any]] = []
    name_map: dict[str, str] = {}
    for tool in tool_result.tools:
        # Host 给模型的名字带命名空间，避免多个 MCP Server 的 Tool 重名。
        model_name = f"mcp__code_http_demo__{tool.name}"
        model_tools.append(
            {
                "name": model_name,
                "description": tool.description or tool.title or tool.name,
                "input_schema": tool.input_schema,
            }
        )
        name_map[model_name] = tool.name
    return model_tools, name_map


def build_agent_system(client: Client) -> str:
    """把 Server instructions 作为 Host 编译出的模型上下文的一部分。"""

    server_info = client.server_info
    server_name = getattr(server_info, "name", "code-http-demo")
    instructions = client.instructions or (
        "Use this server only for the read-only demo code index."
    )
    return (
        "You are a small MCP learning agent.\n"
        f"Connected MCP server: {server_name}\n"
        f"Server instructions: {instructions}\n"
        "Use the namespaced MCP tools when the user asks about the indexed code. "
        "Do not claim to have searched files outside this server. "
        "After a tool result arrives, answer the user in Chinese."
    )


async def run_agent(args: argparse.Namespace) -> None:
    """Run an interactive LLM loop whose Tool calls cross a real HTTP boundary."""

    if not args.model:
        raise RuntimeError(
            "agent 需要 MODEL_ID；请在 .env 中设置 MODEL_ID，或传入 --model。"
        )

    # AsyncAnthropic 读取 ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL，兼容本章 code.py
    # 使用的自定义 OpenAI-compatible/代理网关配置。
    model_client = AsyncAnthropic(
        base_url=os.getenv("ANTHROPIC_BASE_URL") or None,
    )
    async with Client(args.url, read_timeout_seconds=30) as mcp_client:
        # 先发现 MCP Tool，再把它们编译成 Anthropic API 的 tools 格式。
        listed_tools = await mcp_client.list_tools()
        model_tools, name_map = build_anthropic_tools(listed_tools)
        system = build_agent_system(mcp_client)
        history: list[dict[str, Any]] = []

        print(f"Connected to {args.url}")
        print("Model-visible tools:", ", ".join(name_map))
        print("输入问题；输入 q/exit 退出。\n")

        while True:
            try:
                query = input("http-mcp >> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if query.strip().lower() in {"q", "exit"}:
                break
            if not query.strip():
                continue

            history.append({"role": "user", "content": query})
            while True:
                # 模型提出 tool_use 后，下面的 Host 路由会调用远程 MCP Tool，
                # 再把 tool_result 作为下一轮上下文的一部分送回模型。
                response = await model_client.messages.create(
                    model=args.model,
                    system=system,
                    messages=history,
                    tools=model_tools,
                    max_tokens=args.max_tokens,
                )
                history.append({"role": "assistant", "content": response.content})

                if response.stop_reason != "tool_use":
                    # 没有 tool_use 表示模型给出了当前问题的最终回答。
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
                        # 模型看到的是带命名空间的名字；MCP Server 收到原始名字。
                        print(f"[mcp] tools/call {original_name}({block.input})")
                        call_result = await mcp_client.call_tool(
                            original_name, block.input
                        )
                        output = mcp_result_to_text(call_result)
                        is_error = bool(call_result.is_error)
                        print(f"[mcp] is_error={is_error}")

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output,
                            "is_error": is_error,
                        }
                    )
                history.append({"role": "user", "content": tool_results})

    await model_client.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    server = subparsers.add_parser("server", help="start the Streamable HTTP MCP server")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8765)
    server.add_argument("--path", default="/mcp")
    server.add_argument(
        "--stateless-http",
        action="store_true",
        help="run without server-side MCP sessions",
    )
    server.set_defaults(handler=run_server)

    client = subparsers.add_parser("client", help="run the HTTP MCP client")
    client.add_argument("--url", default="http://127.0.0.1:8765/mcp")
    client.add_argument("--query", default="MCP")
    client.add_argument("--limit", type=int, default=5)
    client.set_defaults(handler=lambda args: asyncio.run(run_client(args)))

    agent = subparsers.add_parser(
        "agent", help="run an LLM loop backed by the remote MCP server"
    )
    agent.add_argument("--url", default="http://127.0.0.1:8765/mcp")
    agent.add_argument("--model", default=os.getenv("MODEL_ID"))
    agent.add_argument("--max-tokens", type=int, default=2000)
    agent.set_defaults(handler=lambda args: asyncio.run(run_agent(args)))

    return parser


if __name__ == "__main__":
    cli_args = build_parser().parse_args()
    try:
        cli_args.handler(cli_args)
    except KeyboardInterrupt:
        # uvicorn 会把 Ctrl+C 转成 KeyboardInterrupt；教学脚本应安静退出，
        # 不把正常的人工停机显示成一段误导性的异常堆栈。
        print("MCP server stopped.")
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
