"""最小结构化 Trace。

Trace（追踪）用于还原一次 Run 的事件因果链；它不是把所有 Prompt、正文
和 Secret 原样写进日志。生产环境通常会接 OpenTelemetry 或内部观测平台。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TraceEvent:
    """一条带 Run 关联 ID 和 UTC 时间的结构化事件。"""

    name: str
    run_id: str
    at: str
    attributes: dict[str, Any] = field(default_factory=dict)


class TraceCollector:
    """进程内 Trace 收集器；生产环境应安全地导出 Span/Metric。"""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.events: list[TraceEvent] = []

    def record(self, name: str, **attributes: Any) -> None:
        # 默认只记录状态、ID、数量等安全摘要，避免泄漏完整文档正文。
        self.events.append(
            TraceEvent(
                name=name,
                run_id=self.run_id,
                at=datetime.now(timezone.utc).isoformat(),
                attributes=attributes,
            )
        )

    def as_dicts(self) -> list[dict[str, Any]]:
        # CLI --trace 和测试都使用普通 dict，避免暴露内部 dataclass 对象。
        return [asdict(event) for event in self.events]
