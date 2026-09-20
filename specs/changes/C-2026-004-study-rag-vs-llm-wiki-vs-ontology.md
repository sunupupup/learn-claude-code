# C-2026-004：RAG、GraphRAG、LLM Wiki 与 Ontology 学习

- Status: done
- Completed: 2026-09-20（用户确认本章学习结束，归档已有学习成果）
- Origin: W-2026-025
- Started: 2026-09-19
- 启动依据：用户明确要求开始 RAG 等相关主题学习。
- 学习主记录：[LEARNING_NOTES.md](../../learning-notes/work-pool/W-2026-025-study-rag-vs-llm-wiki-vs-ontology/LEARNING_NOTES.md)
- 原任务观点和候选资料：[历史任务卡](../../learning-notes/work-pool/W-2026-025-study-rag-vs-llm-wiki-vs-ontology/STARTING_CONTEXT.md)，仅作待核验输入。

## 范围与学习方式

采用混合线：D1 基础概念 → D2 对比与小实验 → 按需讨论 D3 生产取舍。一次只推进一个问题，用户复述并确认后再沉淀学习结论。

2026-09-19 用户要求先调研“问题 → 解决办法 → 局限 → 改进”的学习路线，并以官方文档、论文及博客做对比。详细学习路径和阅读清单统一维护在 [LEARNING_PATH.md](../../learning-notes/work-pool/W-2026-025-study-rag-vs-llm-wiki-vs-ontology/LEARNING_PATH.md)。先建立最小 RAG 与评测基础，再比较检索改进、图、Wiki、本体及其他路径，不按名词热度排序。

OpenWiki 已核验到高匹配候选 `langchain-ai/openwiki`，与 LLM Wiki 模式分别处理；是否正是用户所指仍待确认。源码实验前再固定版本。

首节只辨析模型参数中的知识、外部文档、检索结果与当前上下文。以本仓库 RAG Demo 为后续源码基线，外部源码仅在进入对应小节时选择并固定版本。

## 验收与产出

- 用户能画出检索到生成的数据流，说明知识在何处保存、何时更新。
- 能区分 RAG、GraphRAG、Wiki、知识图谱和本体的关注点，解释可组合关系。
- 用同一组小资料对比至少两种组织/检索方式，保留引用、无答案或过期事实反例及真实实验结果。
- 形成有证据的对比表与场景选择依据；原卡的“RAG 结构性无法积累知识”不再作为验收前提。
- 能指出至少一个权限、数据更新、错误传播或成本风险。

## 约束与当前状态

- 收尾记录：[I-2026-002](../implementation/I-2026-002-rag-knowledge-management-learning.md)。以下保留过程记录，不代表所有计划实验已完成或生产效果已验证。

- 2026-09-20 新增 GraphRAG、Agentic RAG 两篇扩展入口及最小 Python 实验，入口见 [RAG.md](../../learning-notes/work-pool/W-2026-025-study-rag-vs-llm-wiki-vs-ontology/RAG.md)。本地图检索、模拟工具循环及边界对照通过；真实模型未调用，未复现微软完整 GraphRAG。

- 用户选择“看到哪里学到哪里”，暂不批量展开五篇知识文档；本轮仅新增 [文档解析清洗与切块](../../learning-notes/work-pool/W-2026-025-study-rag-vs-llm-wiki-vs-ontology/文档解析清洗与切块.md)，完成官方资料初步调研，未修改实验代码或验证生产效果。

- 用户追加要求单独学习数据准备阶段；已新增 [入库模块笔记](../../learning-notes/work-pool/W-2026-025-study-rag-vs-llm-wiki-vs-ontology/RAG数据准备与入库学习笔记.md)与独立 Python 实验，默认仅预览，不改动最小 RAG 主流程。已预览 7 个片段，真实模型与检索质量待验证。

- 不构建生产系统、不安装重量级数据库、不启动付费调用；不扩展成完整 Memory 调研。
- 已完成启动上下文检查与学习路线资料调研；概念掌握、固定版本源码和运行实验尚未验收。
- 原卡中的 RAG 无状态、Wiki 固定容量、GraphRAG 等于事实验证等判断需重新核验，不沿用作事实。
- 用户已有 W-003 删除任务卡及新增 Change/学习笔记的未提交改动，保留不动。
