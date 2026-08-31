"""Agent Loop 的行为测试。

这些测试不验证某个模型“聪不聪明”，而验证 Harness 是否守住
检索前置、调用次数、无证据、修复和最终输出这些确定性边界。
"""

from __future__ import annotations

import json
import unittest
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


class FakeRetriever:
    """只返回预设结果的替身，用来隔离向量检索质量。"""

    def __init__(self, matches: list[RetrievedChunk]) -> None:
        self.matches = matches
        self.calls = 0

    def retrieve(self, query, user, top_k, score_threshold):
        self.calls += 1
        return self.matches


def make_settings() -> Settings:
    # 测试只关心 Run 预算，不需要 API Key、Qdrant 或真实模型。
    root = Path(__file__).resolve().parents[1]
    return Settings(
        project_root=root,
        data_dir=root / "data",
        manifest_path=root / "data/manifest.json",
        max_turns=3,
        max_tool_calls=1,
        max_repair_attempts=1,
    )


def make_tool_factory(retriever: FakeRetriever):
    def factory(user: UserIdentity) -> SearchKnowledgeTool:
        return SearchKnowledgeTool(retriever, user, default_top_k=3, score_threshold=0.7)

    return factory


class AgentLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        # 公共 fixture：一个已授权用户、一个候选 chunk 和两阶段模型响应。
        self.user = UserIdentity(user_id="u-1", tenant_id="demo", groups=["engineering"])
        self.match = RetrievedChunk(
            chunk_id="doc-001",
            title="RAG",
            heading="检索",
            text="RAG 先检索证据再生成回答。",
            score=0.9,
        )
        self.tool_call = ModelResponse(
            kind="tool_call",
            tool_calls=(
                ToolCallRequest(
                    call_id="call-1",
                    name="search_knowledge",
                    arguments={"query": "RAG", "top_k": 3},
                ),
            ),
            response_id="response-1",
        )
        self.final = ModelResponse(
            kind="final_text",
            text=json.dumps(
                {
                    "answerable": True,
                    "answer": "RAG 先检索证据再生成回答。",
                    "sources": [{"chunk_id": "doc-001", "title": "RAG"}],
                }
            ),
            response_id="response-2",
        )

    def test_success_is_tool_call_then_valid_final_output(self) -> None:
        # 成功路径必须是：第一次 Tool Call，检索一次，第二次合法 JSON。
        retriever = FakeRetriever([self.match])
        runner = AgentRunner(
            ScriptedModel([self.tool_call, self.final]),
            make_tool_factory(retriever),
            make_settings(),
        )

        result = runner.run("什么是 RAG？", self.user)

        self.assertEqual(result.state.status, RunStatus.COMPLETED)
        self.assertEqual(retriever.calls, 1)
        self.assertEqual(result.final_answer.sources[0].chunk_id, "doc-001")

    def test_no_evidence_is_a_normal_terminal_state_without_final_model_call(self) -> None:
        # 空检索是正常业务终态，并且不应再调用模型让它凭常识补答案。
        retriever = FakeRetriever([])
        model = ScriptedModel([self.tool_call])
        runner = AgentRunner(model, make_tool_factory(retriever), make_settings())

        result = runner.run("不存在的问题", self.user)

        self.assertEqual(result.state.status, RunStatus.NO_EVIDENCE)
        self.assertEqual(len(model.calls), 1)
        self.assertFalse(result.final_answer.answerable)

    def test_direct_text_is_repaired_once_before_retrieval(self) -> None:
        # Prompt 只是软约束；Harness 允许一次修复，但不会接受未检索文本。
        retriever = FakeRetriever([self.match])
        direct_text = ModelResponse(kind="final_text", text="我直接回答", response_id="bad")
        runner = AgentRunner(
            ScriptedModel([direct_text, self.tool_call, self.final]),
            make_tool_factory(retriever),
            make_settings(),
        )

        result = runner.run("什么是 RAG？", self.user)

        self.assertEqual(result.state.status, RunStatus.COMPLETED)
        self.assertEqual(result.state.repair_attempts, 1)

    def test_second_tool_call_is_rejected(self) -> None:
        # D1 只允许一个检索 Tool，重复工具轨迹必须 fail closed。
        retriever = FakeRetriever([self.match])
        runner = AgentRunner(
            ScriptedModel([self.tool_call, self.tool_call]),
            make_tool_factory(retriever),
            make_settings(),
        )

        result = runner.run("什么是 RAG？", self.user)

        self.assertEqual(result.state.status, RunStatus.FAILED)
        self.assertEqual(result.state.error_category, "policy_violation")

    def test_invalid_tool_arguments_are_not_treated_as_retrieval_outage(self) -> None:
        # query 为空属于模型协议错误，不应被误报为向量库宕机。
        retriever = FakeRetriever([self.match])
        invalid_tool_call = ModelResponse(
            kind="tool_call",
            tool_calls=(
                ToolCallRequest(
                    call_id="call-invalid",
                    name="search_knowledge",
                    arguments={"query": "", "top_k": 3},
                ),
            ),
            response_id="response-invalid",
        )
        runner = AgentRunner(
            ScriptedModel([invalid_tool_call]),
            make_tool_factory(retriever),
            make_settings(),
        )

        result = runner.run("什么是 RAG？", self.user)

        self.assertEqual(result.state.status, RunStatus.FAILED)
        self.assertEqual(result.state.error_category, "invalid_tool_arguments")
        self.assertEqual(retriever.calls, 0)


if __name__ == "__main__":
    unittest.main()
