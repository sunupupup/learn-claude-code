"""模型供应商适配器。

本模块把 OpenAI Responses API 的具体 response item 归一化成项目内部的
ModelResponse，避免 Harness 到处判断供应商 SDK 的对象结构。
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from .config import Settings
from .contracts import ModelResponse, ToolCallRequest


class ModelCallError(RuntimeError):
    """模型调用错误；retryable 只给可恢复的网络/限流类故障。"""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class ModelClient(Protocol):
    """Harness 依赖的最小模型接口；真实模型和测试模型都实现它。"""

    def respond(
        self,
        *,
        input: str | list[dict[str, Any]],
        instructions: str,
        tools: list[dict[str, Any]],
        tool_choice: Any = None,
        previous_response_id: str | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> ModelResponse:
        ...


class OpenAIResponsesModel:
    """真实 OpenAI Responses API 适配器。

    适配器把供应商 response item 归一化为小型内部契约，让 Harness 更容易
    阅读、测试和替换模型供应商。
    """

    def __init__(self, client: Any, model_name: str, request_timeout_s: float = 60.0) -> None:
        self.client = client
        self.model_name = model_name
        self.request_timeout_s = request_timeout_s

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAIResponsesModel":
        # 延迟 import 让没有安装 openai 的离线测试仍能运行。
        from openai import OpenAI

        kwargs: dict[str, Any] = {
            "api_key": settings.openai_api_key,
            "timeout": settings.request_timeout_s,
        }
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return cls(OpenAI(**kwargs), settings.model_name, settings.request_timeout_s)

    def respond(
        self,
        *,
        input: str | list[dict[str, Any]],
        instructions: str,
        tools: list[dict[str, Any]],
        tool_choice: Any = None,
        previous_response_id: str | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> ModelResponse:
        # 先组装一份清晰的 wire request：后续的 tool_choice、续接 response
        # 和 JSON Schema 都是模型调用协议，而不是业务层的隐式魔法。
        request: dict[str, Any] = {
            "model": self.model_name,
            "input": input,
            "instructions": instructions,
            "tools": tools,
        }
        if tool_choice is not None:
            request["tool_choice"] = tool_choice
        if previous_response_id is not None:
            request["previous_response_id"] = previous_response_id
        if output_schema is not None:
            # Structured Output 不是只在 Prompt 里说“请输出 JSON”，而是把
            # JSON Schema 交给 SDK/API；返回后仍需做业务级校验。
            request["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "final_answer",
                    "schema": output_schema,
                    "strict": True,
                }
            }

        try:
            # 这是唯一真正触发外部 LLM 请求的边界。
            response = self.client.responses.create(**request)
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            retryable = status_code in {408, 409, 429, 500, 502, 503, 504} or isinstance(
                exc, (TimeoutError, ConnectionError)
            )
            raise ModelCallError("model request failed", retryable=retryable) from exc

        tool_calls: list[ToolCallRequest] = []
        for item in getattr(response, "output", []):
            # Responses API 的 function_call 是模型提出的动作，尚未代表工具已执行。
            if getattr(item, "type", None) != "function_call":
                continue
            try:
                # SDK 给出的 arguments 仍是一段 JSON 文本，需要转成 dict。
                arguments = json.loads(item.arguments)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ModelCallError("model returned invalid tool arguments") from exc
            if not isinstance(arguments, dict):
                raise ModelCallError("tool arguments must be a JSON object")
            tool_calls.append(
                ToolCallRequest(
                    call_id=str(item.call_id),
                    name=str(item.name),
                    arguments=arguments,
                )
            )

        if tool_calls:
            # 有 function_call 就交给 Harness 执行；不能同时把空 output_text 当最终答案。
            return ModelResponse(
                kind="tool_call",
                tool_calls=tuple(tool_calls),
                response_id=str(getattr(response, "id", "")) or None,
            )

        # 没有 function_call 时才读取最终文本；Harness 还会继续校验其 JSON/业务语义。
        text = str(getattr(response, "output_text", "") or "").strip()
        if not text:
            raise ModelCallError("model returned neither a tool call nor final text")
        return ModelResponse(
            kind="final_text",
            text=text,
            response_id=str(getattr(response, "id", "")) or None,
        )


class ScriptedModel:
    """确定性测试替身，生产 CLI 永远不会使用它。"""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def respond(
        self,
        *,
        input: str | list[dict[str, Any]],
        instructions: str,
        tools: list[dict[str, Any]],
        tool_choice: Any = None,
        previous_response_id: str | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> ModelResponse:
        # 记录请求形状，让测试可以断言 Tool Calling 和 continuation 协议。
        self.calls.append(
            {
                "input": input,
                "instructions": instructions,
                "tools": tools,
                "tool_choice": tool_choice,
                "previous_response_id": previous_response_id,
                "output_schema": output_schema,
            }
        )
        if not self._responses:
            # 队列耗尽说明测试没有预先设计好完整的 Agent 轨迹。
            raise ModelCallError("scripted model has no response left")
        return self._responses.pop(0)
