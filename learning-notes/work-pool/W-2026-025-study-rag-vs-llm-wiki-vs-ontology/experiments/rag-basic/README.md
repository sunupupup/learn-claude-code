# 最小 RAG

直接打开 `rag.py`，从上到下看五步：参数 → 首次入库 → 问题向量化 → 检索 → 生成回答。

想单独展开入库过程，打开 [ingest_demo.py](ingest_demo.py)，配合 [RAG 数据准备与入库笔记](../../RAG数据准备与入库学习笔记.md)。默认只预览切块，运行 ` .\.venv\Scripts\python.exe -X utf8 ingest_demo.py`；其输出位于独立的 `.rag-data-preparation/`，不会自动接入 `rag.py` 的检索。

## 先改哪里

`rag.py` 顶部填写 `base_url`、`embedding_model`、`chat_model`。这个简单版本使用同一家兼容 OpenAI 的服务，要求支持 Embeddings 和 Chat Completions。

- `question`：要问的问题。
- `top_k = 2`：最多取回两个片段。
- `threshold = None`：暂时不按分数过滤。相似度不是正确概率。
- `collection = "documents"`：数据集合名称。

密钥单独放在本地 `.env` 中，内容为 `RAG_API_KEY=你的密钥`；不要把密钥提交到 Git。

## 怎么运行

在本目录的 PowerShell 中执行（会调用真实模型服务，可能计费）：

```powershell
.\.venv\Scripts\python.exe -X utf8 rag.py
```

第一次：读取三个示例文件 → 每个正文段落作为一个片段 → 向量化 → 保存六个片段 → 回答问题。

以后：跳过文档入库 → 只把新问题向量化 → 检索原文 → 生成回答。直接修改顶部的 `question` 再运行即可。

## 当前只需记住

- 向量用于寻找相关片段，聊天模型实际看到的是原文。
- 文档没有自动更新；修改资料或更换向量模型后，把 `collection` 改为一个新名字，如 `documents_v2`，重新入库。
- 为了看清主流程，这版没有导入失败恢复。若首次入库中断，也换新集合名重新运行。
- 文档按空行切分，针对当前几份小示例；没有实现大文档切分策略。
- 当前已做语法检查；尚未调用真实模型，不能保证检索质量和生成结果。

依赖仍在 `requirements.txt`，本机 `.venv` 已安装。原命令行版本的 `inspect / ingest / ask` 和配套测试已移除，不再使用。

方案背景见 [最小 RAG 实操方案](../../最小RAG实操方案.md)；其中原先复杂版本的计划仅作历史记录，以这里和当前代码为准。
