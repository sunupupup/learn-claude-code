# 看见 rerank 把顺序反过来

目标：用真实模型复现 **向量检索 A > B，重排序后 B > A**。没有 API Key、付费调用或手写打分规则。

## 先运行

在仓库根目录执行（本次验证使用 Python 3.11）：

```powershell
python -m venv practice/rerank-demo/.venv
practice/rerank-demo/.venv/Scripts/python.exe -m pip install sentence-transformers==5.1.2 transformers==4.57.3 qdrant-client==1.15.1 hf-xet==1.2.0
practice/rerank-demo/.venv/Scripts/python.exe practice/rerank-demo/demo.py --check
```

已按要求清理依赖与运行产物，只保留 README、源码和验收说明；重新运行需按上述步骤安装。无需激活环境。
首次需从 Hugging Face 下载约 1.2 GB 模型，保存在用户级默认模型缓存中，不存入 Git；默认使用 CPU。
后续运行会复用模型文件；严格离线运行前需完整缓存，之后可设置 `$env:HF_HUB_OFFLINE='1'`。
已安装支持 CUDA 的 PyTorch 时可加 `--device cuda`，CPU 与 GPU 末位分数可能略有差异。

## 这次问什么

用于检索实验的手机帮助知识库，具体问题与候选原文内置于 [demo.py](./demo.py) 的 `DEFAULT_CASES`。

- Query：怎么关闭苹果手机的自动续费？
- A：苹果手机自动续费的功能介绍，说明系统会按月扣费，没有告诉你怎么关闭。
- B：用“iPhone、取消订阅”的措辞，给出停止订阅的操作方法。
- C、D：屏幕亮度和耳机电量信息。

先自己判断哪篇更适合回答，再看程序的两个排序。排序反转由模型实际输出决定，代码没有规定 A、B 的得分或先后。

本机实测：向量分数 **A 0.762836 > B 0.589417**，重排分数 **B 2.900497 > A 1.998149**。
实测汇总与对照实验见 [验收记录](./VERIFICATION.md)。

## 真正发生的调用链

```text
候选原文 → BGE embedding → 文档向量 → Qdrant 本地内存库
Query + 检索前缀 → 同一个 BGE embedding → query 向量
query 向量 → Qdrant 余弦检索 → top-k 候选及向量分数
(原始 Query, 每篇候选原文) → BGE reranker → 新分数 → 重新排序
```

| 名词 | 在这里负责什么 |
|---|---|
| Embedding（向量表示）模型 | 把文字编码成向量，通常希望语义相近的内容距离更近 |
| 向量数据库 Qdrant | 存储向量，根据余弦相似度找近邻；本例在进程内存中运行 |
| Bi-encoder（双编码器） | Query 与文档分别编码；文档向量可以预先计算，适合快速召回 |
| Rerank（重排序） | 对已经召回的候选重新判断相关性 |
| Cross-encoder（交叉编码器） | 本例的重排方式：把问题与一篇文档放在一起，让模型联合计算相关性 |

**向量检索通常也是语义检索，不等于字面匹配。** 有限维度的独立向量未必充分保留条件、主体等细节；交叉编码器能在这一轮同时读取问题和原文。
这也不是绝对的“相似度 vs 语义”分工：两类模型都受训练目标、模型能力和数据分布影响。

两种分数不能直接比较数值大小：

- `vector_score`：Qdrant 的余弦相似度，本例越大越靠前。
- `rerank_score`：重排模型的原始 logit，允许负数，越大越靠前；不是“答对概率”。
- `inversions`：严格排序反转的文档对。`["A", "B"]` 表示向量分数 A > B，同时重排分数 B > A。

## 改一改再感受

替换问题，观察“功能介绍”的文档是否更有用：

```powershell
practice/rerank-demo/.venv/Scripts/python.exe practice/rerank-demo/demo.py --query "苹果手机的自动续费功能是什么？"
```

只召回第一篇，观察 rerank 的边界：

```powershell
practice/rerank-demo/.venv/Scripts/python.exe practice/rerank-demo/demo.py --top-k 1
```

**Rerank 只能重排收到的候选，找不回没被召回的 B。** 增大候选数量与重排质量是两个不同问题。

也可以编辑源码中 `DEFAULT_CASES` 的 query 和文档，或使用 `--cases 路径` 加载自己的 JSON；自定义样例不保证反转。
`--check` 检查样例的 `expected_inversion`（本例为 A、B）是否严格反转；没有声明时检查任意一对。
未出现会返回失败；默认模式如实展示结果。预期标签只用于结果验收，不参与模型打分或排序。
反转只证明顺序改变，是否变好仍需人判断答案和适用条件，不能只看分数。

## 复现依据与限制

- 模型 ID 和具体 revision 固定在 [demo.py](./demo.py)；可用 `--output 文件路径` 导出包版本、输入原文及两阶段完整分数。
- BGE 中文 query 按维护方说明加入检索前缀，文档不加；reranker 接收不加前缀的原始 query。
- 教学样例经过挑选，只用于展示一次真实反转，不是准确率、性能或生产质量评估。
- Qdrant 本地内存模式不验证远程部署、近似索引误差或大规模检索性能；本例文本很短，模型最大输入长度为 512 tokens。
- 真实验收记录见 [VERIFICATION.md](./VERIFICATION.md)。

参考：[Sentence Transformers 检索与重排](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html)、[BGE 中文 embedding](https://huggingface.co/BAAI/bge-small-zh-v1.5)、[BGE reranker](https://huggingface.co/BAAI/bge-reranker-base)、[Qdrant Python 本地模式](https://github.com/qdrant/qdrant-client#local-mode)。

## 实测结果与对比

Query：**怎么关闭苹果手机的自动续费？**（2026-10-25 真实模型实测）

| 候选内容 | 向量检索分数 | Rerank 分数 |
|---|---:|---:|
| A：介绍自动续费功能，没有关闭方法 | **0.762836** | 1.998149 |
| B：说明如何取消订阅 | 0.589417 | **2.900497** |

顺序从 **A > B** 变成 **B > A**：本例中，A 贴近问题主题，B 更能回答“怎么关闭”，重排将 B 提到了前面。

向量检索通常也是**语义检索**；本例 reranker 同时读取问题与候选原文，进一步判断相关性。两列分数只能各自比较，且 rerank 不保证每次都排得更好。
