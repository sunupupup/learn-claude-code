"""真实 Embedding 适配器的请求契约测试（不访问网络）。"""

from __future__ import annotations

from types import SimpleNamespace
import unittest

from rag_agent_demo.embeddings import OpenAIEmbeddingProvider


class FakeEmbeddingsEndpoint:
    """模拟 SDK endpoint，专门记录批次和返回顺序。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **request):
        self.calls.append(request)
        # 故意乱序返回，验证适配器按 API index 恢复输入顺序。
        data = [
            SimpleNamespace(index=index, embedding=[float(index), 1.0])
            for index in reversed(range(len(request["input"])))
        ]
        return SimpleNamespace(data=data)


class EmbeddingTests(unittest.TestCase):
    def test_documents_are_batched_and_restored_to_input_order(self) -> None:
        # 文档入库要批量请求，但结果仍必须和原始 chunk 一一对应。
        endpoint = FakeEmbeddingsEndpoint()
        provider = OpenAIEmbeddingProvider(
            client=SimpleNamespace(embeddings=endpoint),
            model="text-embedding-3-small",
            batch_size=2,
        )

        vectors = provider.embed_documents(["a", "b", "c"])

        self.assertEqual(vectors, [[0.0, 1.0], [1.0, 1.0], [0.0, 1.0]])
        self.assertEqual([call["input"] for call in endpoint.calls], [["a", "b"], ["c"]])
        self.assertTrue(all(call["encoding_format"] == "float" for call in endpoint.calls))

    def test_query_embedding_uses_single_item_request(self) -> None:
        # 查询向量和文档向量必须来自同一模型空间。
        endpoint = FakeEmbeddingsEndpoint()
        provider = OpenAIEmbeddingProvider(
            client=SimpleNamespace(embeddings=endpoint),
            model="text-embedding-3-small",
        )

        vector = provider.embed_query("RAG")

        self.assertEqual(vector, [0.0, 1.0])
        self.assertEqual(endpoint.calls[0]["input"], ["RAG"])


if __name__ == "__main__":
    unittest.main()
