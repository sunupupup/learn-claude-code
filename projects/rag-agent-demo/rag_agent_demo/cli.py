"""最小 CLI 入口。

CLI 只负责组装真实的 Embedding、Qdrant、Tool 和模型适配器；
Agent 的控制规则仍集中在 agent.py，避免 UI 层复制一套循环。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from .agent import AgentRunner
from .config import Settings
from .embeddings import OpenAIEmbeddingProvider
from .ingest import DocumentIngestor
from .model import OpenAIResponsesModel
from .tools import SearchKnowledgeTool
from .vector_store import KnowledgeRetriever, QdrantVectorStore


def build_runner(settings: Settings) -> AgentRunner:
    # 在真正连接外部服务前先验证配置，减少启动到一半才失败的情况。
    settings.validate()

    # 启动索引流程故意放在这里，方便学习者看到完整链路。生产环境通常把
    # ingestion 做成独立的、带版本号的后台流水线，而不是每个 Web worker 执行。
    chunks = DocumentIngestor(
        data_dir=settings.data_dir,
        manifest_path=settings.manifest_path,
    ).ingest()
    embedder = OpenAIEmbeddingProvider.from_settings(settings)
    # 先拿到向量，才能知道 Embedding 模型的维度并创建 Qdrant collection。
    vectors = embedder.embed_documents([chunk.text for chunk in chunks])
    if not vectors:
        raise RuntimeError("no document embeddings were produced")

    store = QdrantVectorStore.from_settings(settings)
    store.prepare_collection(vector_size=len(vectors[0]))
    store.upsert_chunks(chunks, vectors)
    retriever = KnowledgeRetriever(embedder=embedder, store=store)

    def tool_factory(user):
        # 每个请求创建绑定了当前 user 的 Tool；模型无法通过 Tool 参数切换身份。
        return SearchKnowledgeTool(
            retriever=retriever,
            user=user,
            default_top_k=settings.top_k,
            score_threshold=settings.score_threshold,
        )

    return AgentRunner(
        model=OpenAIResponsesModel.from_settings(settings),
        tool_factory=tool_factory,
        settings=settings,
    )


def build_parser() -> argparse.ArgumentParser:
    # CLI 参数是本地演示入口；真实 Web 服务应从认证上下文获得 user identity。
    parser = argparse.ArgumentParser(description="Run the D1 RAG Agent demo")
    parser.add_argument("--question", help="Question to ask; reads stdin when omitted")
    parser.add_argument("--user-id", default="demo-user")
    parser.add_argument("--tenant", default="demo")
    parser.add_argument(
        "--groups",
        default="engineering",
        help="Comma-separated authorization groups, e.g. engineering,support",
    )
    parser.add_argument("--top-k", type=int, help="Override RAG_TOP_K")
    parser.add_argument("--score-threshold", type=float, help="Override RAG_SCORE_THRESHOLD")
    parser.add_argument(
        "--no-rebuild",
        action="store_true",
        help="Do not delete/recreate the demo collection at startup",
    )
    parser.add_argument("--trace", action="store_true", help="Print safe structured trace events")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    question = args.question or input("Question: ").strip()
    if not question:
        print("Question must not be empty.")
        return 2

    # 先读环境配置，再用本次命令行参数覆盖可调的检索/开发选项。
    settings = Settings.from_env(Path(__file__).resolve().parents[1])
    overrides = {"rebuild_collection_on_start": not args.no_rebuild}
    if args.top_k is not None:
        overrides["top_k"] = args.top_k
    if args.score_threshold is not None:
        overrides["score_threshold"] = args.score_threshold
    settings = replace(settings, **overrides)

    try:
        runner = build_runner(settings)
        # 这里直接构造身份只是教学简化；生产系统必须使用已验证的 token/session。
        from .contracts import UserIdentity

        user = UserIdentity(
            user_id=args.user_id,
            tenant_id=args.tenant,
            groups=[group.strip() for group in args.groups.split(",") if group.strip()],
        )
        result = runner.run(question, user)
    except Exception as exc:
        # 启动错误对操作者可诊断，但不要打印 API Key 或完整外部异常上下文。
        print(f"Startup failed: {type(exc).__name__}: {exc}")
        return 1

    # 只输出经过 Harness 校验的 user_message，不把原始模型文本直接透传。
    print(result.user_message)
    if result.final_answer and result.final_answer.sources:
        print("\nSources:")
        for source in result.final_answer.sources:
            print(f"- {source.title} ({source.chunk_id})")
    print(f"\nRun status: {result.state.status.value}")
    if args.trace:
        print(json.dumps(result.trace, ensure_ascii=False, indent=2))
    # no_evidence 是正常业务终态；failed 才代表本次请求没有安全完成。
    return 0 if result.state.status.value in {"completed", "no_evidence"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
