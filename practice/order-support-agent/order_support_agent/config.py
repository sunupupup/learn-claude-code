"""读取本地配置；程序的可信身份与模型生成的参数分开。"""

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_USER_ID = "demo-user-001"


@dataclass(frozen=True)
class Settings:
    # repr 不显示密钥，避免调试打印配置时意外泄露。
    api_key: str = field(repr=False)
    model: str = "deepseek-flash"
    max_model_calls: int = 6
    timeout_seconds: float = 30.0


def load_settings(env_path: Path | None = None) -> Settings:
    path = env_path if env_path is not None else PROJECT_ROOT / ".env"
    local = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, value = line.partition("=")
            if not separator:
                raise ValueError(".env 格式错误：请使用 NAME=value。")
            # 只支持简单键值，不执行变量展开或任何脚本。
            local[name.strip()] = value.strip().strip("\"'")
    key = os.environ.get("DEEPSEEK_API_KEY", local.get("DEEPSEEK_API_KEY", "")).strip()
    model = os.environ.get("DEEPSEEK_MODEL", local.get("DEEPSEEK_MODEL", "deepseek-flash")).strip()
    if not key:
        raise ValueError("缺少 DEEPSEEK_API_KEY，请在项目 .env 或环境变量中设置。")
    if not model:
        raise ValueError("DEEPSEEK_MODEL 不能为空。")
    return Settings(api_key=key, model=model)
