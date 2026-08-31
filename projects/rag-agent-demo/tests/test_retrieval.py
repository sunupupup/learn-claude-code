"""Embedding 与 VectorStore 协调关系测试。"""

from __future__ import annotations

import unittest

from rag_agent_demo.contracts import RetrievedChunk, UserIdentity
from rag_agent_demo.vector_store import KnowledgeRetriever


class FakeEmbeddingProvider:
    """记录查询文本的 fake，隔离真实 Embedding 网络调用。"""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1, 0.2]


class FakeVectorStore:
    """记录向量、用户、top-k 和阈值的 fake 向量库。"""

    def __init__(self, matches: list[RetrievedChunk]) -> None:
        self.matches = matches
        self.calls: list[tuple[list[float], UserIdentity, int, float]] = []

    def search(self, query_vector, user, top_k, score_threshold):
        self.calls.append((query_vector, user, top_k, score_threshold))
        return self.matches


class RetrievalTests(unittest.TestCase):
    def test_retriever_embeds_query_and_passes_policy_to_store(self) -> None:
        # 检索协调器不能丢失用户身份、top-k 或相似度阈值。
        embedder = FakeEmbeddingProvider()
        store = FakeVectorStore(
            [
                RetrievedChunk(
                    chunk_id="doc-001",
                    title="RAG",
                    heading="检索",
                    text="top result",
                    score=0.9,
                )
            ]
        )
        retriever = KnowledgeRetriever(embedder, store)
        user = UserIdentity(user_id="u-1", tenant_id="demo", groups=["engineering"])

        result = retriever.retrieve("如何检索", user, top_k=3, score_threshold=0.7)

        self.assertEqual(embedder.queries, ["如何检索"])
        self.assertEqual(result[0].chunk_id, "doc-001")
        self.assertEqual(store.calls[0][2:], (3, 0.7))


if __name__ == "__main__":
    unittest.main()
