"""暴露给模型的只读知识检索 Tool。

Tool Calling（工具调用）的含义是：模型只提出“工具名 + 参数”，
真正的函数执行、用户身份绑定和错误处理仍由应用程序负责。
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .contracts import RetrievalResult, SearchKnowledgeInput, UserIdentity
from .vector_store import KnowledgeRetriever


class ToolExecutionError(RuntimeError):
    """工具执行失败；retryable 表示上层是否可以有限重试。"""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class ToolInputError(ToolExecutionError):
    """模型生成的参数不满足 Tool 契约，不应伪装成下游服务故障。"""


class SearchKnowledgeTool:
    """暴露给模型的只读知识检索 Tool。

    授权始终留在 retriever/vector store 路径中。Prompt 里写“请遵守权限”
    只是软约束，不能替代数据库过滤。
    """

    name = "search_knowledge"

    def __init__(
        self,
        retriever: KnowledgeRetriever,
        user: UserIdentity,
        default_top_k: int,
        score_threshold: float,
    ) -> None:
        self.retriever = retriever
        self.user = user
        self.default_top_k = default_top_k
        self.score_threshold = score_threshold

    @classmethod
    def schema(cls) -> dict[str, Any]:
        # 这个 Schema 会传给 LLM，帮助它生成可解析的参数；程序端仍必须再次校验。
        return {
            "type": "function",
            "name": cls.name,
            "description": (
                "Search the user's authorized knowledge base. Use this before answering "
                "questions about the local documents."
            ),
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["query", "top_k"],
                "additionalProperties": False,
            },
        }

    def execute(self, raw_arguments: dict[str, Any]) -> RetrievalResult:
        # 模型输出是不可信输入：先校验 query/top_k，再执行任何检索动作。
        try:
            arguments = SearchKnowledgeInput.model_validate(
                {"top_k": self.default_top_k, **raw_arguments}
            )
            matches = self.retriever.retrieve(
                # Tool 在构造时已经绑定当前用户，模型不能通过参数切换租户。
                query=arguments.query,
                user=self.user,
                top_k=arguments.top_k,
                score_threshold=self.score_threshold,
            )
            return RetrievalResult(
                # status 是检索层事实：数组有结果才是 matched，不是 LLM 的答案判断。
                matches=matches,
                retrieval_status="matched" if matches else "no_relevant_match",
            )
        except ValidationError as exc:
            # 参数错误是协议问题，重试同一个坏参数没有意义。
            raise ToolInputError("invalid knowledge search arguments", retryable=False) from exc
        except Exception as exc:
            # A read-only Qdrant/Embedding failure is potentially transient, but
            # the Agent loop still owns the retry budget and user-facing message.
            raise ToolExecutionError("knowledge search failed", retryable=True) from exc

    @staticmethod
    def serialize_result(result: RetrievalResult) -> str:
        # Tool result 是数据而不是指令；文档正文可能包含 Prompt Injection，
        # 因此 final prompt 必须明确要求模型把它当作不可信证据。
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
