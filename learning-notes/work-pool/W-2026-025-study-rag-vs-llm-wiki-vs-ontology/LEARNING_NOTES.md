# W-2026-025 学习笔记：RAG、GraphRAG、LLM Wiki 与 Ontology

## 范围与状态

2026-09-19 正式启动；2026-09-20 用户确认本章学习结束，归档现有笔记与实验。学习完成不等于全部真实模型调用或生产效果已验证。
范围、顺序与验收以 [C-2026-004](../../../specs/changes/C-2026-004-study-rag-vs-llm-wiki-vs-ontology.md) 为准。
详细顺序、主读/对照资料、每节验收与调研限制以 [LEARNING_PATH.md](LEARNING_PATH.md) 为主要来源。

## 用户原始需求

> 找一下，应该有个 关于 rag 、 等相关内容的了解和学习
> 我们先开始那一章的学习
> 而且应该会有很多概念 rag、graphrag\openwiki 等

后续用户明确要求“慢慢学习”，先调研学习路线，沿“为什么出现、解决什么问题、有什么不足、出现哪些改进”阅读官方文档与博客并做对比。

OpenWiki 已找到高匹配候选 `langchain-ai/openwiki`，官方定位和证据见学习路线单元 6；用户是否指该项目仍待确认。LLM Wiki 模式和 OpenWiki 产品分开学习。
启动前观点完整保留在 [STARTING_CONTEXT.md](STARTING_CONTEXT.md)，不视为用户已经掌握或已证实的结论。

## 基础与关联

- [LLM Wiki](LLM_Wiki.md)、[Ontology](Ontology.md)：对应主题入口和用户笔记。
- [GraphRAG](RAG扩展-GraphRAG.md)、[Agentic RAG](RAG扩展-Agentic%20RAG.md)：扩展机制与学习记录。

- [RAG 入口](RAG.md)：准备数据、使用数据、维护数据的简明链路与知识点索引。

- [RAG 资料更新与删除](RAG资料更新与删除.md)：从旧片段残留的 Demo 开始，逐步学习修改、删除和失败处理；独立对话继续。

- [文档解析、清洗与切块](文档解析清洗与切块.md)：保留用户问题，按“完整技术链路 → 问题与实现办法”组织；关键结论明确标记，省略无关的流程和状态说明。

- [最小 RAG 实操方案](最小RAG实操方案.md)：保留最初方案背景；已改为顶部参数、顺序执行的简单版本，运行入口见 [实验 README](experiments/rag-basic/README.md)，尚未调用真实模型。
- [RAG 数据准备与入库](RAG数据准备与入库学习笔记.md)：单独展开解析、清洗、切块、来源、向量化与写入；[入库实验](experiments/rag-basic/ingest_demo.py)默认只预览，已用三份资料得到 7 块，用户实操与理解待确认。

- [现有 RAG Demo](../../../projects/rag-agent-demo/README.md)：后续观察检索结果如何返回模型的本地基线；本轮未运行。
- [W-002 笔记](../W-2026-002-study-llm-runtime-foundations/LEARNING_NOTES.md)：已有 Token、模型与运行时讨论；不能推定已掌握检索用文本向量。
- [W-013 Memory](../../../specs/changes/C-2026-005-study-memory-production-practices.md)：后续连接跨会话保存、更新与召回。

## 术语速查（保留启动时状态，当前以模块笔记为准）

| 术语 | 中文与所属层次 | 本轮状态 |
| --- | --- | --- |
| RAG / Retrieval-Augmented Generation | 检索增强生成；应用的知识访问与生成链路 | 待复述 |
| Context | 上下文；当前一次模型调用可见的输入 | 待辨析与模型参数的区别 |
| GraphRAG | 图增强检索生成；知识访问层，需区分泛称与具体实现 | 待学习 |
| LLM Wiki | 用大语言模型维护 Wiki 知识页的组织模式；知识管理层 | 待学习 |
| KG / Knowledge Graph | 知识图谱；实体和关系的知识表示层 | 待学习 |
| Ontology | 本体；概念、关系及语义约束的表示层 | 待学习 |

## 证据与下一步

2026-09-19 已打开 [RAG 原论文摘要](https://arxiv.org/abs/2005.11401)、[Microsoft GraphRAG 仓库](https://github.com/microsoft/graphrag)、[Karpathy LLM Wiki 原文](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)；属于文献入口核对，不代表已完成全文、源码或性能核验。

后续按具体问题选学，不再自动追加本章课程。归档时保留用户的原始笔记和历史实验说明。

归档验证：现有 Python 文件通过语法检查；历史本地实验结果见各模块。真实模型与生产质量不作已验证声明。Agentic RAG 的历史 Demo 当前不在工作目录，本次仅保存对应笔记；Ontology 入口中的 Demo 路径仍为计划，未声称已交付。
