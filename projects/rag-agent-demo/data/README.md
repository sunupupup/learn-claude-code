# 数据目录说明

这个目录模拟一个很小的企业知识源。`documents/` 放正文，`manifest.json` 放程序可校验的来源和权限元数据。

`manifest.json` 是标准 JSON，不能像 Python 一样写注释，所以字段含义集中记录在这里：

- `document_id`：文档稳定标识，参与 chunk ID 和向量点 ID 的生成；
- `path`：相对于 `data/` 的 Markdown 路径，摄取时会做路径越界检查；
- `title`：最终回答引用来源时展示的标题；
- `tenant_id`：租户边界，查询时必须和当前用户一致；
- `allowed_groups`：群组 ACL，当前用户至少命中一个群组才允许检索；
- chunk 后的每个片段都会复制 `title`、`tenant_id` 和 `allowed_groups`，写进向量库 payload。

建议学习顺序：先读 [manifest.json](manifest.json)，再读 [ingest.py](../rag_agent_demo/ingest.py)，最后读 [vector_store.py](../rag_agent_demo/vector_store.py) 中的 `build_qdrant_acl_filter()`。

注意：示例正文是教学资料，不包含真实客户数据。真实 Embedding/LLM 服务会接收文档或检索上下文，生产环境必须先确认数据驻留、脱敏、保留和供应商授权策略。
