"""跨模块共享的数据契约。

这里的模型不是“为了好看”的类型声明，而是 Harness 的边界：
外部输入、模型输出和状态流转都先变成可校验的数据，再进入下一步。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    # extra=forbid 可以拒绝模型偷偷多塞的字段，避免契约漂移；
    # str_strip_whitespace 则统一处理用户/模型常见的首尾空格。
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UserIdentity(StrictModel):
    """一次请求经过认证后，传给检索层的最小身份信息。

    这个对象在真实服务中应来自已验证的登录凭证，而不是信任前端任意
    传入的字符串。groups 用于演示文档级 ACL（访问控制列表）。
    """

    user_id: str = Field(min_length=1, max_length=200)
    tenant_id: str = Field(min_length=1, max_length=200)
    groups: list[str] = Field(min_length=1, max_length=50)

    @field_validator("groups")
    @classmethod
    def unique_groups(cls, value: list[str]) -> list[str]:
        # 去空、去重并保持顺序，避免同一个用户身份生成不稳定的过滤器。
        cleaned = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if not cleaned:
            raise ValueError("groups must contain at least one non-empty group")
        return cleaned


class DocumentManifest(StrictModel):
    """文档入库清单中的一行，也是权限元数据的来源。

    权限放在 manifest，而不是 Markdown 正文或 Prompt 中，便于程序在
    检索前执行确定性的授权判断。
    """

    document_id: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=300)
    tenant_id: str = Field(min_length=1, max_length=200)
    allowed_groups: list[str] = Field(min_length=1, max_length=50)

    @field_validator("path")
    @classmethod
    def relative_path_only(cls, value: str) -> str:
        # 只允许相对 Markdown 路径；真正的目录逃逸检查还会在 Ingestor
        # 中对 resolve() 后的路径再做一次 containment 检查。
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("manifest path must stay relative to the data directory")
        if path.suffix.lower() != ".md":
            raise ValueError("manifest path must point to a Markdown file")
        return path.as_posix()

    @field_validator("allowed_groups")
    @classmethod
    def non_empty_groups(cls, value: list[str]) -> list[str]:
        # 空权限列表的语义容易被误解成“公开”，因此这里直接拒绝。
        cleaned = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if not cleaned:
            raise ValueError("allowed_groups must contain at least one group")
        return cleaned


class DocumentChunk(StrictModel):
    """切分后的最小知识单元。

    tenant_id 和 allowed_groups 会被复制到向量库 payload；这样查询时不
    需要先把所有向量拿回应用层再过滤，未授权内容不会影响 top-k。
    """

    chunk_id: str
    document_id: str
    title: str
    source_path: str
    tenant_id: str
    allowed_groups: list[str]
    heading: str
    text: str = Field(min_length=1)
    content_hash: str = Field(min_length=64, max_length=64)


class RetrievedChunk(StrictModel):
    """已经通过权限过滤和相似度筛选、允许进入模型上下文的候选。"""

    chunk_id: str
    title: str
    heading: str
    text: str
    score: float


class RetrievalResult(StrictModel):
    """Tool 返回的检索结果。

    retrieval_status 只回答“检索层有没有可用候选”，不回答“候选是否
    真正支撑了用户问题”；后一个判断属于最终模型输出的 answerable。
    """

    matches: list[RetrievedChunk]
    retrieval_status: Literal["matched", "no_relevant_match"]

    @model_validator(mode="after")
    def status_matches_payload(self) -> "RetrievalResult":
        # 状态由结果数组决定，不能让模型/调用方传出自相矛盾的组合。
        expected = "matched" if self.matches else "no_relevant_match"
        if self.retrieval_status != expected:
            raise ValueError("retrieval_status must match whether matches is empty")
        return self


class SearchKnowledgeInput(StrictModel):
    """search_knowledge 的输入边界，模型生成的参数也必须经过它。"""

    query: str = Field(min_length=1, max_length=2_000)
    top_k: int = Field(default=3, ge=1, le=10)


class SourceRef(StrictModel):
    """最终回答中的来源引用，只允许引用本次检索返回的 chunk。"""

    chunk_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)


class FinalAnswer(StrictModel):
    """唯一允许暴露给 CLI 的模型回答契约。

    模型可以生成这个候选对象，但只有通过 output_validation.py 的二次
    校验后，Harness 才把它当作一次成功 Run 的结果。
    """

    answerable: bool
    answer: str = Field(min_length=1, max_length=8_000)
    sources: list[SourceRef] = Field(max_length=20)

    @model_validator(mode="after")
    def source_consistency(self) -> "FinalAnswer":
        # 可回答时必须有来源；不可回答时不带来源，避免给用户造成“有依据”的错觉。
        if self.answerable and not self.sources:
            raise ValueError("an answerable response must cite at least one source")
        if not self.answerable and self.sources:
            raise ValueError("an unanswerable response must not cite sources")
        return self


class RunStatus(StrEnum):
    """一次 Run 的显式状态；终端状态由 Harness 写入，不由 LLM 自报。"""

    CREATED = "created"
    AWAITING_TOOL = "awaiting_tool"
    RETRIEVED = "retrieved"
    GENERATING = "generating"
    COMPLETED = "completed"
    NO_EVIDENCE = "no_evidence"
    FAILED = "failed"


@dataclass
class RunState:
    """Harness 持有的确定性运行状态。

    对话文本是给模型的上下文，RunState 是给程序做预算、审计和恢复
    判断的状态，两者不能混为一谈。
    """

    run_id: str
    user: UserIdentity
    question: str
    status: RunStatus = RunStatus.CREATED
    turns: int = 0
    tool_calls: int = 0
    retrieval_called: bool = False
    repair_attempts: int = 0
    retrieved_chunk_ids: list[str] = field(default_factory=list)
    error_category: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    def transition(self, status: RunStatus) -> None:
        # 终端状态统一记录结束时间，便于后续计算延迟和排查卡住的 Run。
        self.status = status
        if status in {RunStatus.COMPLETED, RunStatus.NO_EVIDENCE, RunStatus.FAILED}:
            self.finished_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        # dataclasses.asdict 不会自动把 Enum/Pydantic 转成 JSON，手动规范化。
        data = asdict(self)
        data["user"] = self.user.model_dump(mode="json")
        data["status"] = self.status.value
        data["created_at"] = self.created_at.isoformat()
        data["finished_at"] = self.finished_at.isoformat() if self.finished_at else None
        return data


@dataclass(frozen=True)
class ToolCallRequest:
    """从供应商响应中归一化出来的 Tool Call。"""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelResponse:
    """模型适配器对不同供应商响应的最小统一表示。"""

    kind: Literal["tool_call", "final_text"]
    tool_calls: tuple[ToolCallRequest, ...] = ()
    text: str = ""
    response_id: str | None = None


@dataclass(frozen=True)
class AgentRunResult:
    """一次 Run 的用户可见结果、结构化答案和安全 Trace。"""

    state: RunState
    user_message: str
    final_answer: FinalAnswer | None
    trace: list[dict[str, Any]]
