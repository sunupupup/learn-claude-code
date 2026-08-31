"""离线 Eval 入口。

这里使用确定性 fake 来检查轨迹、权限和来源契约；它不衡量真实 Embedding
的语义召回质量，也不应被误读成线上模型效果基准。
"""

from __future__ import annotations

import json
from pathlib import Path

from rag_agent_demo.agent import AgentRunner
from rag_agent_demo.config import Settings
from rag_agent_demo.contracts import (
    ModelResponse,
    RetrievedChunk,
    RunStatus,
    ToolCallRequest,
    UserIdentity,
)
from rag_agent_demo.model import ScriptedModel
from rag_agent_demo.tools import SearchKnowledgeTool


class FakeEvalRetriever:
    """用于契约/轨迹评测的确定性检索替身。

    它不假装测量真实 Embedding 质量，而是让离线套件在不调用外部服务的
    情况下检查 Harness、ACL、无证据和来源契约。
    """

    def retrieve(self, query, user, top_k, score_threshold):
        # 先模拟租户隔离，再模拟群组授权，顺序对应真实 Qdrant pre-filter。
        if user.tenant_id != "demo":
            return []
        if "退款" in query and "support" in user.groups:
            return [
                RetrievedChunk(
                    chunk_id="support-faq-001",
                    title="客服 FAQ",
                    heading="退款期限",
                    text="标准商品支持签收后 30 天内申请退款。",
                    score=0.95,
                )
            ]
        keywords = {
            "RAG": ("rag-principles-001", "RAG 原理", "RAG 是在生成前取回外部证据。"),
            "Agent Loop": ("agent-basics-002", "Agent 基础", "Agent Loop 会执行工具并判断是否停止。"),
            "Tool": ("tool-security-001", "Tool 与权限", "模型提出 Tool 请求，应用程序负责执行。"),
            "Eval": ("evaluation-001", "Agent 评测", "Eval Set 是可重复运行的代表性用例集合。"),
        }
        # The real manifest grants the evaluation document to both groups.
        if not {"engineering", "qa"}.intersection(user.groups):
            return []
        for keyword, (chunk_id, title, text) in keywords.items():
            if keyword.lower() in query.lower():
                return [
                    RetrievedChunk(
                        chunk_id=chunk_id,
                        title=title,
                        heading="demo",
                        text=text,
                        score=0.92,
                    )
                ]
        return []


def run_case(case: dict) -> tuple[bool, str]:
    # 每条 case 都构造一条可复现的模型→Tool→结果→模型轨迹。
    user = UserIdentity(
        user_id=f"eval-{case['id']}",
        tenant_id=case.get("tenant", "demo"),
        groups=case.get("groups", ["engineering"]),
    )
    retriever = FakeEvalRetriever()
    tool_call = ModelResponse(
        kind="tool_call",
        tool_calls=(
            ToolCallRequest(
                call_id=f"call-{case['id']}",
                name="search_knowledge",
                arguments={"query": case["question"], "top_k": 3},
            ),
        ),
        response_id=f"response-{case['id']}-1",
    )
    fake_match = FakeEvalRetriever().retrieve(
        case["question"], user, top_k=3, score_threshold=0.7
    )
    # 有候选的 case 使用合法最终 JSON；不同 expected 值检查不同性质：
    # 有的看最终状态，有的看工具次数，有的看来源完整性。
    expected_answerable = case["expected"] in {
        "answerable",
        "one_tool_call",
        "known_source_only",
    }
    scripted_responses = [tool_call]
    if fake_match:
        scripted_responses.append(
            ModelResponse(
                kind="final_text",
                text=json.dumps(
                    {
                        "answerable": expected_answerable,
                        "answer": fake_match[0].text,
                        "sources": [
                            {
                                "chunk_id": fake_match[0].chunk_id,
                                "title": fake_match[0].title,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                response_id=f"response-{case['id']}-2",
            )
        )

    settings = Settings(
        project_root=Path(__file__).resolve().parents[1],
        data_dir=Path(__file__).resolve().parents[1] / "data",
        manifest_path=Path(__file__).resolve().parents[1] / "data/manifest.json",
        max_turns=3,
        max_tool_calls=1,
        max_repair_attempts=1,
    )

    def factory(current_user):
        return SearchKnowledgeTool(
            retriever=retriever,
            user=current_user,
            default_top_k=3,
            score_threshold=0.7,
        )

    result = AgentRunner(ScriptedModel(scripted_responses), factory, settings).run(
        case["question"], user
    )
    expected = case["expected"]
    if expected == "answerable":
        passed = result.state.status == RunStatus.COMPLETED and result.final_answer is not None
    elif expected == "no_evidence":
        passed = result.state.status == RunStatus.NO_EVIDENCE
    elif expected == "one_tool_call":
        passed = result.state.tool_calls == 1
    elif expected == "known_source_only":
        passed = result.final_answer is not None and all(
            source.chunk_id in result.state.retrieved_chunk_ids
            for source in result.final_answer.sources
        )
    else:
        passed = False
    return passed, result.state.status.value

def main() -> int:
    # Eval 集太小会让“全绿”失去意义，因此至少要求 10 条用例。
    cases_path = Path(__file__).with_name("cases.json")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if len(cases) < 10:
        raise SystemExit("eval set must contain at least 10 cases")

    failures: list[str] = []
    for case in cases:
        passed, status = run_case(case)
        print(f"{'PASS' if passed else 'FAIL'} {case['id']}: {status}")
        if not passed:
            failures.append(case["id"])

    if failures:
        print(f"Failed cases: {', '.join(failures)}")
        return 1
    print(f"Passed {len(cases)} offline D1 contract/evidence cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
