# W-2026-006：Tool Result 压缩、恢复与副作用安全学习

- Status: ready
- Area: Context Engineering / Tool Calling / Reliability / Idempotency / Eval
- Difficulty: D2 → D3
- Discovered From: `s08_context_compact` 的 `micro_compact`、工具结果落盘与副作用讨论；`s13_background_tasks` 使用 `output[:200]` 生成后台通知摘要时，用户进一步确认 Bash 命令结果压缩是值得单独验证的生产级问题
- Owner: personal
- Priority: high

## Objective

从“统一把旧工具结果替换为占位符”的教学实现出发，研究生产系统如何根据工具语义、结果大小、业务重要性、副作用与可重试性，决定是否压缩、压缩成什么，以及怎样恢复完整信息。

重点不是把所有工具结果都压缩，而是建立以下判断链：

```text
结果是否足够小？
  ├─ 是：直接保留，不为压缩而压缩
  └─ 否：结果是否可安全重新获取？
         ├─ 是：保留摘要或占位符，必要时重新调用
         └─ 否：是否包含业务关键状态或不可重复副作用？
                ├─ 是：保留操作凭证摘要，完整结果持久化
                └─ 否：按 Token 价值选择摘要、截断或外置
```

## Stable Mental Model

Tool Result 压缩不是单纯缩短字符串，而是一次状态迁移：

```text
活跃模型上下文中的完整结果
  ↓ 选择关键状态
活跃上下文中的短摘要 / 操作凭证
  +
外部存储中的完整结果或业务系统事实
  +
明确的查询、重试、恢复与审计策略
```

业务强相关不等于“完全不能压缩”。关键是不能丢失继续执行和安全恢复所需的最小事实；大段详情仍可通过 `result_ref` 外置。

## Assumptions

1. 短结果（例如单纯的“查询成功”且没有后续依赖）可以直接保留，无需为了形式执行压缩。
2. `success: true/false` 通常不足以表达有副作用操作的真实状态。
3. 只读且可重复获取的结果，与转账、发信、创建资源等写操作采用不同策略。
4. 不能仅根据工具名称判断风险；需要结合副作用、幂等性、可重试性、结果来源和业务约束。
5. 完整结果落盘不代表模型仍能使用它；还需要稳定引用和显式恢复机制。
6. 当前条目只记录后续学习，不立即修改 `s08_context_compact` 或 `s13_background_tasks` 的运行逻辑，也不安装外部压缩工具。

## Result Envelope Fields To Preserve

为写操作或关键业务工具设计压缩结果时，至少评估以下字段；字段是否必需由具体工具契约决定：

```json
{
  "tool": "create_ticket",
  "status": "succeeded",
  "operation_id": "op_123",
  "resource_id": "ticket_456",
  "idempotency_key": "req_789",
  "retry_policy": "do_not_retry",
  "result_ref": "tool-results/op_123.json"
}
```

- `tool`：发生了哪类操作；
- `status`：成功、失败、部分成功、未知或等待确认；
- `operation_id`：本次外部操作的唯一凭证；
- `resource_id`：已创建或修改的业务资源；
- `idempotency_key`：重复请求的去重依据；
- `retry_policy`：允许自动重试、仅查询状态、需人工确认或禁止重试；
- `result_ref`：完整结果、审计记录或 Artifact 的稳定引用；
- 可选补充：错误类别、是否可能已产生副作用、时间戳、参数摘要/Hash、撤销入口和权限主体。

## Learning Plan

### Track A：工具与结果分类

- 区分只读查询、纯计算、幂等写入、非幂等写入和不可逆操作；
- 区分小结果、大文本、大二进制产物、流式结果和分页结果；
- 区分模型推理所需信息、业务状态、审计证据和可重新获取数据；
- 解释为什么“业务重要性”和“结果体积”是两个独立维度。

### Track B：压缩策略与接口

- 比较统一阈值、按工具定制 `compress_result()` 和元数据驱动策略；
- 区分命令源头降噪（例如 quiet/JSON/short 输出）、固定 head-tail 截断、命令感知结构化压缩和 LLM 语义摘要；
- 为 Bash 结果保留 `exit_code`、成功/失败/未知状态、stderr 或失败片段、截断说明和原始输出引用；
- 为 Tool 定义 `side_effect`、`idempotent`、`retryable`、`retention` 和 `compressor` 元数据；
- 设计 `raw_result → context_summary + result_ref + recovery_policy` 契约；
- 研究摘要、截断、字段投影、Blob/Artifact 外置和重新查询的适用边界；
- 保证压缩前后 `tool_use_id`、状态与因果关系仍可追踪。

### Track C：副作用、幂等与恢复

- 分析“请求失败”“执行失败”“执行成功但响应丢失”三种情况；
- 设计基于 `operation_id` 或 `idempotency_key` 的状态核对；
- 说明哪些工具可自动重跑，哪些只能查询状态，哪些必须人工确认；
- 处理部分成功、撤销失败、超时、并发重复与最终一致性；
- 区分模型看到的摘要与业务系统中的权威状态。

### Track D：Bash 输出压缩专项

建立一组冻结的 Git、测试、构建和日志输出，先比较以下基线，不用某个项目自报的压缩比例替代自己的 Eval：

1. `s13_background_tasks` 当前的 `output[:200]` 前缀截断；
2. head-tail、错误关键词保留和命令自身的 quiet/short/JSON 输出；
3. 按命令类型解析并投影关键字段；
4. 摘要加 `result_ref`，需要时回取完整输出。

任务启动时固定具体 Commit，再追踪两个 Bash 专项候选：

1. [RTK / Rust Token Killer](https://github.com/rtk-ai/rtk)：研究命令代理、Git/Test/Build/Log 专用过滤器、底层退出码保留、失败原文落盘与回取，以及 Hook 如何在 Tool Result 进入模型前改写命令；
2. [TRS / Token-Reducing Shell](https://github.com/dPeluChe/trs)：研究专用 Parser、无 Parser 时的通用降噪、结构化 JSON 输出和 Agent Hook 接入，与 RTK 做窄对照。

两者都是当前生态实现候选，不预设为行业标准。必须区分项目自报的 Bash 输出压缩率、实际模型输入 Token 变化和整次 Agent Run 的质量/成本变化。

### Track E：通用上下文实现阅读

任务启动时固定具体 Commit，再追踪以下主样本：

1. [Pydantic AI message history](https://github.com/pydantic/pydantic-ai/blob/main/docs/message-history.md)：研究 History Processor、工具调用/结果配对修复、压缩后历史有效性与不可原地修改的实现约束。
2. [OpenHands condenser abstraction](https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/context/condenser/base.py)：研究 View、Condensation、事件历史与可观测元数据的边界。
3. [LangChain summarization middleware](https://github.com/langchain-ai/langchain/blob/master/libs/langchain_v1/langchain/agents/middleware/summarization.py)：研究安全切点、工具消息配对、Token 触发器与摘要保留窗口。

协议基线参考 [Anthropic Python SDK tool runner](https://github.com/anthropics/anthropic-sdk-python/blob/main/src/anthropic/lib/tools/_beta_runner.py)：确认一次 assistant 响应中的多个 `tool_use` block，如何由下一条 user 消息中的多个 `tool_result` block 按 ID 配对。该实现用于理解消息协议，不直接视为 Tool Result 压缩方案。

通用实现资料初步检索日期：2026-09-04；Bash 专项候选于 2026-09-08 对照项目官方仓库与 Context7 `/rtk-ai/rtk`。正式启动任务时重新核对版本、活跃度、许可证和当前实现。

### Track F：Eval 与故障实验

至少实现并评测以下用例：

1. 小型只读结果保持原文，不触发无收益压缩；
2. 超大只读结果落盘，摘要包含路径和足够预览；
3. 写操作成功但响应丢失，恢复逻辑只查询状态而不重复执行；
4. 并行两个工具调用，压缩后所有 `tool_use_id` 仍有对应结果；
5. 部分成功结果保留成功项、失败项与后续动作；
6. `result_ref` 丢失、过期或无权限时给出明确失败，而不是假装恢复；
7. 比较原始结果、统一摘要和类型化压缩器的 Token、正确率、延迟与恢复成功率。
8. 构造“真正错误只出现在输出尾部”的 Bash 失败，证明前 200 字符截断会丢失诊断证据，而候选策略能保留失败摘要或稳定 `result_ref`。
9. 对同一批 Git/Test/Build/Log 输出比较原文、命令自身降噪、head-tail、RTK 和 TRS；分别记录输出体积、模型任务正确率、回取次数、延迟与误删关键信息次数。

优先使用确定性断言：ID 配对、Schema、状态机、幂等键、文件 Hash、数据库/服务端状态和副作用次数。LLM Judge 只用于摘要语义完整性，并使用人工样本校准。

## Boundaries

- Always：短结果先判断是否值得压缩；关键写操作保留操作凭证；完整结果有稳定引用；压缩后验证消息协议和恢复路径；记录压缩策略版本。
- Ask first：重放任何有副作用的工具；读取含敏感数据的完整结果；修改统一 Tool Result 契约；引入新的外部存储或开源框架依赖。
- Never：仅凭占位符自动重跑写操作；把 `success: true` 当成充分恢复状态；压缩掉未知副作用；把模型摘要当成业务系统权威事实。

## Start Trigger

当前条目只进入 Work Pool，不自动开始。建议完成 `s08_context_compact` 和错误恢复/幂等基础后启动；也可以在 s08 结束时先做只读的 Track A-B 与开源代码追踪，不执行真实副作用。

`s13_background_tasks` 学习期间只需理解 `output[:200]` 是不可恢复的字符截断，并记录它可能丢失失败尾部；完整 Bash 压缩器安装、对照和故障实验仍等待用户明确启动本 Work Pool。

## Success Criteria

完成后应能够：

1. 根据工具语义和结果特征选择保留、摘要、截断、外置或重新查询；
2. 设计包含操作凭证、恢复策略和完整结果引用的 Tool Result Envelope；
3. 解释 `success` 为什么不足以处理响应丢失、部分成功和重复执行；
4. 从至少两个开源项目追踪上下文压缩与工具消息配对实现；
5. 用故障注入证明写操作不会因上下文压缩而被重复执行；
6. 用 Eval 数据比较压缩率、任务正确率、恢复成功率、延迟和成本。
7. 能说明 Bash 前缀截断、命令感知压缩与完整上下文 Condenser 的层级差异，并用冻结输出证明选定策略保留了退出状态、失败证据和原文恢复入口。
