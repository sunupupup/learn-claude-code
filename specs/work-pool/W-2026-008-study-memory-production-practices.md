# W-2026-008：Memory 生产实践与生命周期治理学习

- Status: ready
- Area: Memory / Context Engineering / Reliability / Eval / Privacy / Security
- Difficulty: D2 → D3
- Discovered From: `s09_memory` 的记忆提取、召回、整理和文件替换实现
- Owner: personal
- Priority: high
- Related: [s09 Memory](../../s09_memory/README.md)、[W-2026-006](./W-2026-006-study-tool-result-compaction-and-recovery.md)、[W-2026-007](./W-2026-007-study-side-effect-tool-security.md)

## Objective

从教学版“Markdown 文件 + 索引 + LLM 选择/提取/整理”出发，研究一个可长期运行的 Memory 系统如何处理记忆的作用域、写入时机、召回质量、过期删除、冲突合并、并发一致性、隐私和失败恢复。

本任务的目标不是马上把教学代码改造成生产系统，而是能够判断：

1. 什么信息值得跨会话保存，什么信息只应留在 Run、Session 或 Context 中；
2. 何时写入、何时召回、何时整理、何时过期或删除；
3. LLM 参与记忆决策时，哪些地方必须由程序、权限和数据约束兜底；
4. 如何用 Eval、Trace 和故障实验证明记忆系统确实改善了任务，而不是制造更多噪声。

## Stable Mental Model

Memory 是一个有生命周期的知识对象，而不是聊天记录备份：

```text
候选信号
  → 提取与校验
  → 写入 / 更新
  → 建立索引
  → 按需召回
  → 注入当前 Context
  → 使用与反馈
  → 整理、过期、删除或更正
```

需要始终区分：

| 对象 | 主要作用 | 典型持久性 | 关键风险 |
| --- | --- | --- | --- |
| Context | 当前一次模型调用可见的信息 | 单次请求 | 超预算、注入、信息过时 |
| Run / Session State | 让当前任务可继续执行的状态 | Run 或 Session | 丢失步骤、审批和工具状态 |
| Memory | 未来会话仍可能有用的偏好、反馈或项目事实 | 跨会话 | 错记、过期、隐私、冲突 |
| Knowledge Base | 可查询的领域事实和来源 | 长期 | 权限、版本、溯源、更新 |

关键原则：关键业务事实和副作用状态优先放在显式 State 或权威业务系统中，不应只依赖自然语言 Memory。

## Current Teaching-Code Gaps To Investigate

### 1. 写入时机与门控

当前 `consolidate_memories()` 只按文件数阈值触发，缺少生产系统常见的多层门控：

- 时间门控：距上次整理是否达到冷却时间；
- 扫描节流：是否频繁扫描文件系统；
- 会话门控：上次整理后是否真的有足够多的新会话或修改；
- 并发门控：是否已有另一个提取或整理任务正在运行；
- 失败退避：LLM 或文件系统失败后是否延迟重试。

需要比较同步整理、stop hook 后台整理和队列任务三种方式的延迟、成本、崩溃恢复与用户可见性。

### 2. 提取窗口与评测

教学代码使用最近 10 个 Message 对象作为提取窗口，这是控制输入长度的启发式，不是通用标准。需要建立小型 Eval Set，比较不同窗口和策略对以下指标的影响：

- 重要记忆召回率：该记住的内容是否被提取并在未来正确召回；
- 记忆精确率：写入的内容是否确实来自对话，而不是模型猜测；
- 重复记忆率：是否反复生成相同事实；
- 过期记忆率：事实变化后旧记忆是否仍被使用；
- 冲突率：同一主题出现互相矛盾的记忆比例；
- Token、成本、延迟和 side-query 失败率。

评测不能只看最终回答，还要检查提取、选择、注入和后续工具行为。主观质量可以使用 LLM grader，但必须用确定性断言或人工样本校准。

### 3. 并发、原子替换与 `unlink()` 安全

当前 consolidation 的流程是“先删除旧文件，再写入新文件”。`Path.unlink()` 会直接删除文件；如果进程在删除后、写入完成前崩溃，可能造成：

- 旧记忆无法恢复；
- 只写入部分新记忆；
- `MEMORY.md` 保留已经不存在的链接；
- 多进程同时写入时互相覆盖。

需要研究并比较：

- 文件锁或单写者队列；
- 临时目录完整写入后再原子替换；
- 索引与正文的版本号、内容 Hash 和备份；
- 崩溃恢复、过期锁清理和幂等重放；
- 空结果、非法 JSON、部分写入和重复整理的处理方式。

#### 重点待办：Memory 写入崩溃安全与原子化发布

本章验收题暴露出的核心场景是：consolidation 已经用 `unlink()` 删除旧文件，但新集合尚未完整写入时进程崩溃。该场景单独作为本 Work Pool 的重点练习，要求比较以下两种思路：

```text
逐文件移动旧集合到 temp
    vs.
在 staging 目录完整构造新集合后一次性发布
```

推荐优先研究后者，并回答：

1. 如何让外部读取者只看到完整旧集合或完整新集合，而不是半成品；
2. 如何在新集合校验失败、空结果、部分写入或进程崩溃时保留旧集合；
3. 如何用文件锁、单写者队列或事务标记避免多个整理任务互相覆盖；
4. 如何在重启后判断应回滚、继续发布，还是清理已提交但未清理的 backup；
5. 如何验证 `MEMORY.md` 与正文文件始终来自同一个版本。

阶段性目标：写出“获取锁 → 创建 staging → 写入并校验 → 原子发布 → 保留 backup → 清理 backup”的伪代码，并设计至少一个删除后崩溃的故障注入实验。

### 4. 更新、冲突和删除

当前同一个 slug 会覆盖文件，已有描述只是给 LLM 的软性去重提示。需要设计明确的 Memory Record 字段，例如：

```text
memory_id
scope / owner / tenant
type
content
source
created_at / updated_at
confidence
valid_from / expires_at
visibility / sensitivity
supersedes / superseded_by
```

重点研究：

- 用户明确更正偏好时，如何 supersede 旧记忆；
- 两条记忆冲突时，如何按来源、时间、范围和置信度决定优先级；
- 用户要求“忘记”时，如何删除正文、索引、缓存、备份和派生数据；
- 过期记忆是软删除、归档还是永久删除；
- 不同用户、项目和租户之间如何隔离。

### 5. 记忆内容的安全性与隐私

记忆正文也是不完全可信的模型输入，不能自动视为系统指令。需要覆盖：

- Memory 中的 Prompt Injection；
- 敏感信息、凭据和个人数据的脱敏与加密；
- 记忆读取权限和租户边界；
- 用户查看、修改、导出和删除记忆的能力；
- 审计谁在何时写入、读取或修改了哪条记忆；
- 数据保留期限、备份保留期限和删除证明。

## Learning Plan

### Track A：作用域与生命周期

画出 Run、Session、Memory、Knowledge Base 的边界，并为 `s09_memory/code.py` 中每个目录和函数标注其作用域。

### Track B：提取与召回策略

用不同对话窗口、不同记忆数量和冲突样本构造 Eval Set，比较召回质量、成本和延迟。

### Track C：一致性与恢复

围绕 `write_memory_file()`、`_rebuild_index()`、`consolidate_memories()` 和 `unlink()` 设计崩溃点，写出安全的“准备—校验—提交—恢复”伪代码。

### Track D：过期、冲突与删除

设计 TTL、用户更正、项目结束、敏感信息删除和跨租户隔离的策略，并说明每条策略的权威来源。

### Track E：观测与生产评测

定义 Memory 写入、召回、注入、整理和删除的 Trace/Metric，区分“模型输出看起来正确”和“记忆生命周期正确”。

## Failure-Injection Exercises

至少覆盖以下实验：

1. LLM 返回非法 JSON、空数组、越界索引和重复索引；
2. 同一个 slug 连续写入两条互相冲突的偏好；
3. consolidation 在 `unlink()` 后、写入新文件前崩溃；
4. 两个进程同时提取或整理记忆；
5. 索引存在但目标正文文件缺失；
6. 记忆已过期但仍被召回；
7. 记忆正文包含恶意指令或敏感数据；
8. 记忆数量和正文长度超出 Context 预算。

每个实验都要记录：可观察症状、主要故障层、数据是否可恢复、用户是否受到影响、如何避免再次发生。

## Boundaries

- 先研究文件型 Memory 的生命周期，不先引入向量数据库、知识图谱或复杂 Agent Framework；
- 不把 LLM 选择结果当作授权结果，权限必须由程序和数据层控制；
- 不把保存 transcript 等同于可恢复的 Durable Execution；
- 不在 Work Pool 阶段直接修改教学代码的业务逻辑；
- 与 W-2026-006 重点交叉 Tool Result 恢复，与 W-2026-007 重点交叉副作用工具安全，但本任务聚焦 Memory 生命周期。

## Start Trigger

完成 s09 基础的 `select_relevant_memories()`、`load_memories()`、`extract_memories()` 和 `consolidate_memories()` 代码学习后，再明确启动本任务。

## Success Criteria

完成后应能：

1. 解释 Memory 与 Context、State、Knowledge Base 的边界；
2. 画出从候选提取到召回、整理、过期和删除的完整生命周期；
3. 写出带时间门控、并发控制、原子替换和失败恢复的伪代码；
4. 为记忆召回、重复、过期、冲突、成本和延迟设计 Eval；
5. 说明 `unlink()`、空结果、部分写入和索引不一致的风险与恢复策略；
6. 给出隐私、租户隔离、Prompt Injection 和用户删除权的处理方案；
7. 明确哪些结论仍需要通过实验、Trace 或真实项目资料验证。
