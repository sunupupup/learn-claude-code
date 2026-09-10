# W-2026-022：RAG vs LLM Wiki vs Ontology — 知识管理三范式对比

- Status: someday
- Area: Knowledge Management / RAG / LLM Wiki / Ontology / Knowledge Graph / Agent Memory
- Difficulty: D2（概念辨析和对比实验）→ D3（生产级混合架构设计）
- Discovered From: 2026-09 对三个近期高频词的关注；Karpathy LLM Wiki 模式引发的 RAG 替代讨论
- Owner: personal
- Priority: medium

## Objective

建立 RAG、LLM Wiki、Ontology 三种知识管理范式的比较框架，理解它们的本质差异、各自适用边界、以及生产系统中如何互补组合。

## 核心概念速览

### RAG（Retrieval-Augmented Generation）

**一句话**：查询时从向量库检索相关片段，注入 LLM 上下文生成回答。

- 知识以原始文档形式存储，经 embedding 索引
- 每次查询重新检索、重新合成，无持久化知识积累
- 适合大规模、动态、多用户场景
- 核心瓶颈：chunk 粒度丢失结构、多跳推理弱、无法跨查询积累理解

```text
[用户查询] → embedding → 向量相似度搜索 → top-k chunks → LLM 生成回答
                                                          ↑ 每次从零合成
```

### LLM Wiki（Karpathy 模式）

**一句话**：LLM 将原始资料编译为持久化的互相链接的 Markdown 知识页，查询时直接阅读已编译产物。

- Andrej Karpathy 2025 年提出的个人知识管理模式
- 核心区分：**编译时知识**（compile-time）vs RAG 的**查询时知识**（query-time）
- 新资料到达时，LLM 读取 → 提取 → 整合进现有 wiki 页 → 更新交叉引用 → 标记矛盾
- 知识随时间**复合增长**（compound），不是每次查询后遗忘
- 适合个人/小团队、知识量在 50k-100k token 以内的场景
- 核心瓶颈：超过上下文窗口时失效，不适合大规模多用户动态数据

```text
[新资料] → LLM 读取 → 提取概念 → 更新/创建 wiki 页面 → 维护交叉引用
[查询] → 读取已编译的 wiki 页 → LLM 基于已合成知识回答
                                 ↑ 知识已预先编译，查询成本低
```

### Ontology（本体 / 知识图谱治理层）

**一句话**：定义实体类型、关系约束和层级分类的形式化 schema，为知识提供结构和治理。

- 不是检索机制，而是知识的**结构和语义约束层**
- 确保实体分类一致、关系类型受控、知识可审计
- 与 Knowledge Graph 配合：Ontology 定义 schema，KG 存储实例
- 适合企业级、需要精确性/可解释性/合规审计的场景
- 核心瓶颈：前期 schema 设计成本高，维护需要领域专家

```text
Ontology（schema）→ Knowledge Graph（实例）→ GraphRAG（图遍历检索）
                                                ↑ 路径可追溯、事实可验证
```

## 三范式本质差异

| 维度 | RAG | LLM Wiki | Ontology / KG |
|------|-----|----------|---------------|
| **核心隐喻** | 图书馆员（每次现查） | 编辑（编译维护百科） | 分类学家（定义结构） |
| **知识处理时机** | 查询时（query-time） | 摄入时（compile-time） | 设计时（design-time） |
| **智能所在位置** | 短暂的查询事件 | 持久的编译产物 | 形式化的 schema 约束 |
| **知识是否积累** | 否，每次从零合成 | 是，复合增长 | 是，但需人工/LLM 维护 |
| **存储形态** | 向量索引 + 原始 chunk | Markdown 文件 + 交叉链接 | 图数据库 + 本体定义 |
| **可读性** | 低（chunk 碎片） | 高（人类可读 wiki 页） | 中（需理解 schema） |
| **规模上限** | 几乎无限 | 50k-100k token（受上下文窗口限制） | 取决于图数据库 |
| **多跳推理** | 弱（依赖 chunk 重叠） | 中（依赖预编译的交叉引用） | 强（图遍历天然支持） |
| **适合场景** | 大规模、动态、多用户 | 个人/小团队、深度研究 | 企业级、精确性/审计要求高 |
| **基础设施** | 向量数据库 + embedding 模型 | Markdown 文件 + LLM | 图数据库 + 本体编辑器 |
| **维护成本** | 低（数据变更重新 index） | 中（每次新资料触发编译） | 高（schema 演进 + 实例治理） |

## 个人理解与判断

### 对 RAG 的理解

RAG 在 2023-2024 年被过度神话了。很多团队把它当银弹——"有文档？上 RAG"——但忽略了一个根本问题：**RAG 是无状态的**。它每次查询都从零开始理解你的问题，从零开始拼凑答案。这就像一个失忆的研究员，每天早上忘记昨天做过的所有研究，重新去图书馆翻书。

RAG 真正强的地方是**规模和新鲜度**：当你有几十万份文档、内容每天在变、几百个用户同时用的时候，RAG 是唯一现实的选择。向量检索的"模糊匹配"在这种场景下是优势——用户的提问方式千变万化，embedding 的语义相似度比精确匹配更鲁棒。

但 RAG 最被低估的弱点是**多跳推理**。"A 文档说了 X，B 文档说了 Y，结合起来能推出 Z"——这对 RAG 来说极其困难，因为 chunk 切割天然破坏了这种跨文档的逻辑链。GraphRAG 试图解决这个问题，但代价是引入了知识图谱的全部复杂度。

我的判断：RAG 不会消失，但它会从"默认方案"退化为"大规模检索层"，上面需要叠加编译层（Wiki）或结构层（KG）才能真正好用。

### 对 LLM Wiki 的理解

Karpathy 的 LLM Wiki 模式让我想到一个类比：**RAG 是解释型语言，LLM Wiki 是编译型语言**。

解释型每次运行都重新解析源码（= 每次查询都重新检索合成），编译型提前编译成二进制（= 摄入时就把知识编译成 wiki 页）。编译型在运行时更快、更稳定，但编译过程本身要花时间，而且源码一变就要重新编译。

这个类比也暴露了 LLM Wiki 的核心风险：**编译器（LLM）本身可能引入 bug**。RAG 只是检索和拼接，出错了换个 chunk 策略就行；但 Wiki 的编译过程涉及理解、摘要、交叉引用、矛盾检测——每一步都可能引入幻觉或遗漏。而且这些错误会被"编译"进 wiki，后续查询全部基于错误的编译产物。arXiv 论文里的 Error Book 机制就是在试图解决这个问题。

另一个关键洞察：LLM Wiki 的价值不在于"更好的检索"，而在于**知识的复合增长**。读了 100 篇论文后，wiki 里不是 100 个独立摘要，而是一个已经交叉引用、标记矛盾、逐步合成的知识体。这种复合效应是 RAG 结构性做不到的——RAG 没有可写入的持久层来积累理解。

我的判断：LLM Wiki 对个人知识工作者和小团队是革命性的，但企业级落地还需要解决规模、多用户协作、编译质量保证三个硬问题。当前最实际的用法是 **wiki-first, RAG-fallback**——核心知识编译成 wiki，长尾内容走 RAG。

### 对 Ontology 的理解

Ontology 是三者中最"古老"的概念——语义网时代（2000 年代）就有 OWL、RDF、SPARQL 这套技术栈。当时它失败了，因为**手工构建和维护本体的成本太高**，远超大多数场景的收益。

但 LLM 改变了这个经济学。现在 LLM 可以半自动地从文本中抽取实体和关系、建议 schema、检测不一致——这让 Ontology 的构建成本大幅下降。TigerGraph 的实践已经验证了 "Ontology-first, LLM-extract" 的模式。

Ontology 在三者中扮演的角色最独特：它不负责检索，也不负责知识编译，它负责的是**知识的结构正确性和治理**。没有 Ontology，RAG 检索到的"Phase III trial"可能有 17 种不同的实体类型互相矛盾；没有 Ontology，Wiki 编译时可能把同一个概念拆成了三个不同的页面。

我的判断：Ontology 的价值与知识的**精确性要求**正相关。个人学习笔记不需要它；企业级知识库、医疗/法律/金融领域、多 Agent 系统的事实验证——这些场景下 Ontology 是必须的，不是可选的。

### 对三者关系的整体判断

三者不在同一个层次竞争，而是分属不同的关注点：

```text
Ontology  = 知识的 "类型系统"（什么是合法的实体和关系）
LLM Wiki  = 知识的 "编译器"（把原始资料编译为可直接使用的产物）
RAG       = 知识的 "搜索引擎"（在大规模未编译数据中找到相关内容）
```

用编程类比：Ontology 是 TypeScript 的类型定义，LLM Wiki 是 tsc 编译器，RAG 是 grep/ripgrep。你不会说"TypeScript 和 grep 哪个更好"——它们解决的是不同问题。

当前行业的噪音主要来自把它们放在同一维度比较（"LLM Wiki 比 RAG 好"），而成熟的架构思维应该是问"我的场景需要哪几层，每层用什么"。

## 它们不是互斥的——生产级混合架构

关键认知：**三者解决的是不同层次的问题，生产系统通常需要组合使用。**

```text
┌─────────────────────────────────────────────────┐
│              用户 / Agent 查询                    │
├─────────────────────────────────────────────────┤
│  LLM Wiki 层：已编译的核心知识、概念页、摘要      │ ← 高频 & 核心知识
│  （快速、token 省、知识复合增长）                  │
├─────────────────────────────────────────────────┤
│  RAG 层：大规模原始文档的语义检索                  │ ← 长尾 & 动态知识
│  （覆盖 wiki 未编译到的内容）                     │
├─────────────────────────────────────────────────┤
│  Ontology / KG 层：实体关系验证、事实校验          │ ← 精确性 & 治理
│  （确保答案结构正确、可审计、可追溯）              │
└─────────────────────────────────────────────────┘
```

实际组合策略：

1. **Wiki-first, RAG-fallback**：先查 wiki 编译产物，wiki 没覆盖到的再走 RAG 检索
2. **RAG + KG 验证**（GraphRAG）：向量检索找候选，知识图谱验证事实关系
3. **Wiki + Ontology**：wiki 页面遵循本体 schema，确保概念分类一致
4. **全栈**：Wiki 做核心知识编译 → RAG 做长尾检索 → KG 做事实验证 → Ontology 做治理

## 与 Agent 系统的交叉点

这个主题与本仓库的 Agent 学习高度相关：

| 交叉点 | 说明 | 相关 Work Pool |
|--------|------|---------------|
| Agent 长期记忆 | LLM Wiki 本质上是 Agent 长期记忆的一种实现 | W-2026-008 |
| Context 压缩 | Wiki 的预编译 = 极端的 context compaction | W-2026-006、W-2026-012 |
| Tool 结果处理 | Agent 的 tool 结果可以编译进 wiki 而非丢弃 | W-2026-006 |
| 知识检索 Tool | RAG、wiki 查询、图遍历都可以是 Agent 的 Tool | W-2026-010 |
| 可观测性 | Ontology 提供的可追溯性对 Agent 审计至关重要 | W-2026-010、W-2026-021 |

## 关键资源

### Karpathy LLM Wiki 原始材料

- [Karpathy 原始 Gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — 模式定义、分层结构、工作流
- [microsoft/llmwiki](https://github.com/microsoft/llmwiki) — VS Code 扩展实现，带 MCP server
- [arXiv: Retrieval as Reasoning — LLM-Wiki](https://arxiv.org/html/2605.25480) — 学术论文，在 HotpotQA/MuSiQue 上超越 GraphRAG
- [ROBOCO 72-Run Benchmark](https://roboco.io/en/posts/karpathy-llm-wiki-72-run-benchmark/) — 实测：Wiki 比 vanilla RAG 省 54% token、快 39%

### 对比分析

- [Atlan: LLM Wiki vs RAG Knowledge Base](https://atlan.com/know/llm-wiki-vs-rag-knowledge-base/) — compile-time vs query-time 框架
- [LinkedIn: LLM Wiki Isn't a Better RAG](https://www.linkedin.com/pulse/llm-wiki-isnt-better-rag-its-different-kind-object-entirely-zhang-snmwc) — "不是更好的 RAG，而是完全不同的对象"
- [Falconer: Enterprise LLM Wiki](https://falconer.com/guides/enterprise-llm-wiki-karpathy/) — 企业级扩展 Karpathy 模式

### Ontology / Knowledge Graph

- [Knowledge Graph vs Vector Database vs Ontology (2026)](https://venkatapagadala.com/guides/graph-types-for-ai-agents) — 六种图结构对比
- [TigerGraph: Knowledge Graph with LLMs](https://www.tigergraph.com/blog/how-to-build-knowledge-graph-with-llms-for-enterprise-ai/) — Ontology-first 的 KG 构建
- [Microsoft GraphRAG](https://github.com/microsoft/graphrag) — 图增强检索生成

### Beyond RAG

- [Medium: Beyond RAG — Karpathy's LLM Wiki](https://levelup.gitconnected.com/beyond-rag-how-andrej-karpathys-llm-wiki-pattern-builds-knowledge-that-actually-compounds-31a08528665e) — 知识复合增长的价值

## Core Questions

- RAG 的"每次从零合成"在什么场景下是优势而非劣势？
- LLM Wiki 的 50k-100k token 上限在实践中如何突破？分层 wiki？分域 wiki？
- Ontology 的前期 schema 设计成本能否通过 LLM 自动化降低？
- Wiki 编译过程中的错误（幻觉、遗漏、矛盾）如何检测和修复？
- 个人学习场景下，LLM Wiki 模式是否比现在的 LEARNING_NOTES.md 更有效？
- Agent 的长期记忆应该选择哪种范式？还是混合？
- GraphRAG 是否已经是 RAG + Ontology 的最佳实践，还是仍有其他组合？
- microsoft/llmwiki 的 MCP server 实现值不值得作为工具集成到学习工作流中？

## Recommended Learning Order

1. 精读 Karpathy 原始 Gist，理解 Raw → Wiki → Schema 三层架构
2. 跑一遍 microsoft/llmwiki VS Code 扩展，体验 compile → query 工作流
3. 读 Atlan 对比文章，建立 compile-time vs query-time 的心智模型
4. 读 ROBOCO benchmark，理解 wiki-first 在什么任务上有优势
5. 读 arXiv LLM-Wiki 论文，理解 Error Book 和 agent-native retrieval
6. 读 Knowledge Graph vs Vector Database vs Ontology 对比，理解六种图结构
7. 尝试对本仓库的某个学习主题（如 s15 Agent Teams）用 LLM Wiki 模式重新组织笔记
8. 对比重组前后的查询效果和知识密度

## Expected Output

- 一份三范式对比矩阵（已在本文档初步完成）
- 一个小型实验：用 LLM Wiki 模式重组本仓库某主题的笔记，对比前后效果
- 一份 "何时选择什么" 的决策树
- 对 microsoft/llmwiki 的简要评估：是否值得集成到日常学习工作流

## Success Criteria

完成后应能够：

1. 用一句话准确区分三种范式的核心差异
2. 判断给定场景应优先选择哪种范式或组合
3. 解释 LLM Wiki 的 "知识复合增长" 为什么 RAG 结构性做不到
4. 知道 Ontology 在 Agent 系统中扮演什么角色

## Why Deferred

当前主线学习仍在 Agent 编排和 Runtime 阶段（s17+），RAG/Wiki/Ontology 属于知识管理层，与当前主线正交。标记为 someday，有空时可以快速做一轮概念对比和小实验。

## Start Trigger

- 用户明确说"开始 W-2026-022"；
- 或在学习 Agent Memory（W-2026-008）时自然需要对比知识管理方案；
- 或想尝试用 LLM Wiki 模式改进本仓库的笔记组织。

## Boundaries

- 不构建生产级 RAG/KG 系统，只做概念对比和小规模实验
- 不重复 W-2026-008 的 Agent Memory 完整调研
- 不安装重量级图数据库，如需实验优先用轻量方案

## Related

- [`W-2026-008：Memory 生产实践`](./W-2026-008-study-memory-production-practices.md)
- [`W-2026-006：Tool Result 压缩与恢复`](./W-2026-006-study-tool-result-compaction-and-recovery.md)
- [`W-2026-012：Reactive Context Compaction`](./W-2026-012-study-production-reactive-context-compaction.md)
- [`W-2026-010：Skill 工程化与可观测性`](./W-2026-010-study-agent-skill-engineering-observability.md)
