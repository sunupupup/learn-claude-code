# W-2026-004：生产级 Subagent 机制与真实项目调研

- Status: ready
- Area: Agent / Subagent / Delegation / Runtime / Isolation / Eval
- Difficulty: D2 → D3（从可部署的单次委派进入稳健多用户与长任务边界）
- Discovered From: `s06_subagent` 的上下文隔离、共享副作用与父 Agent 验收讨论
- Owner: personal
- Priority: medium

## Assumptions

1. 本任务当前只进入 Work Pool，不立即安装依赖、下载外部项目、运行生产 Harness 或修改现有 Agent 实现。
2. 本任务中的 Subagent 指“由父 Agent 临时委派、具有独立执行上下文并返回结果的子执行单元”；它与固定 Workflow、后台 Shell Task、持久 Agent Team 和跨服务 Agent 协议分别讨论。
3. 先用单 Agent 或确定性 Workflow 建立基线；只有任务分解带来的质量、上下文或吞吐收益能够被 Eval 证明时，才认为 Subagent 值得其额外成本。
4. 选择一个代码可读、可运行、有测试或 Trace 证据的真实开源项目作为主样本；最多再选一个项目做窄对照，不同时泛读多个框架。
5. 具体项目、版本和 API 在任务启动时根据活跃度、文档、许可证、可运行性和当前官方资料确定；涉及库/API 时使用 Context7 与维护者一手资料核验，不在 Work Pool 阶段锁定易过时结论。
6. “生产级”不表示复制某个厂商架构，而是能够解释和验证委派契约、生命周期、权限、隔离、结果验收、可观测性、可靠性、成本与恢复。

## Problem Statement

`s06_subagent` 用最小实现说明了：父 Agent 把 `task` 当成 Tool 调用，Handler 启动 fresh `messages[]` 的子 Agent Loop，最后只返回文本摘要。

这个教学模型尚未回答生产系统中的关键问题：

- 为什么需要 Subagent，而不是让单 Agent、固定 Workflow 或普通后台任务完成？
- 父 Agent 如何构造边界清晰、可验收、权限最小化的委派契约？
- 子 Agent 继承哪些 Context、Model、Prompt、Tools、Skills、身份和凭证？
- 同步、异步、后台、暂停、取消、超时和恢复分别如何建模？
- 父子 Agent 共享文件系统时如何避免覆盖、脏读和不可归责副作用？
- 子 Agent 的 Summary、结构化结果、Artifact 和真实环境状态如何对应？
- 谁负责验证结果：父模型、独立 Validator、确定性 Harness，还是人工审批？
- 怎样通过 Trace 和 Eval 证明委派质量，而不是只看最终回答像不像正确？

## Stable Mental Model

```text
User Goal
   ↓
Parent Agent：判断是否值得委派
   ↓
Delegation Contract：目标、范围、输入、权限、预算、完成条件
   ↓
Child Context Builder：System / Messages / Tools / Skills / State / Credentials
   ↓
Runtime / Sandbox：执行、超时、取消、重试、资源和副作用隔离
   ↓
Result Contract：状态、摘要、证据、Artifacts、错误和未完成项
   ↓
Validation Gate：确定性检查、测试、策略、人工审批
   ↓
Parent Integration：接受、重试、继续委派、回滚或升级给用户
```

Subagent 的价值不由“调用了多少 Agent”证明，而由相对单 Agent 基线的任务成功率、轨迹质量、上下文压力、延迟、成本和风险共同证明。

## Work

### Track A：建立术语与基线

- 区分 Subagent、Workflow Step、Background Task、Agent Team、Handoff 和跨服务 Agent；
- 建立一个无需 Subagent 的单 Agent 基线，并记录成功率、步骤数、Token、延迟和失败类型；
- 定义什么任务适合委派：可并行、上下文密集、专业工具不同或边界清晰；
- 定义不适合委派的任务：高度共享状态、强顺序依赖、低延迟小任务或副作用难隔离；
- 记录一次错误委派案例，说明拆分成本为什么超过收益。

### Track B：沿真实项目追踪一条完整调用链

选择一个主项目，从用户入口追踪到结果回收：

1. 父 Agent 在哪里决定委派，由模型、规则还是混合策略决定；
2. Tool/Command/API 如何描述子任务，输入是否有 Schema；
3. 子 Agent 如何构建 Context，哪些父消息被复制、摘要、引用或丢弃；
4. Model、System Prompt、Tools、Skills、权限和凭证如何选择；
5. 子 Runtime 使用同进程、线程、子进程、容器、沙箱还是远程 Worker；
6. 文件、网络、数据库和外部 API 副作用如何隔离、审计和回滚；
7. 子任务怎样表示 running、waiting、completed、failed、cancelled、timed_out 和 partial；
8. 结果如何返回：自由文本、结构化对象、Artifact 引用、Patch、Commit 或事件；
9. 父 Agent 如何验收、重试、继续工作或请求人工决策；
10. Trace 如何关联 Parent Run、Child Run、Model Call、Tool Call、权限和副作用。

必须分别画出一条成功链和一条失败/恢复链。

### Track C：Context、权限与隔离矩阵

为主项目建立矩阵，明确每个资源是复制、共享、继承、过滤、引用还是隔离：

| 资源 | 需要研究的选择 |
| --- | --- |
| `messages[]` | fresh、fork、摘要、选择性继承、Prompt Cache |
| System Prompt / Skills | 父级继承、角色覆盖、按任务注入 |
| Tools | 相同集合、Allowlist、Denylist、动态发现 |
| 身份与凭证 | 父身份代理、短期凭证、按用户授权、权限冒泡 |
| 文件系统 | 共享目录、临时目录、Git Worktree、容器或远程沙箱 |
| 网络与外部系统 | 出口限制、域名 Allowlist、只读与写入权限 |
| State / Memory | 子任务局部状态、父会话状态、跨会话持久化 |
| Trace / Audit | Parent-Child 关联、敏感内容最小化、证据保留 |

重点验证“上下文隔离不等于权限、文件系统或进程隔离”。

### Track D：委派与结果契约

设计一份最小委派契约，至少包含：

- `objective`：子任务目标；
- `scope`：允许读取和修改的范围；
- `inputs` / `artifact_refs`：必要输入与外部产物引用；
- `allowed_tools` / `permissions`：最小能力；
- `budget`：最大步骤、时间、Token 和成本；
- `acceptance_criteria`：可验证完成条件；
- `side_effect_policy`：只读、可写、需审批或必须隔离；
- `on_failure`：重试、返回部分结果、回滚或升级。

设计一份结果契约，至少包含：

- `status`：completed / partial / failed / cancelled / timed_out；
- `summary`：供父模型继续推理的简短说明；
- `artifacts` / `files_changed`：可定位的真实产物；
- `evidence`：测试、命令、引用或确定性检查；
- `side_effects`：已发生的外部改变及其可逆性；
- `errors` / `open_questions`：失败和未解决问题；
- `usage`：步骤、Token、延迟与成本。

验证结果契约本身不能替代读取真实文件、检查数据库状态、执行测试或服务端授权。

### Track E：最小可运行实验

在隔离的教学分支或专用实验目录中构造三组任务：

1. **只读调研**：子 Agent 搜索多个文件并返回带来源结论；
2. **共享目录写入**：子 Agent 修改文件，观察未报告改动、错误摘要和父级验收；
3. **隔离目录写入**：子 Agent 在临时目录或 Git Worktree 工作，由父 Agent 检查 Patch、测试和合并决策。

每组至少注入以下失败之一：

- 子 Agent 声称完成但没有修改；
- 修改正确但 Summary 遗漏文件；
- 修改了范围外文件；
- 测试失败却返回 completed；
- 达到步骤、时间或成本上限；
- 父 Agent 重试导致重复副作用；
- 用户取消时子 Agent 仍在执行。

实验必须记录真实 Trace，并区分模型主动验证、Prompt 要求验证和 Harness 强制验证。

### Track F：Eval 与生产边界

冻结 10-20 条代表性任务，至少评测：

- 是否应当委派，以及错误委派率；
- 委派目标、范围和完成条件是否完整；
- 子 Agent 工具选择、参数与轨迹是否合理；
- 最终结果与 Artifact 是否真实一致；
- 父 Agent 是否发现虚假完成、越界修改和失败测试；
- 超时、取消、重试、幂等和部分成功是否正确；
- Prompt Injection、Confused Deputy、权限扩大和数据泄漏；
- 相比单 Agent 基线的成功率、Token、延迟和成本。

优先使用确定性 Oracle：文件 Hash、Git Diff、测试退出码、Schema、权限策略和状态机断言。LLM Judge 只能用于难以规则化的语义质量，并需用人工样本校准。

## Relationship to Later Chapters

- [`s08_context_compact`](../../s08_context_compact/)：比较上下文隔离、选择性继承和压缩；
- [`s11_error_recovery`](../../s11_error_recovery/)：补齐错误分类、重试和终止状态；
- [`s13_background_tasks`](../../s13_background_tasks/)：区分 Subagent 生命周期与异步后台执行；
- [`s15_agent_teams`](../../s15_agent_teams/)：区分一次性子 Agent 与持久队友；
- [`s18_worktree_isolation`](../../s18_worktree_isolation/)：研究文件副作用隔离和可审查合并。

## Reason Deferred

`s06_subagent` 当前目标是理解最小同步委派、fresh context 和 summary-only 返回。立即进入生产 Runtime 会同时引入异步执行、错误恢复、持久状态、团队通信、权限冒泡和 Worktree 隔离，容易把多个尚未学习的机制混在一起。

因此先完成基础章节和本章运行验收，再启动真实项目调研；Work Pool 的存在不表示自动开始。

## Start Trigger

推荐在完成 s18 后完整启动。若希望提前，可在完成 s11 后只启动只读的 Track A-C，不进行异步、团队或 Worktree 实验。

完整启动前应满足：

- 能独立写出 s06 父子 Agent 调用伪代码；
- 能解释 Context、Tool、Permission、Filesystem 和 Runtime 的不同隔离维度；
- 已完成一次只读子任务和一次写文件子任务运行实验；
- 能说明 Summary 为什么不是完成证据；
- 已学习错误恢复、后台任务、Agent Teams 与 Worktree Isolation 的基础机制。

## Preferred Order

1. 冻结单 Agent 基线任务与指标。
2. 建立候选项目筛选标准并选择一个主样本。
3. 只读追踪成功链与失败/恢复链。
4. 完成 Context、权限、隔离和生命周期矩阵。
5. 设计委派契约与结果契约。
6. 构造共享目录与隔离目录的最小实验。
7. 注入虚假完成、越界修改、超时、取消和重复副作用。
8. 对比单 Agent 与 Subagent 的质量、成本和延迟。
9. 输出生产边界、适用条件和仍然未知的问题。

## Boundaries

- Always：先建立非 Subagent 基线；使用冻结任务；保留 Trace；把项目事实与通用原理分开；验证真实副作用而不只读 Summary。
- Ask first：安装新依赖、下载大型仓库或模型、运行外部服务、使用付费 API、修改当前教学代码或引入新的长期架构决定。
- Never：把子 Agent 的自然语言完成声明当作唯一证据；默认共享高权限凭证；在没有隔离和审批时执行高风险写操作；用未校准的 LLM Judge 作为唯一真值。

## Expected Output

- 一张成功委派链和一张失败/恢复链；
- 一份 Context、工具、权限、身份、文件系统和状态的隔离矩阵；
- 一份委派输入契约与结果契约；
- 一个共享目录实验和一个隔离目录实验；
- 一套 10-20 条冻结 Eval Set 与基线对比结果；
- 一份教学版 `s06_subagent` 与真实项目的差异清单；
- 一份生产检查清单，覆盖验证、权限、可靠性、可观测、成本和回滚；
- 是否值得在目标场景使用 Subagent 的证据化结论。

## Success Criteria

完成后应能够：

1. 从真实项目代码中追踪一次父子 Agent 的完整生命周期；
2. 解释每类 Context、权限、状态和副作用为何共享或隔离；
3. 设计可验证、可取消、可审计且预算受控的委派与结果契约；
4. 用故障注入证明父级验收能够发现虚假完成、越界修改和失败测试；
5. 用 Eval 数据比较单 Agent 与 Subagent，而不是凭 Demo 判断收益；
6. 清楚区分稳定 Agent 原理、教学实现和某个项目的版本相关 API。
