"""控制模型—工具循环；context 保存历史，tools 负责实际查询。"""

from dataclasses import dataclass
from typing import Callable, Protocol

from .context import Context
from .model import ModelError, validate_message
from .tools import TOOL_DEFINITIONS, dispatch_tool


class Model(Protocol):
    def complete(self, messages: list[dict], tools: list[dict]) -> dict: ...


@dataclass(frozen=True)
class TurnResult:
    status: str
    text: str
    model_calls: int


def run_turn(user_input: str, *, context: Context, model: Model, user_id: str,
             orders: list[dict], max_model_calls: int = 6,
             log: Callable = lambda event, data: None,
             tool_definitions: list[dict] | None = None,
             executor: Callable | None = None,
             on_delta: Callable | None = None) -> TurnResult:
    if max_model_calls < 1:
        raise ValueError("模型调用上限必须至少为 1。")
    if not user_input.strip():
        return TurnResult("empty_input", "请输入订单查询问题。", 0)
    context.add_user(user_input)
    definitions = tool_definitions if tool_definitions is not None else TOOL_DEFINITIONS
    for number in range(1, max_model_calls + 1):
        messages = context.snapshot()
        log("model_request", {"iteration": number, "messages": messages, "tools": definitions})
        try:
            if on_delta is not None:
                reply = validate_message(model.complete_stream(messages, definitions, on_delta))
            else:
                reply = validate_message(model.complete(messages, definitions))
        except ModelError as exc:
            # 错误提示属于程序状态，不伪装成模型生成的回答写入历史。
            log("model_error", {"iteration": number, "message": str(exc)})
            return TurnResult("model_error", str(exc), number)
        log("model_response", {"iteration": number, "message": reply})
        context.add_assistant(reply)
        calls = reply.get("tool_calls", [])
        if not calls:
            return TurnResult("completed", reply["content"], number)
        pause = None
        for call in calls:
            log("tool_start", {"iteration": number, "tool_call_id": call["id"], "tool": call["function"]["name"], "arguments": call["function"]["arguments"]})
            # 一次响应可能含多个调用。进入选择/确认后，其余调用不再执行，但仍补齐结果配对。
            if pause:
                result = {"status": "error", "code": "WAITING_USER", "message": "请先完成当前选择或确认。"}
            else:
                result = executor(call) if executor else dispatch_tool(call, user_id=user_id, orders=orders)
            context.add_tool_result(call["id"], result)
            log("tool_result", {"iteration": number, "tool_call_id": call["id"],
                                "tool": call["function"]["name"], "result": result})
            if result.get("status") in ("waiting_selection", "waiting_approval"):
                pause = result["status"]
        if pause:
            return TurnResult(pause, "请在卡片中完成操作。", number)
    # 最后一次请求产生的只读调用仍完成并配对；绝不额外请求模型做总结。
    return TurnResult("budget_exhausted", "已达到本轮模型调用上限，暂时无法完成回答，请缩小问题范围后重试。", max_model_calls)
