"""只看 RAG 数据准备；说明见 ../../RAG数据准备与入库学习笔记.md。"""

import hashlib
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

# 1. 先改这里的参数。默认只预览，不调用模型、不写向量库。
preview_only = True       # False 才真正调用 Embedding 并入库
chunk_mode = "paragraph"  # paragraph：先按段落；fixed：把正文按固定长度切
chunk_size = 80           # 每块正文最多 80 个字符；故意设小，便于看效果，不是生产推荐值
chunk_overlap = 20        # 同一段连续切块时，后一块重复前一块末尾的 20 个字符
include_title = True     # 给每块补上文档标题，减少“这一条说的是谁”的歧义
document_prefix = ""      # 只有模型明确要求时才填，比如某些 E5 模型要求 passage: 前缀
embedding_batch_size = 4  # 每次 Embedding 请求最多发送 4 个片段
write_batch_size = 4      # 每次向量库写入最多发送 4 条记录，与模型请求批量是两回事

base_url = "https://your-provider.example/v1"  # Embedding 服务根地址
embedding_model = "填写你的向量模型名"        # 本实验不需要聊天模型
collection = "prepared_documents_v1"          # 每轮实际入库换新名字，保留旧实验结果

root = Path(__file__).resolve().parent
documents_dir = root / "documents"             # 从这里读取原始 Markdown
output_dir = root / ".rag-data-preparation"    # 实验输出，与 rag.py 的库分开


def split_text(text):
    """按长度滑动切块；只把这段重复使用的切分逻辑提成一个函数。"""
    pieces = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        pieces.append(text[start:end])
        if end == len(text):  # 已覆盖结尾，不再生成一块只有重复尾巴的内容
            break
        start = end - chunk_overlap
    return pieces


# 2. 这些限制是为了避免切分循环不前进，以及批量参数为零。
if not 0 <= chunk_overlap < chunk_size:
    raise ValueError("需要满足：0 <= chunk_overlap < chunk_size。")
if chunk_mode not in ("paragraph", "fixed") or min(embedding_batch_size, write_batch_size) < 1:
    raise ValueError("检查 chunk_mode 和两个 batch_size 参数。")

# 3. 读原文，做最少清洗，再切分。这个示例只处理简单 Markdown，不解析 PDF/表格。
chunks = []
for file in sorted(documents_dir.glob("*.md")):
    original = file.read_text(encoding="utf-8-sig")
    text = original.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        continue
    source_hash = hashlib.sha256(original.encode("utf-8")).hexdigest()  # 标记读取到的原文版本
    first_line = text.split("\n", 1)[0]
    title = first_line[2:] if first_line.startswith("# ") else file.stem
    body = text[len(first_line):].strip() if first_line.startswith("# ") else text
    paragraphs = body.split("\n\n") if chunk_mode == "paragraph" else [body]

    number = 0
    for paragraph in paragraphs:
        for piece in split_text(paragraph.strip()):
            number += 1
            chunk_text = f"{title}\n{piece}" if include_title else piece
            chunks.append({
                "id": str(uuid5(NAMESPACE_URL, f"{file.name}:{source_hash}:{number}")),
                "source": file.name, "source_hash": source_hash,
                "chunk_number": number, "title": title,
                "body": piece, "text": chunk_text,
                "embedding_input": document_prefix + chunk_text,
            })
if not chunks:
    raise ValueError("没有可入库的正文，请检查 documents 目录。")

# 4. 先看切出来的东西。模型前缀只影响编码输入，不改来源原文。
for chunk in chunks:
    print(f"\n{chunk['source']} #{chunk['chunk_number']} | 正文 {len(chunk['body'])} 字符")
    print(chunk["embedding_input"])
output_dir.mkdir(exist_ok=True)
(output_dir / "chunks-preview.json").write_text(
    json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n共 {len(chunks)} 块；预览保存到 {output_dir / 'chunks-preview.json'}")

# 5. 真正入库：先获得所有向量，再创建一个新集合，避免混用不同实验配置。
if preview_only:
    print("仅预览：没有调用 Embedding，没有写入向量库。")
else:
    from dotenv import load_dotenv
    from openai import OpenAI
    from qdrant_client import QdrantClient, models

    load_dotenv(root / ".env")
    api_key = os.getenv("RAG_API_KEY")
    if not api_key or api_key == "replace-me" or "your-provider.example" in base_url or "填写" in embedding_model:
        raise ValueError("请填写 base_url、embedding_model 和 .env 的 RAG_API_KEY。")
    db = QdrantClient(path=str(output_dir / "qdrant"))
    try:
        if db.collection_exists(collection):
            raise ValueError("集合已存在：请改成新的 collection 名称，避免残留旧片段。")
        vectors = []
        with OpenAI(api_key=api_key, base_url=base_url, timeout=60, max_retries=0) as client:
            for start in range(0, len(chunks), embedding_batch_size):
                batch = chunks[start:start + embedding_batch_size]
                response = client.embeddings.create(model=embedding_model,
                    input=[item["embedding_input"] for item in batch], encoding_format="float")
                ordered = sorted(response.data, key=lambda item: item.index)
                if [item.index for item in ordered] != list(range(len(batch))):
                    raise ValueError("返回的向量与输入片段没有一一对应。")
                vectors.extend(item.embedding for item in ordered)
                print(f"已向量化 {len(vectors)}/{len(chunks)} 块。")
        dimension = len(vectors[0])  # 维度由模型实际输出决定，不随意写成 768 或 1536
        if dimension == 0 or any(len(vector) != dimension for vector in vectors):
            raise ValueError("向量为空或维度不一致。")
        db.create_collection(collection_name=collection,
            vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE))
        for start in range(0, len(chunks), write_batch_size):
            points = []
            for i in range(start, min(start + write_batch_size, len(chunks))):
                payload = {key: chunks[i][key] for key in ("text", "source", "source_hash", "chunk_number", "title")}
                points.append(models.PointStruct(id=chunks[i]["id"], vector=vectors[i], payload=payload))
            db.upsert(collection_name=collection, points=points, wait=True)
        count = db.count(collection_name=collection, exact=True).count
        if count != len(chunks):
            raise ValueError("库中的记录数与准备的片段数不同。")
        # 记录模型和切分规则，之后检索时才能知道这批向量是怎样生成的。
        record = {"collection": collection, "count": count, "dimension": dimension,
            "embedding_model": embedding_model, "base_url": base_url,
            "document_prefix": document_prefix, "include_title": include_title,
            "chunk_mode": chunk_mode, "chunk_size": chunk_size, "chunk_overlap": chunk_overlap}
        (output_dir / f"{collection}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"入库完成：{count} 条，{dimension} 维；本实验到这里结束，不检索、不生成回答。")
    finally:
        db.close()  # 即使导入失败，也释放本地数据库文件锁
