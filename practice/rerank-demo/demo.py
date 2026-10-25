"""真实中文 embedding → Qdrant 向量检索 → cross-encoder 重排。"""

import argparse
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path

EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
EMBEDDING_REVISION = "7999e1d3359715c523056ef9478215996d62a620"
RERANK_MODEL = "BAAI/bge-reranker-base"
RERANK_REVISION = "2cfc18c9415c912f9d8155881c133215df768a70"
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："
# 将教学输入保留在源码中，清理运行产物后仍能看到完整问题与候选原文。
DEFAULT_CASES = [{
    "name": "cancel-subscription",
    "expected_inversion": ["A", "B"],
    "query": "怎么关闭苹果手机的自动续费？",
    "documents": [
        {"id": "A", "text": "苹果手机自动续费功能介绍：开通连续包月服务后，系统会按月自动扣费，无须用户手动付款。"},
        {"id": "B", "text": "取消订阅的方法：打开 iPhone 设置，点击顶部的 Apple ID，进入订阅，选择需要停止的服务，然后点击取消订阅。"},
        {"id": "C", "text": "苹果手机支持手动调节屏幕亮度，也可以开启深色模式。"},
        {"id": "D", "text": "蓝牙耳机的电量可在手机的电池组件中查看。"},
    ],
}]


def load_cases(path=None):
    # 深拷贝避免 --query 替换问题时修改模块级默认样例；外部 JSON 输入仍然可选。
    cases = json.loads(path.read_text(encoding="utf-8")) if path else deepcopy(DEFAULT_CASES)
    if not isinstance(cases, list) or not cases:
        raise ValueError("样例文件必须是非空 JSON 数组。")
    names = set()
    for case in cases:
        if not isinstance(case.get("name"), str) or not case["name"].strip():
            raise ValueError("每个样例需要非空 name。")
        if case["name"] in names:
            raise ValueError("样例 name 不能重复。")
        names.add(case["name"])
        if not isinstance(case.get("query"), str) or not case["query"].strip():
            raise ValueError("每个样例需要非空 query。")
        documents = case.get("documents")
        if not isinstance(documents, list) or len(documents) < 2:
            raise ValueError("每个样例至少需要两篇候选文档。")
        ids = [doc.get("id") for doc in documents]
        if any(not isinstance(doc_id, str) or not doc_id for doc_id in ids):
            raise ValueError("文档 id 必须是非空字符串。")
        if len(set(ids)) != len(ids):
            raise ValueError("同一个样例的文档 id 不能重复。")
        if any(not isinstance(doc.get("text"), str) or not doc["text"].strip()
               for doc in documents):
            raise ValueError("文档 text 不能为空。")
        expected = case.get("expected_inversion")
        if expected is not None and (
            not isinstance(expected, list) or len(expected) != 2
            or any(doc_id not in ids for doc_id in expected) or expected[0] == expected[1]
        ):
            raise ValueError("expected_inversion 必须包含两个不同且存在的文档 id。")
    return cases


def model_path(model_id, revision):
    from huggingface_hub import snapshot_download

    # 只下载运行所需文件，避免连同另一种权重格式和 ONNX 文件重复下载。
    # 使用本地快照路径加载，也避免 tokenizer 在离线模式额外请求仓库元信息。
    return snapshot_download(
        model_id, revision=revision,
        allow_patterns=["config.json", "config_sentence_transformers.json", "modules.json",
                        "sentence_bert_config.json", "model.safetensors", "tokenizer.json",
                        "tokenizer_config.json", "special_tokens_map.json", "vocab.txt",
                        "sentencepiece.bpe.model", "1_Pooling/config.json"],
    )


def run_case(case, embedder, reranker, top_k):
    from qdrant_client import QdrantClient, models

    documents = case["documents"]
    texts = [doc["text"] for doc in documents]
    # 双编码器分别压缩 query 和文档；文档向量可提前生成，查询时复用。
    vectors = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    query_vector = embedder.encode(
        QUERY_PREFIX + case["query"], normalize_embeddings=True, show_progress_bar=False
    )
    # 本地内存模式仍使用 Qdrant 的存储/查询接口，不需要 Docker 或远程服务。
    with closing(QdrantClient(":memory:")) as database:
        database.create_collection(
            "documents",
            vectors_config=models.VectorParams(
                size=vectors.shape[1], distance=models.Distance.COSINE
            ),
        )
        database.upsert(
            "documents",
            points=[models.PointStruct(id=i, vector=vector.tolist(), payload=doc)
                    for i, (doc, vector) in enumerate(zip(documents, vectors))],
        )
        hits = database.query_points(
            "documents", query=query_vector.tolist(), limit=top_k, with_payload=True
        ).points

    # 交叉编码器同时读取 query 和每篇候选原文；不读取向量分数或人工标签。
    # Identity 保留模型原始 logit：分数可为负，不是概率，也不能与余弦分数比较。
    scores = reranker.predict(
        [(case["query"], hit.payload["text"]) for hit in hits],
        show_progress_bar=False,
    )
    retrieved = [dict(hit.payload, vector_rank=i, vector_score=float(hit.score),
                      rerank_score=float(score))
                 for i, (hit, score) in enumerate(zip(hits, scores), start=1)]
    reranked = sorted(retrieved, key=lambda row: row["rerank_score"], reverse=True)
    # 检查严格反转，平分后排序变化不计入成功；只有进入 top-k 的文档才能参与。
    inversions = [
        [left["id"], right["id"]]
        for i, left in enumerate(retrieved)
        for right in retrieved[i + 1:]
        if left["vector_score"] > right["vector_score"]
        and left["rerank_score"] < right["rerank_score"]
    ]
    expected = case.get("expected_inversion")
    return dict(name=case["name"], query=case["query"], retrieved=retrieved,
                reranked=reranked, inversions=inversions, expected_inversion=expected,
                check_passed=expected in inversions if expected else bool(inversions))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, help="可选：加载自己的 JSON 样例，默认使用源码内置样例")
    parser.add_argument("--query", help="替换单个样例的 query；候选文本保持不变")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--output", type=Path, help="把本次真实结果保存为 JSON")
    parser.add_argument("--check", action="store_true", help="检查样例声明的反转对；未声明则检查任意严格反转")
    args = parser.parse_args()
    try:
        cases = load_cases(args.cases)
        if args.top_k < 1:
            raise ValueError("--top-k 必须大于零。")
        if args.query is not None:
            if len(cases) != 1 or not args.query.strip():
                raise ValueError("--query 需要一个样例和非空问题。")
            cases[0]["query"] = args.query
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        parser.error(str(error))

    # 参数检查后再加载大依赖，--help 或输入错误不必等待模型运行库初始化。
    print("加载固定版本的真实模型，首次运行需联网下载；默认在 CPU 上计算。", flush=True)
    import torch
    from sentence_transformers import CrossEncoder, SentenceTransformer

    # 限制小样本 CPU 线程数，避免线程调度开销淹没计算；固定种子便于复跑。
    torch.set_num_threads(4)
    torch.manual_seed(0)
    embedder = SentenceTransformer(
        model_path(EMBEDDING_MODEL, EMBEDDING_REVISION), device=args.device
    )
    print("Embedding 模型已就绪，开始加载 reranker。", flush=True)
    reranker = CrossEncoder(
        model_path(RERANK_MODEL, RERANK_REVISION), device=args.device, max_length=512,
        activation_fn=torch.nn.Identity(),
    )
    print("两个模型已就绪，开始向量检索与重排。", flush=True)
    results = []
    for case in cases:
        result = run_case(case, embedder, reranker, args.top_k)
        results.append(result)
        print(f"\nQuery：{result['query']}")
        for title, rows, score_key in [
            ("向量检索（余弦相似度）", result["retrieved"], "vector_score"),
            ("Rerank（原始相关性分数）", result["reranked"], "rerank_score"),
        ]:
            print(f"\n{title}")
            for rank, row in enumerate(rows, start=1):
                print(f"  {rank}. {row['id']}  {row[score_key]:.6f}  {row['text']}")
        print("\n严格反转的文档对（原先靠前 → 原先靠后）：", result["inversions"])
    report = dict(
        generated_at=datetime.now(timezone.utc).isoformat(), device=args.device,
        embedding_model=EMBEDDING_MODEL, embedding_revision=EMBEDDING_REVISION,
        rerank_model=RERANK_MODEL, rerank_revision=RERANK_REVISION,
        query_prefix=QUERY_PREFIX, top_k=args.top_k,
        versions={name: version(name) for name in
                  ["torch", "sentence-transformers", "transformers", "qdrant-client"]},
        results=results,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(f"\n真实结果已保存：{args.output.resolve()}")
    if args.check and any(not result["check_passed"] for result in results):
        raise SystemExit("验收失败：至少一个样例没有出现要求的严格反转；保留实际结果，不伪造分数。")
    if args.check:
        print("验收通过：每个样例都出现了向量分数与重排分数的严格排序反转。")


if __name__ == "__main__":
    main()
