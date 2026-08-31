"""文档摄取和路径安全测试。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rag_agent_demo.ingest import DocumentIngestor, ManifestError


class IngestTests(unittest.TestCase):
    def test_ingest_attaches_manifest_metadata_to_each_chunk(self) -> None:
        # 验证标题、租户、群组和 content hash 会从 manifest 进入每个 chunk。
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "data"
            docs_dir = data_dir / "documents"
            docs_dir.mkdir(parents=True)
            (docs_dir / "guide.md").write_text(
                "# Guide\n\n## Loop\n\nThe loop stops after a bounded number of turns.",
                encoding="utf-8",
            )
            manifest = data_dir / "manifest.json"
            manifest.write_text(
                json.dumps(
                    [
                        {
                            "document_id": "guide",
                            "path": "documents/guide.md",
                            "title": "学习指南",
                            "tenant_id": "demo",
                            "allowed_groups": ["engineering"],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            chunks = DocumentIngestor(data_dir, manifest).ingest()

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].title, "学习指南")
        self.assertEqual(chunks[0].tenant_id, "demo")
        self.assertEqual(chunks[0].allowed_groups, ["engineering"])
        self.assertEqual(len(chunks[0].content_hash), 64)

    def test_manifest_rejects_path_escape(self) -> None:
        # manifest 是不可信配置，不能通过 ../ 读取 data 根目录之外的文件。
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "data"
            data_dir.mkdir()
            manifest = data_dir / "manifest.json"
            manifest.write_text(
                json.dumps(
                    [
                        {
                            "document_id": "escape",
                            "path": "../secret.md",
                            "title": "不应读取",
                            "tenant_id": "demo",
                            "allowed_groups": ["engineering"],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ManifestError):
                DocumentIngestor(data_dir, manifest).ingest()


if __name__ == "__main__":
    unittest.main()
