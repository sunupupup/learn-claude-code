"""把 manifest + Markdown 文档转换为带权限元数据的 chunk。

摄取（ingestion）是离线/启动阶段的知识准备工作，不是用户每次提问
时临时拼接文本。这里先把来源、标题和 ACL 固定下来，再交给 Embedding
和向量库适配器。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .contracts import DocumentChunk, DocumentManifest


class ManifestError(ValueError):
    """文档元数据不可信时停止摄取，避免把坏数据写入索引。"""


class MarkdownChunker:
    """Small heading-aware chunker for the demo corpus.

    A production ingestion pipeline would usually add language-aware splitting,
    token-based budgets, overlap policy, document versioning, and richer parsers.
    The important invariant here is that each chunk keeps its heading and source.
    """

    # 只识别 Markdown 标题，不引入重量级解析器；D1 语料足够简单。
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

    def __init__(self, max_chars: int = 900) -> None:
        if max_chars < 100:
            raise ValueError("max_chars must be at least 100")
        self.max_chars = max_chars

    def chunk(self, markdown: str) -> list[tuple[str, str]]:
        # 第一遍先按空行和标题拆成带 heading 的语义块。
        blocks: list[tuple[str, str]] = []
        heading = "Document"
        buffer: list[str] = []

        def flush() -> None:
            # 统一行内空白，但保留段落边界，便于模型理解原文结构。
            nonlocal buffer
            body = "\n".join(line.strip() for line in buffer).strip()
            if body:
                blocks.append((heading, body))
            buffer = []

        for line in markdown.splitlines():
            match = self.heading_pattern.match(line)
            if match:
                flush()
                heading = match.group(2).strip()
            elif not line.strip():
                flush()
            else:
                buffer.append(line)
        flush()

        chunks: list[tuple[str, str]] = []
        # 第二遍把相邻小块合并到字符上限内；生产系统通常会用 token
        # 预算、重叠窗口和语言感知切分，这里刻意保持可读。
        current_heading: str | None = None
        current_parts: list[str] = []
        current_size = 0

        def emit_current() -> None:
            # 每次 emit 都形成一个最终可嵌入、可检索的 chunk。
            nonlocal current_heading, current_parts, current_size
            if current_parts and current_heading is not None:
                chunks.append((current_heading, "\n\n".join(current_parts).strip()))
            current_heading = None
            current_parts = []
            current_size = 0

        for block_heading, body in blocks:
            rendered = f"## {block_heading}\n{body}"
            if current_parts and current_size + len(rendered) + 2 > self.max_chars:
                # 先输出已有内容，再开始下一个 chunk，避免超过预算。
                emit_current()
            current_heading = current_heading or block_heading
            current_parts.append(rendered)
            current_size += len(rendered) + 2
        emit_current()
        return chunks


class DocumentIngestor:
    def __init__(self, data_dir: Path, manifest_path: Path, chunker: MarkdownChunker | None = None) -> None:
        # resolve() 让后续的路径 containment 检查基于绝对路径，并处理符号链接。
        self.data_dir = data_dir.resolve()
        self.manifest_path = manifest_path.resolve()
        self.chunker = chunker or MarkdownChunker()

    def load_manifest(self) -> list[DocumentManifest]:
        # manifest 是外部输入，先解析 JSON，再交给 Pydantic 做字段/权限校验。
        try:
            raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestError(f"cannot load manifest: {self.manifest_path}") from exc

        if not isinstance(raw, list):
            raise ManifestError("manifest root must be a JSON array")

        entries: list[DocumentManifest] = []
        seen_ids: set[str] = set()
        for item in raw:
            try:
                entry = DocumentManifest.model_validate(item)
            except Exception as exc:  # Pydantic error is surfaced as a manifest error.
                raise ManifestError(f"invalid manifest entry: {item!r}") from exc
            if entry.document_id in seen_ids:
                # 同一个 ID 会造成覆盖或引用歧义，因此整个索引直接失败。
                raise ManifestError(f"duplicate document_id: {entry.document_id}")
            seen_ids.add(entry.document_id)
            entries.append(entry)
        return entries

    def _safe_document_path(self, relative_path: str) -> Path:
        # 仅检查字符串里的 ".." 不够：符号链接也可能把路径带出根目录。
        # 所以这里对拼接结果 resolve 后再检查它是否仍是 data_dir 的子路径。
        candidate = (self.data_dir / relative_path).resolve()
        if self.data_dir not in candidate.parents:
            # Never let a manifest path escape the ingestion root.
            raise ManifestError(f"document path escapes data directory: {relative_path}")
        return candidate

    def ingest(self) -> list[DocumentChunk]:
        # 这是完整摄取链路：manifest → 文件 → chunk → ACL + content hash。
        chunks: list[DocumentChunk] = []
        for entry in self.load_manifest():
            document_path = self._safe_document_path(entry.path)
            try:
                markdown = document_path.read_text(encoding="utf-8")
            except OSError as exc:
                raise ManifestError(f"cannot read document: {entry.path}") from exc

            sections = self.chunker.chunk(markdown)
            if not sections:
                raise ManifestError(f"document has no content: {entry.path}")

            for index, (heading, text) in enumerate(sections, start=1):
                # 内容 hash 用来识别快照变化，也让向量点 ID 可以稳定、可重试。
                content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{entry.document_id}-{index:03d}",
                        document_id=entry.document_id,
                        title=entry.title,
                        source_path=entry.path,
                        tenant_id=entry.tenant_id,
                        allowed_groups=entry.allowed_groups,
                        heading=heading,
                        text=text,
                        content_hash=content_hash,
                    )
                )
        return chunks
