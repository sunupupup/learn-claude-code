# W-2026-013：Agent Task Completion Verification 与完成证据学习

- Status: ready
- Area: Agent / Task System / Verification / Eval / Reliability / Side Effects
- Difficulty: D2 → D3（从单任务确定性验收进入多 Agent、异步和不确定状态）
- Discovered From: `s12_task_system` 中 `complete_task` 只检查状态、模型可能虚假完成，以及“完成前是否需要 verifier”讨论
- Owner: personal
- Priority: high

## Objective

研究如何把“模型声称完成”转化为“系统有证据地允许完成”。为任务增加可执行的验收标准、验证器、证据和失败状态，使 `completed` 成为受约束的状态迁移，而不是自由文本结论。

## Problem Statement

当前 s12 的 `complete_task()` 只检查任务是否为 `in_progress`，随后直接写入 `completed`。它不知道：

- 任务的完成条件是什么；
- Bash、测试、文件修改或外部 API 是否真正成功；
- 哪个 Tool Call 产生了任务证据；
- 结果是成功、失败、部分成功还是执行状态未知；
- 谁验证了结果，以及证据是否仍然有效。

`blockedBy` 只回答“上游任务是否完成”，不能回答“当前任务是否真的完成”。`verify_task` 可以是一个接口，但如果它只是模型可选的 Tool，模型仍然可以跳过它。因此需要研究由 Harness 强制执行的完成门、独立验证器和人工审批边界。

## Stable Mental Model

```text
Task Contract
  objective / scope / acceptance_criteria / side_effect_policy
        ↓
Execution
  tool calls / artifacts / test results / external operation IDs
        ↓
Verification Gate
  deterministic verifier → optional semantic evaluator → human approval if required
        ↓
State Transition
  verifying → completed | failed | partial | needs_review | unknown
        ↓
Evidence Record
  verifier version / inputs / outputs / timestamps / trace / artifact references
```

默认顺序是先使用确定性 Oracle，再在无法规则化的语义质量上使用 LLM 评估，最后对高风险或争议结果交给人。LLM 评估不能替代数据库状态、文件 Hash、测试退出码、权限判定或外部资源查询。

## Work

### Track A：任务契约与验收标准

- 为代码、文件、数据库、只读调研、文档生成和外部副作用任务分别定义 `acceptance_criteria`；
- 区分目标、执行步骤、完成条件、质量条件和人工批准条件；
- 研究任务创建时由用户、父 Agent、规则模板还是模型生成验收标准；
- 处理验收标准缺失、互相冲突、过于开放和被任务内容注入的情况；
- 设计 `verifier_ref`、任务类型、版本和参数，避免 `complete_task` 盲猜验证方式。

### Track B：验证器与状态机

- 比较 `complete_task` 内部调用 verifier、独立 `verify_task` 服务、工作流节点和事件驱动验证；
- 设计 `in_progress → verifying → completed / failed / partial / needs_review / timed_out / unknown`；
- 明确验证失败时任务是否保持 `in_progress`、转为 `failed`，以及谁可以重试或覆盖；
- 区分同步短验证与需要后台执行的长测试、部署、数据质量检查；
- 研究验证器崩溃、超时、重复执行、版本变更和验证结果过期。

### Track C：证据、产物与可追溯性

- 设计 `evidence` 结构：命令、退出码、日志摘要、文件 Hash、Schema 快照、外部资源 ID、时间戳和权限主体；
- 把证据与 `task_id`、`run_id`、`tool_use_id`、Artifact 和 Trace 关联；
- 区分模型看到的 Summary 与权威业务状态；
- 处理证据过大、敏感、过期、丢失、不可访问和被篡改的情况；
- 研究完成状态是否需要不可变验证记录，以及如何审计人工覆盖。

### Track D：LLM 评估与人工边界

- 识别适合确定性验证的任务与只能做语义评估的任务；
- 比较同一模型自评、独立小模型、规则 + LLM、人工抽查和强制审批；
- 评测 LLM verifier 的误报、漏报、偏置、Prompt Injection 和成本；
- 要求 LLM verifier 输出结构化结果与证据引用，不能只返回“看起来完成”；
- 对支付、生产部署、删除、发信和权限变更等高风险操作建立人工门。

### Track E：失败、重试与副作用

- 区分未执行、执行失败、执行成功但响应丢失、验证失败和状态未知；
- 研究副作用 Tool 的 `operation_id`、`idempotency_key`、状态查询、补偿和人工接管；
- 设计验证重试与任务重试的边界，避免重复写入或重复部署；
- 处理部分完成、多个 Artifact、并行子任务和下游任务解锁；
- 注入进程崩溃、网络分区、锁竞争、验证器超时和父 Agent 重启。

### Track F：最小实验与 Eval

在专用实验目录中比较三种策略：

1. 当前实现：状态为 `in_progress` 即允许 `completed`；
2. 确定性验证：测试、文件 Hash、Schema 或模拟服务状态通过后才完成；
3. 确定性验证加可选 LLM 语义评估，并在高风险样本上人工复核。

至少覆盖：

- Bash 返回非零退出码；
- 文件缺失或内容与要求不符；
- 测试通过但改动超出范围；
- 外部写操作成功但 Tool Result 丢失；
- 验证器本身超时或不可用；
- 结果只有自然语言 Summary，没有 Artifact；
- 子任务部分完成后父任务是否错误解锁；
- 重试是否产生重复副作用。

优先使用确定性指标：false completion rate、false failure rate、证据完整率、重复副作用次数、验证延迟、Token、成本和人工接管率。

## Open-source study candidates

启动时只选择一个主样本和最多一个对照样本，重新核对 Commit、版本、许可证、活跃度和安全状态：

1. [Temporal](https://github.com/temporalio/temporal)：研究 Workflow 与 Activity 的持久化、重试、超时、心跳和“Activity 可能重复执行”时的幂等设计。
2. [LangGraph](https://github.com/langchain-ai/langgraph)：研究 thread/checkpoint、interrupt、Human-in-the-loop、暂停恢复和状态持久化如何支撑验证门。
3. [OpenHands Software Agent SDK](https://github.com/OpenHands/software-agent-sdk)：研究 Agent Server、Conversation、Event、Workspace、工具结果和运行完成事件之间的证据关联。
4. [Dagster](https://github.com/dagster-io/dagster)：研究软件资产的检查、数据质量断言和失败可观测性，作为“确定性验证器”对照，不把它当作 Agent Runtime。

## Boundaries

- Always：把验收标准和证据作为任务契约的一部分；高风险任务 fail-closed；验证真实状态而不只看 Summary；记录 verifier 版本和证据来源。
- Ask first：安装新依赖、下载大型仓库、运行外部服务、使用付费 API、修改 s12 教学实现或引入持久化数据库。
- Never：让模型单独把任务标记为完成；用一个未经校准的 LLM Judge 作为唯一真值；在执行状态未知时盲目重跑有副作用的工具；把“验证器返回成功”当成无需检查验证器输入的证明。

## Relationship to Related Work Pools

- [`s12_task_system`](../../s12_task_system/)：当前教学任务状态、依赖和 `complete_task` 的起点；
- [`W-2026-004`](W-2026-004-study-production-subagent-runtime.md)：父子 Agent、协同、结果契约和父级验收；
- [`W-2026-006`](W-2026-006-study-tool-result-compaction-and-recovery.md)：副作用结果、操作凭证和响应丢失恢复；
- [`W-2026-007`](W-2026-007-study-side-effect-tool-security.md)：写操作授权、幂等和安全门；
- [`s13_background_tasks`](../../s13_background_tasks/)：长验证和异步通知；
- [`s16_team_protocols`](../../s16_team_protocols/)：验证请求、审批和请求响应关联。

## Reason Deferred

s12 只需要理解“状态记录”和“依赖解锁”，立即实现通用 verifier 会同时引入任务契约、Artifact、测试执行、异步状态、权限和人工审批。先完成基础章节验收，再单独研究完成证据，避免把“任务系统”误学成“自动测试平台”。

## Start Trigger

完成 s13、s15 和 s18 的基础学习后，明确说“开始 W-2026-013”或同等意思时启动。启动时先只读分析一个真实项目，再决定是否修改教学代码。

## Expected Output

- 一份任务契约和验收标准模板；
- 一张验证状态机与失败转移图；
- 一个确定性 verifier registry 设计；
- 一份证据与 Artifact 关联格式；
- 一个确定性验证与 LLM 评估的对照实验；
- 一组覆盖虚假完成、响应丢失、验证超时和重复副作用的 Eval；
- 一份适用于 Subagent、后台任务和高风险 Tool 的完成门设计。

## Success Criteria

完成后应能够：

1. 说明 `completed`、`verified`、`approved` 和“模型声称完成”的边界；
2. 为至少三种任务类型写出可执行的验收标准；
3. 设计不依赖 LLM 自觉的完成门；
4. 处理失败、部分成功、状态未知、重试和重复副作用；
5. 用确定性证据和校准后的语义评估比较不同验证策略；
6. 解释验证器如何接入主 Agent、Subagent、后台 Worker 和人工审批流程。

## Open Questions

- 任务创建时如果没有可靠的验收标准，系统应拒绝创建、进入 `needs_review`，还是允许先执行后补充？
- 验证证据是否需要不可变存储、签名或内容 Hash，取决于什么风险等级？
- 父 Agent、执行 Subagent 和独立 Validator 之间如何分配完成判定责任，才能避免互相自证？
