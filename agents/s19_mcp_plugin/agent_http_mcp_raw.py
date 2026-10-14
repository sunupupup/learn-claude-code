"""不使用 MCP SDK 的 HTTP MCP Agent Loop。

这个文件只负责 Agent/Host 一侧，不启动 MCP Server。默认连接官方参考服务
server-everything：

    npx -y @modelcontextprotocol/server-everything streamableHttp

然后在另一个终端运行：

    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\agent_http_mcp_raw.py inspect
    ..\\.venv\\Scripts\\python.exe s19_mcp_plugin\\agent_http_mcp_raw.py agent

“无 SDK”只针对 MCP：本文件用 urllib 手写 initialize、tools/list、tools/call、
SSE 解析和 session header。模型调用仍使用 Anthropic SDK，保持和 code.py 相同的
Agent Loop 结构，避免把两个学习主题混在一起。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from anthropic import AsyncAnthropic
from dotenv import load_dotenv


load_dotenv(override=True)

# Everything Server 的 instructions 可能包含 emoji；协议已经成功时，输出也不能
# 因 Windows 默认 GBK 编码失败，所以 Agent 进程启动时切换到 UTF-8。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROTOCOL_VERSION = "2025-11-25"
DEFAULT_URL = "http://127.0.0.1:3001/mcp"
DEFAULT_SERVER_NAME = "everything"


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def normalize_namespace(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "server"


class RawHTTPMCPClient:
    """只用标准库发送 MCP JSON-RPC；它是 Host 内部的协议 Client。"""

    def __init__(self, url: str) -> None:
        self.url = url
        self.session_id: str | None = None
        self._next_id = 1

    def connect(self) -> dict[str, Any]:
        """connect 是本地编排函数，内部按顺序发起两个真实 MCP 请求。"""

        print("[raw-mcp] initialize")
        initialize = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "raw-http-agent", "version": "0.1.0"},
            },
        )
        print("[raw-mcp] notifications/initialized")
        self._request("notifications/initialized", None, notification=True)
        return initialize["result"]

    def list_tools(self) -> list[dict[str, Any]]:
        return self._request("tools/list", {})["result"]["tools"]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "tools/call", {"name": name, "arguments": arguments}
        )["result"]

    def list_resources(self) -> list[dict[str, Any]]:
        return self._request("resources/list", {})["result"]["resources"]

    def list_prompts(self) -> list[dict[str, Any]]:
        return self._request("prompts/list", {})["result"]["prompts"]

    def close(self) -> None:
        if not self.session_id:
            return
        request = Request(
            self.url,
            method="DELETE",
            headers={"Mcp-Session-Id": self.session_id},
        )
        try:
            with urlopen(request, timeout=30) as response:
                print(f"[raw-mcp] DELETE /mcp -> HTTP {response.status}")
        except (HTTPError, URLError) as exc:
            print(f"[raw-mcp] close failed: {exc}")
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
            payload["id"] = self._next_id
            self._next_id += 1
        if params is not None:
            payload["params"] = params

        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        request = Request(
            self.url,
            data=json_bytes(payload),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                returned_session = response.headers.get("Mcp-Session-Id")
                if returned_session:
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
            f"[raw-mcp] {method} -> HTTP {status}, "
            f"{content_type.split(';', 1)[0]}, session={self.session_id}"
        )
        if notification or status == 202:
            return None
        if "text/event-stream" in content_type:
            return self._parse_sse(body)
        return json.loads(body)

    @staticmethod
    def _parse_sse(body: str) -> dict[str, Any]:
        data_lines = [
            line[5:].lstrip()
            for line in body.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            raise RuntimeError(f"SSE response has no data event: {body!r}")
        return json.loads("\n".join(data_lines))


def build_model_tools(
    tools: list[dict[str, Any]],
    server_name: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """把手写 Client 得到的 tools/list JSON 转成模型工具定义。"""

    namespace = normalize_namespace(server_name)
    model_tools: list[dict[str, Any]] = []
    name_map: dict[str, str] = {}
    for tool in tools:
        model_name = f"mcp__{namespace}__{tool['name']}"
        model_tools.append(
            {
                "name": model_name,
                "description": tool.get("description") or tool.get("title") or tool["name"],
                "input_schema": tool["inputSchema"],
            }
        )
        name_map[model_name] = tool["name"]
    return model_tools, name_map


def mcp_result_to_text(result: dict[str, Any]) -> str:
    """把 tools/call result 变成下一轮模型可读的文本。"""

    parts: list[str] = []
    structured = result.get("structuredContent")
    if structured is not None:
        parts.append(json.dumps(structured, ensure_ascii=False, default=str))
    for block in result.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
        else:
            parts.append(json.dumps(block, ensure_ascii=False, default=str))
    return "\n".join(parts) or "<empty MCP tool result>"


def build_system_prompt(
    initialize_result: dict[str, Any],
    server_name: str,
) -> str:
    server_info = initialize_result.get("serverInfo") or {}
    instructions = initialize_result.get("instructions") or (
        "Use the connected MCP server's tools when they are relevant."
    )
    return (
        "You are a small MCP learning agent.\n"
        f"Connected MCP server: {server_info.get('name', server_name)}\n"
        f"Server instructions: {instructions}\n"
        "Use the namespaced MCP tools when they help answer the user's request. "
        "After receiving tool results, answer the user in Chinese."
    )


async def inspect_server(url: str) -> None:
    """先验证真实 HTTP MCP Server，避免把连接问题误认为模型问题。"""

    client = RawHTTPMCPClient(url)
    try:
        initialize_result = await asyncio.to_thread(client.connect)
        print("initialize=", json.dumps(initialize_result, ensure_ascii=False, indent=2))
        tools = await asyncio.to_thread(client.list_tools)
        print("tools=", [tool["name"] for tool in tools])
        try:
            resources = await asyncio.to_thread(client.list_resources)
            print("resources=", [resource["uri"] for resource in resources])
        except Exception as exc:
            print("resources=<unavailable>", type(exc).__name__, exc)
        try:
            prompts = await asyncio.to_thread(client.list_prompts)
            print("prompts=", [prompt["name"] for prompt in prompts])
        except Exception as exc:
            print("prompts=<unavailable>", type(exc).__name__, exc)
    finally:
        await asyncio.to_thread(client.close)


async def run_agent(
    url: str,
    server_name: str,
    model: str | None,
    max_tokens: int,
) -> None:
    """运行 code.py 形状的模型循环，但 MCP 协议全部手写。"""

    if not model:
        raise RuntimeError(
            "agent 需要 MODEL_ID；请在 .env 中设置 MODEL_ID，或通过 --model 传入。"
        )

    mcp_client = RawHTTPMCPClient(url)
    model_client = AsyncAnthropic(base_url=os.getenv("ANTHROPIC_BASE_URL") or None)
    try:
        # 这些调用是真实 HTTP；只有模型选择工具的部分使用 Anthropic SDK。
        initialize_result = await asyncio.to_thread(mcp_client.connect)
        tool_defs = await asyncio.to_thread(mcp_client.list_tools)
        model_tools, name_map = build_model_tools(tool_defs, server_name)
        system = build_system_prompt(initialize_result, server_name)
        history: list[dict[str, Any]] = []

        print(f"Connected to HTTP MCP server: {url}")
        print("Model-visible tools:", ", ".join(name_map) or "<none>")
        print("输入自然语言问题；输入 q/exit 退出。\n")

        while True:
            try:
                query = input("mcp-agent-raw >> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if query.lower() in {"q", "exit"}:
                return
            if not query:
                continue

            history.append({"role": "user", "content": query})
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
                        print(f"[raw-mcp] tools/call {original_name}({block.input})")
                        try:
                            result = await asyncio.to_thread(
                                mcp_client.call_tool,
                                original_name,
                                dict(block.input or {}),
                            )
                            output = mcp_result_to_text(result)
                            is_error = bool(result.get("isError"))
                        except Exception as exc:
                            output = f"MCP call failed: {type(exc).__name__}: {exc}"
                            is_error = True
                        print(f"[raw-mcp] is_error={is_error}")

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
        await asyncio.to_thread(mcp_client.close)
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
        print("\nRaw MCP Agent stopped.")
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
