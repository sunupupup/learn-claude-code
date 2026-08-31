"""最终模型输出的运行时校验。

Structured Output 能提高格式遵循率，但“格式正确”不等于“答案有依据”。
这里再做来源白名单、证据状态和业务规则校验，采用 fail-closed 策略。
"""

from __future__ import annotations

import json
from typing import Iterable

from .contracts import FinalAnswer


class OutputValidationError(ValueError):
    """模型最终输出不能安全进入用户界面时抛出。"""

    pass


def validate_final_output(
    raw_text: str,
    *,
    allowed_source_ids: Iterable[str],
    retrieval_status: str,
) -> FinalAnswer:
    """对格式错误、无依据或越权来源的最终输出 fail closed。"""

    try:
        # 第一道：文本必须是完整 JSON，而不是 JSON Markdown 或自然语言混排。
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise OutputValidationError("final output is not valid JSON") from exc

    try:
        # 第二道：字段、类型、必填项和 answerable/source 关系由 Pydantic 检查。
        answer = FinalAnswer.model_validate(payload)
    except Exception as exc:
        raise OutputValidationError("final output does not match FinalAnswer schema") from exc

    # 第三道：模型只能引用本次检索拿到的 chunk，不能凭空编造 source_id。
    allowed = set(allowed_source_ids)
    unknown_sources = {source.chunk_id for source in answer.sources} - allowed
    if unknown_sources:
        raise OutputValidationError("final output cites a chunk outside this retrieval")

    # 检索为空时，任何“有答案”的模型输出都拒绝，避免模型绕过 no_evidence 分支。
    if retrieval_status != "matched" and answer.answerable:
        raise OutputValidationError("answerable output is forbidden without matched evidence")

    return answer
