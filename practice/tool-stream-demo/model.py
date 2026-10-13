"""只访问官方固定地址，不记录请求头、密钥或服务端原始错误正文。"""
import json
import os
from pathlib import Path
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent
TOOL = {"type": "function", "function": {
    "name": "demo_steps", "description": "安全的三步模拟测试，持续报告进度。",
    "parameters": {"type": "object", "properties": {
        "fail": {"type": "boolean", "description": "是否模拟失败"}},
        "required": ["fail"], "additionalProperties": False}}}


def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def chat(messages, emit, first=False):
    load_env()
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY（.env 或环境变量）")
    body = {"model": os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
            "messages": messages, "stream": True, "max_tokens": 512,
            "thinking": {"type": "disabled"}, "tools": [TOOL],
            "tool_choice": {"type": "function", "function": {"name": "demo_steps"}}
            if first else "none"}
    request = urllib.request.Request("https://api.deepseek.com/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json",
                                               "Authorization": "Bearer " + key})
    message = {"role": "assistant", "content": ""}
    calls = {}
    finish = None
    done = False
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            for raw in response:
                line = raw.decode().strip()
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    done = True
                    break
                chunk = json.loads(data)
                for choice in chunk.get("choices", []):
                    finish = choice.get("finish_reason") or finish
                    delta = choice.get("delta", {})
                    content = delta.get("content") or ""
                    if content:
                        message["content"] += content
                        emit("message_update", delta=content)
                    # 模型参数也是分片的；只在接收完整后解析和执行，绝不执行半截 JSON。
                    for part in delta.get("tool_calls", []):
                        call = calls.setdefault(part["index"], {"id": "", "type": "function",
                            "function": {"name": "", "arguments": ""}})
                        call["id"] += part.get("id") or ""
                        for field in ("name", "arguments"):
                            call["function"][field] += part.get("function", {}).get(field) or ""
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"DeepSeek HTTP {exc.code}；指定模型未切换") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("DeepSeek 网络错误或超时；未重试") from None
    if not done or finish not in ("stop", "tool_calls"):
        raise RuntimeError(f"模型流未完整结束（finish_reason={finish}）")
    if calls:
        message["tool_calls"] = [calls[i] for i in sorted(calls)]
    return message
