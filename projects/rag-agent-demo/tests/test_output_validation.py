"""最终回答的 JSON、来源白名单和证据状态测试。"""

from __future__ import annotations

import json
import unittest

from rag_agent_demo.output_validation import OutputValidationError, validate_final_output


class OutputValidationTests(unittest.TestCase):
    def test_valid_answer_must_cite_retrieved_chunk(self) -> None:
        # 有答案时必须引用本次检索到的 chunk。
        output = validate_final_output(
            json.dumps(
                {
                    "answerable": True,
                    "answer": "答案",
                    "sources": [{"chunk_id": "doc-001", "title": "文档"}],
                }
            ),
            allowed_source_ids=["doc-001"],
            retrieval_status="matched",
        )
        self.assertTrue(output.answerable)

    def test_unknown_source_is_rejected(self) -> None:
        # 模型即使输出合法 JSON，也不能引用本次上下文之外的来源。
        with self.assertRaises(OutputValidationError):
            validate_final_output(
                json.dumps(
                    {
                        "answerable": True,
                        "answer": "答案",
                        "sources": [{"chunk_id": "not-retrieved", "title": "伪造"}],
                    }
                ),
                allowed_source_ids=["doc-001"],
                retrieval_status="matched",
            )

    def test_no_evidence_cannot_become_answerable(self) -> None:
        # 空检索时拒绝模型用外部常识生成“看似正确”的事实答案。
        with self.assertRaises(OutputValidationError):
            validate_final_output(
                json.dumps(
                    {
                        "answerable": True,
                        "answer": "模型常识答案",
                        "sources": [{"chunk_id": "doc-001", "title": "文档"}],
                    }
                ),
                allowed_source_ids=[],
                retrieval_status="no_relevant_match",
            )


if __name__ == "__main__":
    unittest.main()
