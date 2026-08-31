"""运行时配置。

配置集中在这里，避免 top-k、阈值、重试和预算散落在各个模块里。
真实部署时通常由环境变量或配置中心注入，密钥不应写进源码。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    # 环境变量本质上都是字符串；在启动阶段转换，错误可以尽早暴露。
    value = os.getenv(name)
    return default if value is None else int(value)


def _env_float(name: str, default: float) -> float:
    # 相似度阈值、超时等需要浮点数，不能把字符串一路传到业务逻辑。
    value = os.getenv(name)
    return default if value is None else float(value)


def _env_bool(name: str, default: bool) -> bool:
    # 不直接使用 bool("false")，因为任何非空字符串都会变成 True。
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime configuration with safe, explicit defaults for the demo.

    这里的字段同时描述“外部服务怎么连”和“Harness 允许走多远”。
    后者是安全边界，不应由模型自己决定。
    """

    project_root: Path
    data_dir: Path
    manifest_path: Path
    # 向量数据库连接信息。API Key 只从环境变量读取。
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "rag_agent_demo"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    # 模型名称可配置；业务代码只依赖 ModelClient，不绑定具体供应商模型。
    model_name: str = "gpt-5.5"
    embedding_model: str = "text-embedding-3-small"
    # RAG 召回参数：top-k 控制候选数量，阈值先过滤低相似度结果。
    top_k: int = 3
    score_threshold: float = 0.70
    embedding_batch_size: int = 64
    # Harness 预算：防止模型无限循环、无限修复或无限消耗外部服务。
    max_turns: int = 3
    max_tool_calls: int = 1
    max_repair_attempts: int = 1
    rebuild_collection_on_start: bool = True
    request_timeout_s: float = 60.0
    qdrant_timeout_s: float = 30.0

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "Settings":
        # 默认根目录取包的上两级：projects/rag-agent-demo。
        # 这样从任意当前工作目录启动时，仍能找到 data/manifest.json。
        root = (project_root or Path(__file__).resolve().parents[1]).resolve()
        data_dir = root / "data"
        return cls(
            project_root=root,
            data_dir=data_dir,
            manifest_path=data_dir / "manifest.json",
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            qdrant_collection=os.getenv("QDRANT_COLLECTION", "rag_agent_demo"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv("OPENAI_BASE_URL"),
            model_name=os.getenv("MODEL_NAME", "gpt-5.5"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            top_k=_env_int("RAG_TOP_K", 3),
            score_threshold=_env_float("RAG_SCORE_THRESHOLD", 0.70),
            embedding_batch_size=_env_int("EMBEDDING_BATCH_SIZE", 64),
            max_turns=_env_int("AGENT_MAX_TURNS", 3),
            max_tool_calls=_env_int("AGENT_MAX_TOOL_CALLS", 1),
            max_repair_attempts=_env_int("AGENT_MAX_REPAIR_ATTEMPTS", 1),
            rebuild_collection_on_start=_env_bool("REBUILD_INDEX_ON_START", True),
            request_timeout_s=_env_float("MODEL_TIMEOUT_SECONDS", 60.0),
            qdrant_timeout_s=_env_float("QDRANT_TIMEOUT_SECONDS", 30.0),
        )

    def validate(self) -> None:
        # 先做本地 fail-fast 校验，再连接 OpenAI/Qdrant，避免带着坏配置发请求。
        if self.top_k < 1:
            raise ValueError("RAG_TOP_K must be >= 1")
        if not 0.0 <= self.score_threshold <= 1.0:
            raise ValueError("RAG_SCORE_THRESHOLD must be between 0 and 1 for cosine similarity")
        if self.max_tool_calls < 1:
            raise ValueError("AGENT_MAX_TOOL_CALLS must be >= 1")
        if self.max_turns < 1:
            raise ValueError("AGENT_MAX_TURNS must be >= 1")
        if self.max_repair_attempts < 0:
            raise ValueError("AGENT_MAX_REPAIR_ATTEMPTS must be >= 0")
        if self.embedding_batch_size < 1:
            raise ValueError("EMBEDDING_BATCH_SIZE must be >= 1")
        if self.request_timeout_s <= 0:
            raise ValueError("MODEL_TIMEOUT_SECONDS must be > 0")
        if self.qdrant_timeout_s <= 0:
            raise ValueError("QDRANT_TIMEOUT_SECONDS must be > 0")
