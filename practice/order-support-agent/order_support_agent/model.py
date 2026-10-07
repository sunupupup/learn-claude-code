"""DeepSeek Chat Completions 接入；阶段 1 使用非流式、非思考模式。"""

from copy import deepcopy
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings

API_URL = "https://api.deepseek.com/chat/completions"


class ModelError(Exception):
    """对用户安全的错误消息，不携带密钥或供应商原始响应体。"""


def validate_message(message: dict) -> dict:
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ModelError("模型返回了不支持的消息格式。")
    content = message.get("content")
    calls = message.get("tool_calls") or []
    if content is not None and not isinstance(content, str):
        raise ModelError("模型返回的正文格式无效。")
    if not isinstance(calls, list) or len(calls) > 8:
        raise ModelError("模型单次工具调用数量或格式无效。")
    seen = set()
    for call in calls:
        if not isinstance(call, dict):
            raise ModelError("模型工具调用格式无效。")
        call_id = call.get("id")
        function = call.get("function")
        if (not isinstance(call_id, str) or not call_id or call_id in seen
                or call.get("type") != "function" or not isinstance(function, dict)
                or not isinstance(function.get("name"), str)
                or not isinstance(function.get("arguments"), str)):
            raise ModelError("模型工具调用缺少有效标识或参数。")
        seen.add(call_id)
    if not calls and (not content or not content.strip()):
        raise ModelError("模型没有返回正文或工具调用。")
    # 不保存供应商额外字段；本阶段禁用思考模式，不需要 reasoning_content。
    result = {"role": "assistant", "content": content}
    if calls:
        result["tool_calls"] = deepcopy(calls)
    return result


class DeepSeekModel:
    def __init__(self, settings: Settings):
        self.settings = settings

    def complete_stream(self, messages: list[dict], tools: list[dict], on_delta) -> dict:
        """转发真实正文增量，但工具参数必须完整接收后才能进入执行层。"""
        payload = {
            "model": self.settings.model, "messages": messages, "tools": tools,
            "stream": True, "thinking": {"type": "disabled"}, "max_tokens": 2048,
        }
        request = Request(API_URL, data=json.dumps(payload, ensure_ascii=False).encode(),
                          headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.settings.api_key}, method="POST")
        try:
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                return read_stream(response, on_delta)
        except HTTPError as exc:
            raise ModelError(f"DeepSeek 请求失败（HTTP {exc.code}），请检查密钥、余额或稍后重试。") from None
        except (URLError, TimeoutError, OSError):
            raise ModelError("模型流连接中断或超时，本轮未完成，请重试。") from None

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        payload = {
            "model": self.settings.model, "messages": messages, "tools": tools,
            "stream": False, "thinking": {"type": "disabled"}, "max_tokens": 1024,
        }
        request = Request(
            API_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.settings.api_key},
            method="POST",
        )
        try:
            # 不自动重试模型请求，让循环预算与实际请求数一致。
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                body = json.load(response)
        except HTTPError as exc:
            hints = {401: "密钥无效", 402: "余额不足", 429: "请求频率受限"}
            raise ModelError(f"DeepSeek 请求失败（HTTP {exc.code}，{hints.get(exc.code, '请检查配置或稍后重试')}）。") from None
        except (URLError, TimeoutError, OSError):
            raise ModelError("DeepSeek 连接失败或超时，请检查网络后重试。") from None
        except (ValueError, UnicodeError):
            raise ModelError("DeepSeek 返回了无法解析的数据。") from None
        try:
            choice = body["choices"][0]
            if choice["finish_reason"] not in ("stop", "tool_calls"):
                raise ModelError("模型输出未完整结束，本轮不执行工具；请缩短问题后重试。")
            return validate_message(choice["message"])
        except (KeyError, IndexError, TypeError):
            raise ModelError("DeepSeek 响应缺少有效消息。") from None


def read_stream(response, on_delta) -> dict:
    content = ""
    calls = {}
    finish = None
    done = False
    try:
        for raw in response:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                done = True
                break
            chunk = json.loads(data)
            if not chunk.get("choices"):
                continue
            choice = chunk["choices"][0]
            delta = choice.get("delta", {})
            text = delta.get("content") or ""
            if text:
                content += text
                on_delta(text)
            for part in delta.get("tool_calls") or []:
                index = part["index"]
                if type(index) is not int or not 0 <= index < 8:
                    raise ModelError("模型工具调用数量或索引无效。")
                target = calls.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                if part.get("id"):
                    target["id"] = part["id"]
                function = part.get("function") or {}
                target["function"]["name"] += function.get("name") or ""
                target["function"]["arguments"] += function.get("arguments") or ""
            if choice.get("finish_reason"):
                finish = choice["finish_reason"]
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeError):
        raise ModelError("模型流格式异常，本轮不执行工具。") from None
    # 即使工具参数恰好是合法 JSON，流被截断也不能认为调用已经完成。
    if not done or finish not in ("stop", "tool_calls"):
        raise ModelError("模型输出中断或达到长度上限，本轮不执行工具。")
    message = {"role": "assistant", "content": content or None}
    if calls:
        message["tool_calls"] = [calls[index] for index in sorted(calls)]
    return validate_message(message)
