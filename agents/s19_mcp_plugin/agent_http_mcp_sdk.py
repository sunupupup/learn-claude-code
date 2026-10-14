"""通过 MCP SDK 连接真实 HTTP MCP Server 的 Agent Loop。

这个文件只负责 Agent/Host 一侧，不启动 MCP Server。默认连接官方参考服务
server-everything：

    npx -y @modelcontextprotocol/server-everything streamableHttp

然后在另一个终端运行：

    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\agent_http_mcp_sdk.py inspect
    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\agent_http_mcp_sdk.py agent

完整链路是：

    MCP Client -> tools/list -> Host 转换成模型 tools
    用户问题 -> 模型 tool_use -> MCP Client tools/call -> Tool result -> 下一轮模型

这里的“SDK 版”指 MCP Client 使用 Python MCP SDK。模型调用仍使用 Anthropic SDK，
因为本例的学习重点是“Agent 如何连接远程 MCP”，不是手写模型供应商 HTTP API。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from typing import Any

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from mcp import Client


load_dotenv(override=True)

# 官方 Everything Server 的 instructions 可能包含 emoji；Windows PowerShell 的
# 默认代码页不一定能输出它。统一使用 UTF-8，避免“协议成功但打印结果失败”。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_URL = "http://127.0.0.1:3001/mcp"
DEFAULT_SERVER_NAME = "everything"


def normalize_namespace(value: str) -> str:
    """把 Server 名称压成模型工具名中稳定、可读的命名空间。"""

    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "server"


def build_model_tools(
    tool_result: Any,
    server_name: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """把 MCP tools/list 的结果编译成模型工具，并保留反向路由。"""

    namespace = normalize_namespace(server_name)
    model_tools: list[dict[str, Any]] = []
    name_map: dict[str, str] = {}
    for tool in tool_result.tools:
        # Host 添加命名空间，避免多个 MCP Server 暴露同名 Tool 时发生碰撞。
        model_name = f"mcp__{namespace}__{tool.name}"
        model_tools.append(
            {
                "name": model_name,
                "description": tool.description or tool.title or tool.name,
                "input_schema": tool.input_schema,
            }
        )
        name_map[model_name] = tool.name
    return model_tools, name_map


def block_to_text(block: Any) -> str:
    """把 MCP 返回的文本或其他内容块转成模型可消费的字符串。"""

    if getattr(block, "type", None) == "text":
        return getattr(block, "text", "")
    try:
        return json.dumps(block, ensure_ascii=False, default=str)
    except TypeError:
        return str(block)


def mcp_result_to_text(result: Any) -> str:
    """把 CallToolResult 编译成下一轮 Anthropic messages 的 tool_result 内容。"""

    parts: list[str] = []
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        parts.append(json.dumps(structured, ensure_ascii=False, default=str))
    parts.extend(
        block_to_text(block)
        for block in getattr(result, "content", [])
        if block_to_text(block)
    )
    return "\n".join(parts) or "<empty MCP tool result>"


def build_system_prompt(client: Client, server_name: str) -> str:
    """把 MCP Server 元信息编译进模型可见的 System Prompt。"""

    server_info = getattr(client, "server_info", None)
    actual_name = getattr(server_info, "name", server_name)
    instructions = getattr(client, "instructions", None) or (
        "Use the connected MCP server's tools when they are relevant."
    )
    return (
        "You are a small MCP learning agent.\n"
        f"Connected MCP server: {actual_name}\n"
        f"Server instructions: {instructions}\n"
        "Use the namespaced MCP tools when they help answer the user's request. "
        "After receiving tool results, answer the user in Chinese."
    )


async def inspect_server(url: str) -> None:
    """只做 HTTP MCP 能力探测，不调用模型，便于先验证连接。"""

    async with Client(url, read_timeout_seconds=30) as client:
        print("server_info=", client.server_info)
        print("instructions=", client.instructions)

        tools = await client.list_tools()
        print("tools=", [tool.name for tool in tools.tools])

        # Resources 和 Prompts 是 Client/Host 主动使用的能力，不会自动变成模型 Tool。
        try:
            resources = await client.list_resources()
            print("resources=", [resource.uri for resource in resources.resources])
        except Exception as exc:
            print("resources=<unavailable>", type(exc).__name__, exc)

        try:
            prompts = await client.list_prompts()
            print("prompts=", [prompt.name for prompt in prompts.prompts])
        except Exception as exc:
            print("prompts=<unavailable>", type(exc).__name__, exc)


async def run_agent(
    url: str,
    server_name: str,
    model: str | None,
    max_tokens: int,
) -> None:
    """运行与 code.py 相同形状的交互式 Agent Loop。"""

    if not model:
        raise RuntimeError(
            "agent 需要 MODEL_ID；请在 .env 中设置 MODEL_ID，或通过 --model 传入。"
        )

    model_client = AsyncAnthropic(base_url=os.getenv("ANTHROPIC_BASE_URL") or None)
    try:
        # Client 上下文管理器负责 MCP initialize、会话和关闭；这里观察 Host 逻辑。
        async with Client(url, read_timeout_seconds=30) as mcp_client:
            listed_tools = await mcp_client.list_tools()
            model_tools, name_map = build_model_tools(listed_tools, server_name)
            system = build_system_prompt(mcp_client, server_name)
            history: list[dict[str, Any]] = []

            print(f"Connected to HTTP MCP server: {url}")
            print("Model-visible tools:", ", ".join(name_map) or "<none>")
            print("输入自然语言问题；输入 q/exit 退出。\n")

            while True:
                try:
                    query = input("mcp-agent-sdk >> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return
                if query.lower() in {"q", "exit"}:
                    return
                if not query:
                    continue

                history.append({"role": "user", "content": query})

                # 一次用户问题可以经历多轮：模型提出 Tool，Host 执行，再把结果送回模型。
                while True:
                    response = await model_client.messages.create(
                        model=model,
                        system=system,
                        messages=history,
                        tools=model_tools,
                        max_tokens=max_tokens,
                    )
                    history.append({"role": "assistant", "content": response.content})

                    if response.stop_reason != "tool_use":
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
                            print(f"[mcp-sdk] tools/call {original_name}({block.input})")
                            try:
                                result = await mcp_client.call_tool(
                                    original_name, block.input
                                )
                                output = mcp_result_to_text(result)
                                is_error = bool(getattr(result, "is_error", False))
                            except Exception as exc:
                                output = f"MCP call failed: {type(exc).__name__}: {exc}"
                                is_error = True
                            print(f"[mcp-sdk] is_error={is_error}")

                        # tool_use_id 必须和模型刚才提出的 tool_use 一一对应。
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
        await model_client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect = subparsers.add_parser("inspect", help="discover the remote MCP server")
    inspect.add_argument("--url", default=DEFAULT_URL)

    agent = subparsers.add_parser("agent", help="run the model + MCP Agent Loop")
    agent.add_argument("--url", default=DEFAULT_URL)
    agent.add_argument("--server-name", default=DEFAULT_SERVER_NAME)
    agent.add_argument("--model", default=os.getenv("MODEL_ID"))
    agent.add_argument("--max-tokens", type=int, default=2000)

    args = parser.parse_args()
    if args.command == "inspect":
        asyncio.run(inspect_server(args.url))
    else:
        asyncio.run(run_agent(args.url, args.server_name, args.model, args.max_tokens))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMCP SDK Agent stopped.")
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
