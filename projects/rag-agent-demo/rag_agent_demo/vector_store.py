"""Qdrant 向量库适配器和检索协调器。

最重要的安全点在这里：权限过滤必须作为向量查询的 pre-filter，
而不是拿到 top-k 后才在 Python 里删除。否则未授权内容可能先影响排序，
甚至进入模型上下文、日志或缓存。
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from .contracts import DocumentChunk, RetrievedChunk, UserIdentity
from .embeddings import EmbeddingProvider


class VectorStore(Protocol):
    """向量库最小接口；业务层不依赖 Qdrant 的具体 SDK 类型。"""

    def prepare_collection(self, vector_size: int) -> None:
        ...

    def upsert_chunks(self, chunks: list[DocumentChunk], vectors: list[list[float]]) -> None:
        ...

    def search(
        self,
        query_vector: list[float],
        user: UserIdentity,
        top_k: int,
        score_threshold: float,
    ) -> list[RetrievedChunk]:
        ...


def is_authorized_payload(payload: dict[str, Any], user: UserIdentity) -> bool:
    """Pure policy helper used by tests and by the mental model.

    The real Qdrant path enforces the same rule in its query filter, before ranking.
    """

    # 授权条件是“同租户 AND 至少一个群组重叠”，不是二选一。
    return (
        payload.get("tenant_id") == user.tenant_id
        and bool(set(payload.get("allowed_groups", [])) & set(user.groups))
    )


def build_qdrant_acl_filter(user: UserIdentity) -> Any:
    """把应用身份编译成向量库级别的 pre-filter。

    这里的 Filter 会随着 query 一起发送给 Qdrant，先缩小候选范围，
    再做相似度排序；Prompt 里的“请遵守权限”不能替代这一步。
    """

    # 供应商 SDK 只在适配器函数内部导入，便于核心逻辑脱离 Qdrant 测试。
    from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

    return Filter(
        must=[
            FieldCondition(key="tenant_id", match=MatchValue(value=user.tenant_id)),
            FieldCondition(key="allowed_groups", match=MatchAny(any=user.groups)),
        ]
    )


class QdrantVectorStore:
    """Qdrant 适配器：在向量排序前执行租户/群组过滤。"""

    def __init__(
        self,
        client: Any,
        collection_name: str,
        rebuild_on_start: bool = True,
    ) -> None:
        self.client = client
        self.collection_name = collection_name
        self.rebuild_on_start = rebuild_on_start

    @classmethod
    def from_settings(cls, settings: Any) -> "QdrantVectorStore":
        # 只有真正运行 CLI 时才需要导入和连接 Qdrant；测试可以使用 Protocol fake。
        from qdrant_client import QdrantClient

        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=settings.qdrant_timeout_s,
        )
        return cls(
            client=client,
            collection_name=settings.qdrant_collection,
            rebuild_on_start=settings.rebuild_collection_on_start,
        )

    def prepare_collection(self, vector_size: int) -> None:
        # collection 的向量维度必须和 Embedding 模型输出一致，因此由首批向量决定。
        from qdrant_client.models import Distance, VectorParams

        if self.client.collection_exists(self.collection_name):
            if not self.rebuild_on_start:
                # --no-rebuild 用于复用已有索引；生产环境还应校验模型/维度版本。
                return
            # 这是学习版的启动快照策略。生产环境不能删除线上 collection，
            # 应构建 versioned collection，验证后用 alias 原子切换并保留回滚。
            self.client.delete_collection(self.collection_name)

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    @staticmethod
    def _point_id(chunk: DocumentChunk) -> str:
        # 稳定 ID 让同一内容快照的重试/upsert 幂等；内容变化会生成新的点 ID。
        return str(uuid5(NAMESPACE_URL, f"{chunk.document_id}:{chunk.chunk_id}:{chunk.content_hash}"))

    def upsert_chunks(self, chunks: list[DocumentChunk], vectors: list[list[float]]) -> None:
        # Qdrant 的 payload 同时保存正文、来源和 ACL，后续检索才能返回可引用内容。
        from qdrant_client.models import PointStruct

        if len(chunks) != len(vectors):
            raise ValueError("chunk/vector count mismatch")

        points = [
            PointStruct(
                id=self._point_id(chunk),
                vector=vector,
                payload=chunk.model_dump(mode="json"),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self.client.upsert(
            # wait=True 保证返回时写入已经完成，避免马上查询读到半成品。
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    def search(
        self,
        query_vector: list[float],
        user: UserIdentity,
        top_k: int,
        score_threshold: float,
    ) -> list[RetrievedChunk]:
        # 只取生成回答所需的字段；ACL 字段已经用于过滤，不必暴露给模型。
        payload_fields = ["chunk_id", "title", "heading", "text"]
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            # query_filter 在 Qdrant 内部先执行，top-k 不会被未授权文档污染。
            query_filter=build_qdrant_acl_filter(user),
            limit=top_k,
            # score_threshold 只表示“相似度候选门槛”，不等于答案正确。
            score_threshold=score_threshold,
            with_payload=payload_fields,
            with_vectors=False,
        )

        matches: list[RetrievedChunk] = []
        for point in response.points:
            # payload 来自我们自己的入库契约；仍通过 Pydantic 再校验一次形状。
            payload = point.payload or {}
            matches.append(
                RetrievedChunk(
                    chunk_id=str(payload["chunk_id"]),
                    title=str(payload["title"]),
                    heading=str(payload.get("heading", "")),
                    text=str(payload["text"]),
                    score=float(point.score),
                )
            )
        return matches


class KnowledgeRetriever:
    """协调“问题 Embedding → 带权限的向量查询”两步。"""

    def __init__(self, embedder: EmbeddingProvider, store: VectorStore) -> None:
        self.embedder = embedder
        self.store = store

    def retrieve(
        self,
        query: str,
        user: UserIdentity,
        top_k: int,
        score_threshold: float,
    ) -> list[RetrievedChunk]:
        # 文档入库和问题查询必须使用同一个向量空间/模型。
        query_vector = self.embedder.embed_query(query)
        # user、top_k 和 threshold 一起交给 VectorStore，不能在上层丢掉权限上下文。
        return self.store.search(query_vector, user, top_k, score_threshold)
