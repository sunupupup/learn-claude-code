# C-2026-002：LLM Runtime 基础——Token、Prompt、生成与缓存

- Status: active
- Area: LLM Runtime / Tokenizer / Inference / Cache / Agent Foundation
- Discovered From: 用户在 Agent 生产级学习规划中发现 Token 编码、Prompt 处理、Token Cache 与模型生成链路缺少独立主线
- Owner: personal
- Priority: high
- Related: [W-2026-001 总路线](../work-pool/W-2026-001-agent-engineering-master-learning-roadmap.md)、[W-2026-027 后训练与严格 JSON](../work-pool/W-2026-027-study-strict-json-output-post-training.md)、[W-2026-004 Tool Result 恢复](../work-pool/W-2026-004-study-tool-result-compaction-and-recovery.md)、[W-2026-012 Skill 可观测性](../work-pool/W-2026-012-study-agent-skill-engineering-observability.md)、[W-2026-009 Context 治理](../work-pool/W-2026-009-study-system-prompt-production-context-governance.md)


## 本次启动与执行状态

- Origin: W-2026-002；Started: 2026-09-13；用户明确要求执行 PROMPT_4 并开始本任务。
- 主模式：混合线，按通用理论 → 固定版本输入观察 → 最小生成/缓存实验 → 失败诊断推进。
- 当前仅启动第 1 小节「字符、词、字节与 Token」，先保留用户判断，再校准，不预填答案。
- 首轮采用概念观察方案，固定输入为 `ABC`、` ABC`（首字符为空格）、`你好`、`print("hi")`。不使用 Mock Token 数冒充真实 Tokenizer 结果。
- Tokenizer、模型、Chat Template、推理 Runtime 的具体版本尚未选定；在相关实验运行前通过 Context7 与官方资料核验并固定。当前无运行证据。
- 学习过程与掌握状态的唯一来源：[LEARNING_NOTES.md](../../learning-notes/work-pool/W-2026-002-study-llm-runtime-foundations/LEARNING_NOTES.md)。下文保留原卡的完整目标、范围与验收约束。
- 启动只读基线：HEAD `5460c0e23c14887c28e37000a02f9b96d6e0d619`；检查了 s01 调用循环、s08/s10 笔记与相关 Work Pool。specs/current 和 specs/decisions 当前无文件；现有 C/I-2026-001 为已完成的 s07 资源加载，未发现冲突。
- 用户已有改动：AGENTS.md、requirements.txt、s19_mcp_plugin/LEARNING_NOTES.md；未跟踪的 code_http_mcp.py、code_http_mcp_sdk.py。本任务不改动这些文件。
- 建档验证：检查迁移后的相对链接与文档 diff；没有运行代码、安装依赖或调用模型。验收尚未开始，不创建完成记录。

## Objective

建立 Agent 工程师必须掌握的 LLM Runtime 基础：文本怎样变成 Token，Chat Prompt 怎样被序列化和输入模型，模型怎样逐 Token 生成输出，推理 Runtime 怎样使用 Prefill、Decode 和 KV Cache，以及这些机制怎样影响 Agent 的上下文、延迟、吞吐、成本和 Tool Calling。

本任务是 W-2026-001 两套路线的**必修前置基础线**。它解释模型推理机制，但不把学习目标扩张为完整的模型训练或 CUDA 优化工程。

## Problem Statement

当前 Agent 章节已经能解释模型调用、Tool Use、Context、Error Recovery 和 Agent Loop，但如果缺少以下基础，生产问题很难定位：

- `ABC` 究竟被 Tokenizer 切成几个 Token；中文、空格、标点和代码为什么会产生不同的 Token 数；
- system/user/assistant/tool 消息如何通过 Chat Template 变成模型真正看到的序列；
- “模型理解 Prompt”为什么更准确地说是基于上下文预测下一个 Token；
- Logit、Softmax、Temperature、Top-p 和停止条件分别位于生成链路的哪一层；
- Prefill 与 Decode 如何影响首 Token 延迟和逐 Token 延迟；
- KV Cache、Prompt/Prefix Cache、Tokenizer Cache 和应用层 Context Cache 缓存的对象及边界是什么；
- Prompt 变长、Tool Result 变大、Skill 注入或租户信息变化时，为什么会影响 Token、缓存命中、成本和安全；
- Tool Call 是模型输出，还是已经执行的动作；模型输出合法 JSON 是否等于业务操作已经安全完成。

## Stable Mental Model

```text
原始文本 / Chat Messages
  → Tokenizer：文本切成 Token
  → Token ID：词表中的整数编号
  → Embedding + Position：变成模型可计算的向量
  → Transformer：Attention + FFN 处理可见上下文
  → Hidden State
  → LM Head：为词表中的候选 Token 计算 Logits
  → Sampling / Constrained Decoding：选择下一个 Token
  → 追加到上下文并重复
  → Detokenizer：还原文本或识别 Tool Call
```

Agent 的边界继续保持：

```text
模型提出 tool_use
  → Runtime 解析、Schema 校验、权限判断、必要时请求审批
  → Tool / 业务服务执行
  → tool_result 写回 Context、State、Trace
  → 模型根据新上下文决定下一步
```

模型的“理解”是训练得到的条件生成能力，不是业务数据库中的权威事实；模型生成了 Tool Call，也不代表 Tool 已执行成功。

## Terminology And Boundaries

| 术语 | 所在层 | 缓存/计算对象 | 不应混淆为 |
| --- | --- | --- | --- |
| Tokenizer / Tokenization | 输入预处理 | 文本到 Token ID 的切分与映射 | 语义 Embedding |
| Token ID | 词表表示 | 一个整数编号 | Token 的含义或概率 |
| Chat Template | 应用/模型输入适配 | role、控制 Token 和消息序列化规则 | 模型天然理解的 JSON |
| Embedding | 模型输入层 | Token ID 到向量的映射 | 生成结果 |
| Hidden State | Transformer 内部 | 结合上下文后的中间表示 | 可直接当作答案 |
| Logit | 输出头 | 每个候选 Token 的未归一化分数 | 最终概率或最终文本 |
| Decode / Sampling | 推理输出层 | 从候选分布选择下一个 Token | Tool 已经执行 |
| KV Cache | 推理 Runtime | 历史 Token 在各层 Attention 中的 Key/Value | 跨会话 Memory |
| Prompt/Prefix Cache | 推理服务或 Provider | 可复用输入前缀的预计算结果 | 任意相似 Prompt 都能命中 |
| Context Cache | Harness/应用层 | 组装后的消息、指令、Memory 或文档快照 | 模型永久记住了内容 |

本任务还要特别区分两种“编码”：

1. **Tokenization 编码**：文本 → Token ID；这是输入预处理。
2. **Position Encoding / RoPE**：把顺序信息加入模型计算；它不是把文字切成 Token。

## Learning Plan

建议按 3–4 小时/天、每周 6 天投入，完成 12 个小课题，约 2–3 周。每个小课题先理解 60–90 分钟，再做 30–60 分钟实验或独立复述。

| 顺序 | 小课题 | 实验/产出 |
| --- | --- | --- |
| 1 | 字符、词、字节与 Token | 对中文、英文、空格、标点和代码做 Token 数对照 |
| 2 | Tokenizer、词表、BPE / SentencePiece | 查看实际 Token ID；说明同一可见字符为何不一定对应一个 Token |
| 3 | Token 预算与上下文窗口 | 计算输入、输出、Tool Result、System Prompt 的预算关系 |
| 4 | Chat Template 与控制 Token | 把 system/user/assistant/tool 消息展开成模型输入序列 |
| 5 | Token ID、Embedding、Position 的关系 | 画输入层数据流，区分 ID、向量和位置信息 |
| 6 | Q/K/V、Attention 与因果 Mask | 用 2–3 个 Token 的小矩阵手算一次注意力 |
| 7 | Hidden State、Logit、Softmax | 固定 Logits，观察候选 Token 概率变化 |
| 8 | Temperature、Top-p、停止条件 | 对比采样、截断、EOS 和 `max_tokens` 的不同结果 |
| 9 | 自回归生成与流式输出 | 记录“每次只生成一个 Token，再追加回上下文”的过程 |
| 10 | Prefill、Decode、TTFT 与吞吐 | 画首 Token 和后续 Token 的计算时序 |
| 11 | KV Cache、Prompt/Prefix Cache、Context Cache | 用 `ABC → ABCD → ABCDE` 画最长公共 Token 前缀和缓存分支 |
| 12 | Tool Calling 与 Agent Loop | 区分模型输出、Runtime 校验、业务执行、Tool Result 和下一轮请求 |

## Intermediate Learning Line

在 W-2026-001 和生产专题之间增加一条“小型观测与故障实验线”，避免从理论直接跳到大型框架：

### M1：Prompt Microscope

使用一个本地 Tokenizer 或受控 Mock，输出原文、Token 列表、Token ID、Token 数量、Chat Template 展开结果和每个 section 的增量。

### M2：Generation Lab

用固定 Logits 和小矩阵模拟 Softmax、Temperature、Top-p、停止条件以及 Tool Call 结构，不依赖真实付费模型先验证控制流。

### M3：Cache Branch Lab

用 `ABC → ABCD → ABCDE`、分支到 `ABX`、回到 `ABC` 三组序列，区分：最长公共前缀、完整 Prompt、KV 片段、缓存命中和缓存失效。实验结果必须标记为 Mock/本地 Runtime 观察，不能直接冒充 Provider 行为。

### M4：Agent Measurement Lab

给现有 RAG Agent 或一个最小 Agent 增加输入 Token、输出 Token、模型耗时、Tool 耗时、总耗时、重试次数和结果状态记录。这个实验连接 W-2026-001 的 Trace/Eval 和后续 W-2026-003 的完成验证。

### M5：Failure Lab

至少观察四类失败：Tokenizer/Template 配置错误、Prompt 超长、输出截断、Tool Call 合法但业务执行失败。每类失败都要定位到 Model、Prompt、Context、Tool 或 Runtime 层。

## Cache Learning Boundary

针对用户输入 `ABC → ABCD → ABCDE`，先使用抽象 Token `t1…t5` 推演：

```text
t1 t2 t3       第一次请求：可能没有缓存
t1 t2 t3 t4    第二次请求：可能复用 t1 t2 t3，只计算 t4
t1 t2 t3 t4 t5 第三次请求：可能复用更长前缀，只计算 t5
```

但以下条件必须单独验证：

- 实际缓存按 Token，不按字符；`ABC` 不保证是 3 个 Token；
- 缓存可能要求最小长度、固定 Token Block、TTL 或有淘汰；
- 较长的 `ABCDE` 缓存不能直接当作较短 `ABC` 的完整上下文；只能在 Runtime 支持前缀片段复用时截取；
- 多轮聊天中，缓存匹配的是完整序列化前缀，通常包括 System Prompt、历史消息、控制 Token 和 Tool Schema；
- 改动前缀中的租户、用户、权限、Skill 版本或工具列表，可能使后续全部缓存失效；
- 缓存命中只能影响计算、延迟或成本，不应改变权限判断、业务状态或完成证据。

## Production Questions

每个课题都必须回答：

1. 模型实际看到的 Token 序列是什么？
2. 哪些内容属于稳定前缀，哪些内容属于动态后缀？
3. 这个缓存存储的是文本、Token ID、KV 张量，还是应用状态？
4. 缓存命中/失效会影响什么：质量、延迟、成本，还是仅影响性能？
5. 租户、权限、模型版本、Prompt 版本和敏感数据如何隔离？
6. 输出 Token、Tool Call 和 Tool 执行失败时，哪个组件负责恢复？

## Expected Output

- 一张“文本 → Token → Prompt → Transformer → Logit → 输出”的数据流图；
- 一份 Tokenizer、Chat Template、Token ID、Embedding、Logit、Decode 的术语表；
- 一份 KV Cache、Prompt/Prefix Cache、Tokenizer Cache、Context Cache 对比表；
- 一个 `ABC → ABCD → ABCDE` 和分支请求的缓存推演记录；
- 一份输入/输出 Token、TTFT、生成延迟、Tool 耗时和成本的测量表；
- 一份 Prompt 超长、输出截断、Tool Call 合法但执行失败的故障分析；
- 一段能够独立解释“模型如何处理 Prompt 并生成输出”的五分钟口头说明。

## Success Criteria

完成后应能够：

- 不看资料解释一次 Chat 请求中模型实际接收的序列；
- 用真实 Tokenizer 观察至少三种语言或代码输入的 Token 差异；
- 区分 Tokenization、Embedding、Position Encoding 和 KV Cache；
- 解释 Prefill、Decode、TTFT、吞吐和输出长度之间的关系；
- 解释模型为何是逐 Token 生成，而不是一次性写出完整答案；
- 区分模型生成的 Tool Call、Runtime 执行和业务服务最终状态；
- 为 Prompt/Context Cache 设计版本、租户、权限和失效边界；
- 用日志或 Trace 证明一次缓存命中/未命中以及一次模型或工具失败；
- 明确区分代码/实验已观察事实、通用原理和未核验的 Provider 行为。

## Source And Version Boundary

- 理论主线使用 Transformer、Tokenizer、Causal Language Model 和推理系统的原始论文或维护者文档；
- 具体 Tokenizer、Chat Template、生成接口和 Prompt Cache 行为，在任务启动时固定模型、Tokenizer、Runtime、版本和 Commit；
- 涉及代码生成、库配置或 API 文档时，按仓库要求使用 Context7，并以固定版本的官方文档为准；
- Provider 的缓存计费、最小前缀、TTL、Block 大小和命中指标不能从 Mock 或其他 Provider 推断；
- 真实模型、付费 API、GPU 下载和外部服务都不在本 Work Pool 建档阶段自动执行。

## Relationship To Existing Work

- W-2026-001 维护总路线和 8/24 周计划；本文件维护 LLM Runtime 基础的详细学习内容；
- W-2026-027 研究后训练、LoRA、严格 JSON 和约束解码；本任务只提供其所需的 Tokenizer、Chat Template、生成和解码前置知识；
- W-2026-004 研究 Tool Result 压缩与恢复；本任务解释 Token 预算和推理缓存，不重复设计业务结果压缩器；
- W-2026-009 研究多租户 Context、Prompt 治理和缓存失效；本任务先建立底层推理和缓存对象的模型；
- W-2026-012 研究 Trace/Eval；本任务的测量表和失败实验作为其输入；
- W-2026-014 研究真实 MCP 服务；本任务先解释模型输出 Tool Call 与 Runtime 执行的边界。

## 启动前背景（历史）

本任务最初登记为必修基础线；2026-09-13 用户已明确启动。正式学习前需要确定本轮使用的 Tokenizer/模型或 Mock 方案，并区分纯概念实验、本地运行观察和 Provider 行为核验。

## Start Trigger

用户明确说“开始 W-2026-002”或同等意思后启动。启动时：

- 先阅读本文件和 W-2026-001 的当前推荐线路；
- 先做 Tokenizer 与 Chat Template 的输入观察，不先下载大模型；
- 固定实验数据、版本、Token 统计口径和证据标签；
- 如需修改代码或新增实验目录，按 [Spec 工作流](../README.md) 建立对应 Change；
- 不把缓存命中作为正确性前提，也不在没有授权时调用付费模型或真实副作用 Tool。

## Non-goals

- 不要求推导完整反向传播或从零训练大模型；
- 不把 CUDA Kernel、FlashAttention、量化内核、分布式推理列为当前必修；
- 不把某一家 Provider 的 Prompt Cache 规则当作通用行业标准；
- 不用一次 Token 数下降证明 Agent 质量提升；
- 不把 KV Cache 当成跨会话 Memory 或业务事实存储。
