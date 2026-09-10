# W-2026-020：Agent-to-Agent 协作方式与通信拓扑

- Status: ready
- Area: Agent Collaboration / Agent-to-Agent Communication / Delegation / Handoff / Inbox / Task Board / Peer Coordination / Eval
- Difficulty: D2 → D3（从协作模式辨析进入生产级协议、权限和评测边界）
- Discovered From: s15 学习过程中对 Subagent、Teammate、跨 Lead Turn 驻留、跨 Session 协作以及 Agent 之间通信方式的重新分类
- Owner: personal
- Priority: high

## Objective

专门研究 Agent 之间如何协作，建立不依赖厂商命名的比较框架。重点区分协作拓扑、生命周期和通信/状态边界，而不是把所有异步线程、后台任务或普通 Workflow 都称为 Agent Team。

目标是能够判断一个问题应该使用：

- 一次性父子委派；
- 持久 Lead-Teammate inbox；
- Handoff（控制权交接）；
- 层级子团队；
- 共享任务板或 Blackboard（黑板式协作）；
- Peer-to-Peer（同级 Agent 点对点协商）；
- 跨进程/跨 Session 的 Durable Agent 协作。

## Problem Statement

不同 Agent 系统可能都使用“Subagent”“Team”“Handoff”“Worker”或“Swarm”等词，但真实协作语义可能完全不同。需要分别回答：

- 谁拥有任务和最终验收责任；
- Agent 是一次性、有限多轮、空闲等待还是可恢复的 Durable 逻辑实体；
- 消息是返回值、定向 inbox、共享任务状态、事件还是控制权交接；
- Agent 是否能主动发现、选择、委派和监督其他 Agent；
- 上下文、权限、Artifact、状态和副作用如何在 Agent 之间传递；
- 失败、取消、重复消息和部分成功如何归责与恢复。

## Stable Mental Model

```text
Agent-to-Agent Collaboration
  = Topology
  × Lifecycle
  × Communication / State Boundary
  × Authority / Verification
```

常见组合：

```text
s06：parent-child × one-shot × direct result
s15：lead-worker × bounded multi-turn × inbox
Handoff：single active owner × control transfer × context handoff
Task Board：many workers × claim-based lifecycle × shared task state
Peer Team：peer topology × message exchange × shared coordination rules
Durable Team：any topology × cross-process/session state × event delivery
```

“跨 Session”主要是持久化和运行边界，不是单独的拓扑；跨 Session 的 Agent 仍可以采用父子、Lead-Worker、Peer 或任务板协作。

## 不要把三类问题混成一个“编排模式”

生产系统里的 Agent Orchestration（Agent 编排）通常至少由以下维度组合而成：

```text
编排方案
  = 控制权拓扑
  × 执行形态
  × 生命周期
  × 通信/状态边界
  × 权限与验收责任
```

### 1. 控制权拓扑

回答“谁拥有当前任务和用户对话”：

- **Manager / Orchestrator**：中心 Agent 保留用户对话和最终结果控制权；
- **Handoff / Transfer**：把当前控制权交给另一个 Agent；
- **Supervisor-Worker**：上层 Supervisor 拆分、分配和验收，下层 Worker 执行；
- **Peer / Swarm**：同级 Agent 互相转移、协商或广播，没有固定的单一执行者；
- **Task Board / Blackboard**：Agent 通过共享任务状态协调，不一定直接互相发消息；
- **Lead-Teammate**：Lead 与具有独立 Loop 的 Teammate 通过 inbox 持续协作。

### 2. 执行形态

回答“任务如何展开和合成”：

- **Sequential / Pipeline**：固定的 A → B → C 阶段；
- **Router / Branch**：先分类，再选择一个或多个分支；
- **Parallel Fan-out / Fan-in**：并行派发，再聚合结果；
- **Map-Reduce**：把输入切成多个分片，分别处理后归并；
- **Planner-Executor**：先规划，再执行，必要时重新规划；
- **Generator-Critic**：生成者产出，评审者检查，再迭代；
- **Debate / Ensemble**：多个 Agent 独立或对立地产生意见，再投票或裁决；
- **Event-driven**：由消息、定时器、审批或外部事件推进下一步。

这些执行形态不一定都需要多个独立 Agent。例如固定的 Pipeline 可以完全由普通代码实现；多 Agent 只有在上下文隔离、专业能力、并行性或独立验证带来净收益时才值得引入。

### 3. 生命周期与运行时

回答“Agent 活多久、如何暂停和恢复”：

- **One-shot**：调用一次，返回一次结果；
- **Bounded multi-turn**：在有限轮数内持续工作；
- **Idle resident**：完成一轮后进入 idle，等待新消息再工作；
- **Durable**：跨进程/Session 保存身份、状态和 Checkpoint；
- **Human-gated**：等待用户澄清、审批或编辑后恢复；
- **Compensatable**：失败后能够取消、补偿或从安全边界重试。

因此，`Manager`、`Agent as Tool` 和 `Handoff` 不是同一层的概念：

```text
Manager        = 控制权/协调角色
Agent as Tool  = 调用另一个 Agent 的封装机制
Handoff        = 控制权转移机制
Teammate       = 独立 Loop + 通信 + 生命周期模式
```

一个系统可以同时使用它们，例如：Root Manager 通过 Agent-as-Tool 调用研究子 Agent，研究子 Agent 内部再使用并行 Worker；另一个客服场景则在 Router 后 Handoff 给退款 Agent。

## Agent 编排模式地图

### A. 控制权与拓扑模式

| 模式 | 运行机制 | 适用场景 | 优点 | 主要代价/风险 | 生产选择信号 |
| --- | --- | --- | --- | --- | --- |
| 单 Agent + Tools | 一个 Agent 持有完整对话、状态和 Tool | 任务边界清楚、工具数量可控 | 最简单，调试和验收成本最低 | 上下文膨胀，职责混杂 | 默认起点；先证明单 Agent 不够再拆分 |
| Manager + Agent as Tool | Manager 把专家 Agent 当作受约束的 Tool 调用，结果返回 Manager | 子任务边界清楚，最终回答必须由一个 Agent 统一生成 | 最终责任集中，容易做权限和输出汇总 | 子 Agent 不能自然接管用户；嵌套调用有额外延迟和 Token 成本 | 需要专业上下文隔离，但不需要转移用户对话 |
| Router / Triage | 规则或模型先分类，再路由到专家 | 客服、语言、领域、任务类型分流 | 路径清晰，专家上下文更小 | 分类错误；复杂任务可能需要二次路由 | 入口类别稳定，能定义路由 Eval |
| Handoff | Agent A 把当前对话和控制权转给 Agent B | 用户应该直接和领域专家继续交流 | 专家拥有完整交互权，Prompt 更聚焦 | 最终责任、上下文过滤、回退路径更复杂 | “谁接管用户”本身就是业务流程的一部分 |
| Supervisor-Worker / 层级 Team | Supervisor 拆分、分配、监督和验收 Worker | 子任务动态产生，领域边界明确 | 适合复杂任务和多阶段协作 | 监督者成为瓶颈；层级越深越难追踪失败和权限 | 任务无法预先列出，且有明确的上层验收者 |
| Lead-Teammate Inbox | Lead 与独立 Loop 的 Teammate 通过消息持续沟通 | 长任务、并行领域工作、需要多轮追加指令 | Teammate 可跨 Lead Turn 驻留，职责隔离 | 需要 Registry、消息可靠性、idle、shutdown、恢复 | 工作跨度长于一个模型 Turn，且不应转移用户控制权 |
| Task Board / Blackboard | Agent 认领共享任务，写回状态、Artifact 和结果 | 多个 Worker 处理大量相互独立的任务 | 解耦生产者/消费者，适合扩展和重试 | 需要 claim/lease/CAS、冲突解决、重复任务和一致性设计 | 任务数量多、异步、可重试，且共享状态比点对点消息更自然 |
| Peer-to-Peer / Swarm | Agent 之间点对点转移或协商，弱化中央协调者 | 多专家协商、动态接力、没有固定 Root | 局部决策灵活，减少单一 Supervisor 瓶颈 | 责任、终止、预算、冲突和审计最难 | 只有在中心协调确实成为瓶颈，并且能定义全局终止和验收时考虑 |
| Shared Group Chat / Selector | Agent 共享会话，Selector 或 Group Manager 选择下一个发言者 | 创作、讨论、多人审阅、实验型协作 | 信息共享直接，调度策略可替换 | 上下文爆炸、轮次失控、重复发言、难以归责 | 需要协商过程本身，且能接受高 Token/延迟成本 |

### B. 执行与合成模式

| 模式 | 运行机制 | 适用场景 | 优点 | 主要风险 |
| --- | --- | --- | --- | --- |
| Sequential Pipeline / DAG | 代码或图明确规定节点和边 | 抽取 → 检索 → 判断 → 生成等固定阶段 | 可预测、易测试、易审计 | 流程变化需要改图；模型灵活性有限 |
| Conditional Branch | 根据分类或中间状态选择下一节点 | 不同用户类型、不同风险等级或数据路径 | 规则清楚，便于权限和成本控制 | 路由边界覆盖不足会漏分支 |
| Parallel Fan-out/Fan-in | 同时运行多个独立 Agent，聚合器合并结果 | 多领域研究、多个文件分析、多路检索 | 降低墙钟时间，隔离上下文 | 并发成本、结果冲突、聚合质量和取消传播 |
| Map-Reduce | 对多个分片执行同一 Agent 任务，再归并 | 长文档、多仓库、多客户记录 | 可水平扩展，单个 Worker 上下文小 | 分片边界、归并丢信息、跨分片依赖 |
| Dynamic Orchestrator-Worker | Orchestrator 动态生成任务并创建 Worker | 子任务数量和内容事先未知 | 灵活，适合代码修改和复杂报告 | 任务爆炸、重复委派、预算失控、计划不可复现 |
| Planner-Executor | Planner 生成计划，Executor 按步骤执行并反馈 | 长链路任务、需要显式计划的操作 | 计划与执行职责分开，便于检查 | 计划过时；计划本身可能是错误的，不应跳过执行校验 |
| Generator-Critic / Reviewer | 生成结果后由独立 Agent 检查、提出修正 | 代码、合同、报告、结构化输出 | 质量和缺陷发现可能提升 | 成本和延迟增加；Critic 也可能错误或无效地反复挑错 |
| Debate / Ensemble / Voting | 多 Agent 独立回答或互相质询，再投票/裁决 | 高不确定性、需要多视角或风险复核 | 降低单次模型偏差，提供独立证据 | “多数票”不等于正确；成本高，需校准裁决器 |
| Human-in-the-loop Gate | 在高风险节点暂停，用户审批/编辑后恢复 | 发布、删除、付款、生产变更、敏感数据访问 | 控制不可逆副作用，责任边界清晰 | 人工延迟、断线、过期审批、恢复和审计复杂 |
| Event-driven Durable Flow | 以事件、队列、定时器和 Checkpoint 驱动状态机 | 等待外部系统、审批、长时间任务 | 可暂停、恢复、重试、跨进程运行 | 持久状态、幂等、顺序、重复事件和版本迁移复杂 |

### C. 这些模式可以组合，而不是互斥

生产系统通常是组合，而不是选择一个标签：

```text
用户入口
  → Router
  → Manager
  → Agent-as-Tool 调用领域专家
  → 并行 Fan-out 研究
  → Fan-in / Critic 审核
  → Human Approval
  → Durable Executor 执行副作用
```

几个常见组合：

1. **Manager + Agent-as-Tool + Fan-out/Fan-in**：Manager 保持最终回答，多个研究 Agent 并行查资料，Aggregator 合并结果；
2. **Router + Handoff**：入口 Agent 判断领域，转交给真正负责该领域对话的 Agent；
3. **Supervisor + Task Board + Durable Worker**：Supervisor 产生任务，Worker 通过租约认领，结果写回任务板，失败后可恢复；
4. **DAG + Agent 节点 + Human Gate**：确定性流程控制顺序，Agent 负责不确定的抽取/判断，高风险节点由人审批；
5. **Lead + Teammate + `user_input_request`**：长任务中的 Teammate 暂停等待用户补充信息，Lead 负责用户交互，再把响应发回。

## 生产选择方式：从简单到复杂的升级梯度

### 第 0 步：先判断是否真的需要多 Agent

如果单 Agent 加合适的 Tool、Context 和输出校验能够稳定完成任务，就不要为了“专业分工”增加多个 Agent。多 Agent 带来的成本包括：

- 更多模型调用、Token、延迟和失败点；
- 跨 Agent 上下文和结果契约；
- 消息重复、状态竞争和副作用归责；
- Trace、Eval、权限和故障恢复的复杂度。

### 第 1 步：优先选择中心责任人

生产默认通常先选 **单 Agent** 或 **Manager + Agent-as-Tool**：

- 一个组件负责面向用户；
- 一个组件承担最终验收；
- 子 Agent 只返回结构化结果、证据和失败状态；
- 高风险副作用经过统一权限和人工审批。

### 第 2 步：根据任务形态选择执行方式

| 观察到的任务特征 | 首选模式 | 不要直接选择 |
| --- | --- | --- |
| 步骤固定、输入输出明确 | Pipeline / DAG | 让多个 Agent 自由聊天 |
| 多个子任务互相独立 | Parallel Fan-out/Fan-in | 串行等待每个 Worker |
| 子任务数量事先未知 | Orchestrator-Worker | 手写固定 N 个 Agent |
| 需要把用户交给领域专家 | Handoff | 让 Manager 反复转述所有对话 |
| 只需专家完成局部子任务 | Agent-as-Tool | Handoff 夺走整个对话 |
| 任务很多、异步、可重试 | Task Board + Lease | 只依赖进程内字典 |
| 需要跨等待和崩溃恢复 | Durable Event-driven | 只启动 daemon thread |
| 需要高质量复核 | Generator-Critic / 独立验证 | 无限 Reflection Loop |
| 需要多视角且能承担成本 | Ensemble / Debate | 把多数票当成真值 |
| 高风险不可逆动作 | Human Gate | 只依赖模型自我判断 |

### 第 3 步：只有证据证明需要时才引入层级或 Peer

层级 Team、Peer-to-Peer 和 Swarm 应该有明确的收益假设，例如：

- 单一 Supervisor 的上下文或调度吞吐确实成为瓶颈；
- 领域边界稳定，子团队可以独立验收；
- 多个 Agent 的协商能带来可测量的质量收益；
- 任务可以被安全地拆分、取消、重试和归责；
- 有明确的全局预算、终止条件和最终验证者。

如果只能说“多 Agent 更聪明”，还不足以选择这些模式。

## 生产级编排的共同控制面

不管选择哪种拓扑，生产实现都至少要定义：

1. **Ownership**：谁拥有用户交互、任务、资源和最终验收责任；
2. **Contract**：输入、输出、证据、失败状态和 `needs_user_input` 的结构化 Schema；
3. **Lifecycle**：created、working、waiting、idle、completed、failed、cancelled、terminated；
4. **Budget**：最大深度、扇出、模型调用数、Token、延迟和费用；
5. **State**：Run、Task、Agent、Message、Artifact、Checkpoint 的 ID 和持久化边界；
6. **Delivery**：ack、重试、去重、过期、顺序、幂等和死信策略；
7. **Authority**：谁能创建、委派、发送消息、调用 Tool、审批和撤销；
8. **Side effects**：写入、发布、删除、支付等动作的预览、审批、幂等和补偿；
9. **Verification**：子结果如何验收，模型的“完成”声明不能直接作为完成证明；
10. **Observability**：能否按 Run/Task/Agent/Tool/Message 还原完整轨迹；
11. **Termination**：正常完成、预算耗尽、无进展、循环、冲突和人工接管如何结束；
12. **Recovery**：进程崩溃、Agent 失联、部分成功和版本升级后如何恢复。

## 典型生产场景与推荐组合

### 复杂研究 / 多来源调查

推荐：`Manager/Lead + Parallel Research Workers + Evidence Aggregator + Critic`。

研究问题可以按来源或子问题并行拆分，最后由聚合器统一处理冲突和引用。此类任务适合并行，但必须限制扇出、保留来源 ID、去重结果，并评测“引用正确性”而不只是最终文案。

Anthropic 公开介绍其多 Agent Research 系统时，也描述了 Lead Agent 规划研究、并行启动子 Agent、再汇总结果的架构，同时强调多 Agent 会带来协调、评测和可靠性挑战。[官方工程文章](https://www.anthropic.com/engineering/multi-agent-research-system)

### 代码重构 / 多文件修改

推荐：`Manager/Orchestrator + Task Board 或动态 Worker + 文件/资源所有权 + 最终测试 Agent`。

不要让多个 Agent 无约束地同时写同一个文件。应先按模块切任务，设置文件所有权或租约，最后由统一验证者运行测试、检查 diff 和处理冲突。

### 客服 / 多领域用户对话

推荐：`Router/Triage + Handoff`，或 `Manager + Agent-as-Tool`，取决于谁拥有最终对话。

- 如果退款 Agent 后续要直接和用户沟通，选择 Handoff；
- 如果客服 Manager 必须统一措辞、权限和最终回答，选择 Agent-as-Tool；
- 领域分类稳定时优先规则路由，只有边界模糊时才让模型路由。

### 长时间运行的业务任务

推荐：`Durable State Machine + Supervisor + Worker/Task Board + Human Gate`。

例如采购、部署、审批、数据导入。重点不是让 Agent 一直占用线程，而是保存状态，在等待用户/外部系统时释放计算资源，事件到达后从 Checkpoint 恢复。

### 高风险操作

推荐：`Agent 规划/准备 + Deterministic Policy + Human Approval + Idempotent Executor`。

Agent 可以生成计划和参数，但不要让多个 Peer Agent 自行互相批准。权限、审批、执行和审计必须有独立的控制面。

## 主要模式的生产风险对照

| 风险 | 最容易出现的模式 | 必须补的控制 |
| --- | --- | --- |
| 上下文爆炸 | Group Chat、Peer、共享历史 | Context 过滤、摘要、Artifact 引用、预算 |
| 责任不清 | Peer、Swarm、深层级 Team | Root Owner、结果契约、最终验收者 |
| 调度瓶颈 | 单一 Supervisor、中心 Selector | 限制扇出、分域 Supervisor、队列和背压 |
| 任务重复 | Task Board、事件总线、重试 | Lease、幂等键、ack、去重和死信 |
| 结果冲突 | 并行 Fan-out、Debate | 结构化结果、证据优先级、合并策略 |
| 无限循环 | Reflection、Planner-Replanner、Peer | 最大轮次、无进展检测、成本预算、终止条件 |
| 权限扩大 | 层级委派、Handoff、共享凭证 | 身份绑定、最小权限、不可转移授权、审计 |
| 副作用重复 | 并行 Worker、重试、恢复 | 单写者、幂等、预览、补偿和人工审批 |
| 状态丢失 | daemon thread、短期 Subagent | Checkpoint、持久消息、恢复协议、状态版本 |

## 官方资料与版本核验入口

以下资料用于启动 Work Pool 时建立对照，不把任何框架的命名直接当作通用标准：

- [OpenAI Developer quickstart：Agents SDK 与 handoff 示例](https://platform.openai.com/docs/quickstart/make-your-first-api-request)
- [LangGraph：Workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)：串行、并行、Orchestrator-Worker 等执行形态；
- [LangGraph：Subgraphs 与子 Agent](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)：子 Agent、嵌套图、持久化和多 Agent 调用边界；
- [LangGraph：Overview](https://docs.langchain.com/oss/python/langgraph/overview)：持久执行、人机协同和长期状态运行时；
- [AutoGen：Teams](https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/tutorial/teams.html)：RoundRobin、SelectorGroupChat、Swarm 等 Team 预设；
- [AutoGen：Group Chat pattern](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/group-chat.html)：共享 Topic、发言选择和事件驱动通信；
- [Anthropic：Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)：Lead + 并行 Research Workers 的生产案例与协调挑战。

启动真实源码对照时必须固定版本/Commit，并分别记录：产品术语、实际拓扑、消息协议、状态持久化、权限边界和评测证据。

## Recommended Learning Order

1. 固定术语：Subagent、Teammate、Handoff、Peer、Worker、Blackboard、Task Board 和 Durable Agent；
2. 以 s06/s15 为基线，比较一次性委派和进程内多轮 inbox 协作；
3. 研究 Handoff 与 Lead-Worker 的责任和控制权差异；
4. 对比直接消息、共享任务板、事件总线和共享 Artifact；
5. 研究层级 Team 与 Peer-to-Peer/Swarm 的授权、冲突和结果汇总；
6. 研究跨进程/跨 Session 协作的身份、Registry、checkpoint、ack、重试和恢复；
7. 按“拓扑 → 执行形态 → 生命周期 → 控制面”的顺序，对每种模式写出最小状态机和消息/结果契约；
8. 用至少四种场景比较 Manager、Agent-as-Tool、Handoff、Fan-out/Fan-in、Task Board 和 Durable Team 的取舍；
9. 选择一个主开源项目和最多一个窄对照，固定版本/Commit，使用 Context7、官方文档和维护者源码核验调用链；
10. 用固定 Eval 比较不同协作方式的成功率、延迟、成本、上下文压力、消息可靠性和副作用风险。

## Core Questions

- 一次性 Subagent 和多轮 Teammate 的最小边界是什么？
- Handoff 是新 Agent 接管同一任务，还是只复制一份上下文？
- 直接 inbox、任务板和事件总线分别适合什么协作关系？
- Peer Agent 没有 Root Lead 时，谁负责冲突解决和最终验收？
- 什么时候层级委派有收益，什么时候只是增加消息和协调成本？
- Durable Teammate 是否需要模型可调用的 `list_teammates`，还是 Runtime 内部 Registry 足够？
- Agent 身份、角色、权限、租户、Run 和 Task ID 如何关联？
- 如何避免重复委派、消息环路、无限嵌套、结果丢失和副作用重复？
- 子 Agent 需要用户澄清时，应该返回 `needs_user_input`、触发 Handoff，还是通过 Teammate inbox 挂起等待？
- 哪些模式只是 Agent 拓扑，哪些其实是 Pipeline、DAG、Human-in-the-loop 或质量评审策略？
- Manager + Agent-as-Tool 与 Handoff 如何在最终责任、用户体验和上下文隔离上取舍？
- Parallel Fan-out/Fan-in 的聚合器如何处理冲突、部分失败、超时和取消传播？
- Task Board 的 claim、lease、CAS、ack 和幂等如何避免重复认领和双重副作用？
- Planner-Executor 的计划如何版本化、验证、过期和重新规划？
- Critic、Debate 和 Ensemble 的额外调用是否带来可测量收益，如何设计对照 Eval？
- Durable Team 如何处理等待审批、进程崩溃、成员失联、消息重复和 Checkpoint 迁移？
- 为什么生产系统通常先保留一个最终责任人，而不是直接选择 Peer/Swarm？

## Expected Output

- 一张 Agent-to-Agent 协作方式对照表：拓扑、生命周期、通信、状态、授权和验收；
- 一份 Subagent / Teammate / Handoff / Task Board / Peer / Durable Team 决策矩阵；
- 一张更完整的编排模式地图，分开控制权拓扑、执行形态和生命周期；
- 一份从单 Agent 到 Durable Team 的生产选择梯度与反模式清单；
- 至少四个真实场景的组合架构：研究、代码修改、客服路由和长任务审批；
- 一张消息、Artifact、Context、权限和最终责任的流转图；
- 一个包含 `list_teammates`、`send_message`、`handoff`、`claim_task` 等能力的最小控制面契约草案；
- 一组覆盖消息重复、成员崩溃、权限升级、层级环路和部分成功的 Eval；
- 至少一个真实开源项目的固定版本协作调用链，以及与 s15 教学实现的差异报告。

## Success Criteria

完成后应能够：

1. 只用拓扑、生命周期和通信边界解释不同 Agent 协作模式；
2. 判断任务应使用一次性委派、持久队友、Handoff、任务板、Peer 或层级 Team；
3. 解释为什么 Durable Team 需要 Registry，但不必然需要模型可调用的成员列表 Tool；
4. 区分 Manager、Agent-as-Tool、Handoff、Router、Pipeline、Fan-out/Fan-in、Task Board、Peer 和 Durable Event-driven；
5. 为一种协作模式写出消息、权限、失败和验收契约；
6. 根据任务的并行性、动态性、用户交互、生命周期和副作用风险选择最小可行拓扑；
7. 用真实项目代码和 Eval 证据支持协作方式选择，而不是只依据产品名词。

## Why Deferred

当前继续 s15 的基础通信和生命周期学习，不立即展开完整 Agent 协作模式调研。该任务会横跨 s06、s15、s16、s17 以及生产 Runtime、权限、评测和恢复问题，适合作为独立 Work Pool。

## Start Trigger

- 用户明确说“开始 W-2026-020”；
- 或明确说“开始研究 Agent 之间的协作方式”；
- 启动时按 [`specs/README.md`](../README.md) 创建对应 Change，并移除本 Work Pool 文件；
- 进入真实项目调研前，重新核验版本、Commit、许可证、活动状态和当前官方资料。

## Boundaries

- 当前只登记学习任务，不安装外部框架、不运行生产项目、不修改 s15 行为逻辑；
- 主要研究 Agent-to-Agent 协作，不把普通 Background Task 或确定性 Workflow 当作 Agent 协作模式；
- 不假设“跨 Session”天然意味着 Peer-to-Peer；
- 不把 Agent 数量、层级深度或消息数量本身当作质量证明；
- 不把模型生成的自然语言结果当作最终完成验证。

## Non-goals

- 不构建通用 Agent 通信协议或消息中间件；
- 不重复承担 W-2026-004 的全部 Subagent Runtime 调研；
- 不重复承担 W-2026-015 的全部运行时消息注入治理；
- 不默认实现多层 Team，只有评测证明协作收益超过协调成本时才考虑。

## Related

- [`s06 Subagent`](../../s06_subagent/README.md)
- [`s15 Agent Teams`](../../s15_agent_teams/README.md)
- [`s15 学习笔记`](../../s15_agent_teams/LEARNING_NOTES.md)
- [`W-2026-004：生产级 Subagent Runtime`](./W-2026-004-study-production-subagent-runtime.md)
- [`W-2026-015：Agent 消息注入、插队与运行时事件交付`](./W-2026-015-study-agent-message-injection-steering.md)
- [`W-2026-018：Agent Team 层级设计与委派拓扑权衡`](./W-2026-018-study-agent-team-hierarchy-and-delegation.md)
- [`W-2026-019：持久 Teammate 生命周期、Idle Loop 与唤醒`](./W-2026-019-study-persistent-teammate-lifecycle.md)
