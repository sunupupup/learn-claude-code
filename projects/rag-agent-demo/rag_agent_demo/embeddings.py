"""Embedding 适配器。

Embedding（向量表示）把文本转换成一串数字，使语义相近的文本在向量
空间里更接近。它只是检索的表示方式，不是知识库，也不负责判断事实真伪。
"""

from __future__ import annotations

from itertools import islice
from typing import Any, Protocol

from .config import Settings


class EmbeddingProvider(Protocol):
    """供应商边界：生产用真实服务，测试用确定性的 fake。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class EmbeddingError(RuntimeError):
    """Embedding 服务调用失败；上层可据此决定是否有限重试。"""

    pass


class OpenAIEmbeddingProvider:
    """真实 OpenAI Embeddings 适配器。

    批处理是显式的，因为 Embedding API 通常有请求条数和 Token 限制。
    向量维度从响应中发现，再用来创建 Qdrant collection；不要把维度散落
    在业务代码中硬编码。
    """

    def __init__(self, client: Any, model: str, batch_size: int = 64) -> None:
        self.client = client
        self.model = model
        self.batch_size = batch_size

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAIEmbeddingProvider":
        # 延迟 import，让没有安装 openai 的离线单测仍能测试 Harness。
        # 真正执行 CLI 时，API Key 由 OpenAI SDK 从参数/环境变量读取。
        from openai import OpenAI

        kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return cls(
            client=OpenAI(**kwargs),
            model=settings.embedding_model,
            batch_size=settings.embedding_batch_size,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            # 空文档集不应该发一个无意义的外部请求。
            return []

        vectors: list[list[float]] = []
        iterator = iter(texts)
        while batch := list(islice(iterator, self.batch_size)):
            # 一个 batch 对应一次网络请求；失败由 EmbeddingError 统一向上抛出。
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                    encoding_format="float",
                )
            except Exception as exc:
                raise EmbeddingError("embedding request failed") from exc

            # API 返回的数据可能不是输入顺序，必须按 index 排回去，
            # 否则第 N 个 chunk 会被写入第 M 个向量，产生隐蔽的数据错位。
            data = sorted(response.data, key=lambda item: item.index)
            if len(data) != len(batch):
                raise EmbeddingError("embedding response length does not match request")
            vectors.extend([list(item.embedding) for item in data])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        # 查询向量必须使用和文档向量相同的模型，才能在同一空间比较。
        if not text.strip():
            raise ValueError("query text must not be empty")
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=[text],
                encoding_format="float",
            )
        except Exception as exc:
            raise EmbeddingError("query embedding request failed") from exc
        # query 只发一个文本，取第一个向量即可。
        return list(response.data[0].embedding)
