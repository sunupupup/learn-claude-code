"""仅在 --debug 时打印学习用事件；不记录 HTTP 头或整个配置对象。"""

import json
import re
import sys


class DebugLogger:
    def __init__(self, enabled: bool = False, secrets: tuple[str, ...] = ()):
        self.enabled = enabled
        self.secrets = tuple(value for value in secrets if value)

    def __call__(self, event: str, data: dict) -> None:
        if not self.enabled:
            return
        text = json.dumps({"event": event, **data}, ensure_ascii=False)
        # 替换已知密钥及常见密钥形式，包括用户误贴在消息中的情况。
        for secret in self.secrets:
            text = text.replace(secret, "[REDACTED]")
        text = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", text)
        print(text, file=sys.stderr)
