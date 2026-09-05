# W-2026-007：生产级副作用 Tool 的分层安全与业务接入学习

- Status: ready
- Area: Agent Harness / Tool Calling / Authorization / Idempotency / HITL / Durable Execution / Audit
- Difficulty: D2 → D3
- Discovered From: `s08_context_compact` 中创建工单、Tool Result 压缩、权限与重复调用讨论
- Owner: personal
- Priority: high

## Objective

选择“创建工单、查询订单状态、代用户下单”三个逐级增加风险的场景，研究真实开源项目如何把 Agent 的 Tool 调用接入生产业务系统，并通过分层防护处理权限、审批、重复调用、执行结果不确定、撤销补偿、审计与结果压缩。

重点不是找到一个包办所有安全问题的 Agent 框架，而是理解每一层必须承担什么责任，以及为什么最终安全不能只依赖模型、Prompt 或 Harness：

```text
模型：提出动作和参数
  ↓
Harness / Agent Runtime：策略检查、预算、审批、暂停恢复和轨迹记录
  ↓
Tool Adapter / Gateway：Schema 校验、身份传递、业务 API 映射和结果过滤
  ↓
业务服务：最终鉴权、幂等、事务、数据库约束、审计和补偿
  ↓
Tool Result 压缩器：保留业务状态、操作凭证、重试策略和原结果引用
```

## Stable Mental Model

> 模型只能提出动作，Harness 决定是否允许进入执行流程，业务服务负责最终保证执行安全。

“Harness 允许”不等于“业务服务必须执行”；业务服务仍要根据可信身份、租户、资源关系和当前业务状态再次鉴权，并通过幂等记录、事务与数据库约束抵抗重复请求和并发竞争。

Tool Result 压缩也属于安全链：如果压缩后丢失“已经执行成功”“创建了哪个资源”“是否允许重试”等事实，Agent 可能重复执行有副作用的动作。

## Assumptions

1. 当前条目只进入 Work Pool，不立即下载项目、安装依赖或修改现有 Harness。
2. 三个场景使用同一套分层框架分析，但风险策略不同，不强行设计成完全相同的 Tool。
3. 前端与 Agent 可以复用同一个底层业务能力；是否共用 Web BFF 入口由身份、契约、流量与安全边界决定。
4. 请求体中的 `source: agent` 或 `is_agent: true` 只能作为普通元数据，不能作为可信授权依据；调用身份应来自经过验证的凭证与服务端上下文。
5. Agent 代表用户行动时，至少同时考虑用户权限、Agent/客户端权限、租户范围和资源级权限；原则上使用二者交集，而不是让 Agent 继承后台服务的全部权限。
6. 幂等不等于不重试；它使同一业务意图的重试不会产生额外副作用，但仍需定义作用域、冲突参数、保留期限与并发行为。
7. Human-in-the-loop（HITL，人在回路）审批不是最终授权，也不能替代业务服务校验。
8. 开源 Demo 用于学习调用链和机制，不直接视为生产安全证明。

## Scenario Ladder

### 场景 A：智能客服查询订单状态

- 风险：只读，但可能越权读取他人订单、泄露地址/电话/支付信息；
- 重点：用户与订单关系校验、租户隔离、字段脱敏、速率限制、缓存与审计；
- 默认策略：通常无需人工审批，但必须由业务服务执行资源级授权；
- Tool Result：只返回当前回答所需字段，不把完整订单和敏感信息无边界放入 Context 或 Trace。

### 场景 B：Agent 创建工单

- 风险：可重复产生资源、发送通知或触发后续自动化；
- 重点：`Idempotency-Key`、重复检测、创建结果查询、通知去重、响应丢失后的核对；
- 默认策略：低风险工单可按规则自动创建，高敏感分类或高频创建进入审批/限流；
- Tool Result：保留 `status`、`ticket_id`、`operation_id`、`idempotency_key`、`retry_policy` 与 `result_ref`。

### 场景 C：智能客服代用户下单

- 风险：库存、价格、地址、优惠、支付和法律承诺会形成高价值副作用；
- 重点：报价快照、参数预览、明确确认、支付授权、库存并发、订单幂等、部分成功、取消和退款补偿；
- 默认策略：把“生成购物车/报价”和“提交订单/支付”拆成不同 Tool，高风险提交前必须基于最终参数审批；
- Tool Result：保留订单/支付状态、金额与币种摘要、操作 ID、幂等键、下一步状态查询入口，禁止看到超时就盲目重下单。

## Layered Responsibility Matrix

| 层级 | 必须研究的责任 | 不能只依赖这一层解决的问题 |
| --- | --- | --- |
| 模型 | Tool 选择、参数生成、识别是否需要更多信息 | 身份真实性、最终授权、数据库一致性 |
| Harness / Agent Runtime | Tool allowlist、参数前置检查、调用预算、风险分类、审批、暂停/恢复、Trace | 服务端最终鉴权、唯一性约束、支付和订单事务 |
| Tool Adapter / Gateway | 输入/输出 Schema、身份与幂等元数据传播、错误归一化、字段过滤 | 仅靠客户端字段防伪、替代业务服务的资源级授权 |
| 业务服务 | AuthN/AuthZ、租户隔离、幂等记录、事务、并发约束、审计、撤销/补偿 | 决定模型应该在何时调用哪个 Tool |
| Tool Result 压缩器 | 保留状态、资源 ID、操作 ID、幂等键、重试策略和原始结果引用 | 把自然语言摘要当成业务系统权威状态 |

## Core Questions

以后看到一个具有副作用的 Tool，依次回答：

1. 谁能调用？调用时代表谁？权限来自哪里？
2. 是否需要人工确认？确认的是抽象动作还是最终参数快照？
3. 重复调用会怎样？幂等键由谁生成、怎样定作用域和保存多久？
4. 超时后能否安全重试？哪些错误允许自动重试？
5. 执行成功但响应丢失时，怎样查询权威状态而不是猜测？
6. 是否能够取消、撤销或通过补偿操作恢复？部分成功怎样处理？
7. Tool Result 压缩后，是否仍能判断动作已经执行以及下一步允许做什么？
8. 审计记录能否回答谁、何时、代表谁、用什么参数、经过谁批准、产生了什么资源？

额外补充四问：

9. Prompt Injection 或恶意 Tool Result 能否诱导 Agent 越权调用？
10. 并行 Tool Call、Worker 重启和消息重复是否会放大副作用？
11. 前端 BFF、Tool Gateway 和业务服务之间怎样传播用户身份、Agent 身份、租户、Scope、Trace 与幂等键？
12. 哪些结论能用确定性测试验证，而不是只靠模型或人工感觉？

## Open-source Study Samples

正式启动时固定 Commit，并重新核对版本、许可证、活跃度与对应代码路径。初步推荐按以下顺序学习，而不是同时泛读全部仓库。

### 1. 业务样例：OpenAI Customer Service Agents Demo

- Repository: <https://github.com/openai/openai-cs-agents-demo>
- 观察点：客服路由、订单/航班查询、改签取消、补偿类 Tool、用户确认、Guardrail 和前后端交互；
- 实验：把 Mock `cancel` / `book` / `issue_compensation` Tool 替换成带幂等键和状态查询的假业务服务，注入超时与重复提交；
- 边界：仓库明确是 Demo，适合学习业务流程和 Tool 接口，不证明真实支付、授权、事务或恢复已经达到生产级。

### 2. Harness 审批与 Tool Guardrail：OpenAI Agents SDK for Python

- Repository: <https://github.com/openai/openai-agents-python>
- 重点文档：`docs/human_in_the_loop.md`、`docs/guardrails.md`；
- 观察点：`needs_approval`、按调用 ID 审批、`RunState` 序列化与恢复、Tool 输入/输出 Guardrail、审批前后检查、拒绝路径和 Trace；
- 实验：分别给 `query_order`、`create_ticket`、`submit_order` 配置无需审批、条件审批和强制审批，并验证恶意/畸形参数默认拒绝；
- 边界：SDK 的审批和 Guardrail 不能替代下游 Ticket/Order Service 的最终授权与幂等。

### 3. 暂停恢复与重复副作用：LangGraph

- Repository: <https://github.com/langchain-ai/langgraph>
- 观察点：`interrupt`、Checkpoint、Durable Execution、恢复时节点重放、把副作用隔离进 Task、幂等调用与人工修改状态；
- 实验：在审批前后分别放置“创建工单”，恢复同一个 Run，观察错误位置为何会产生重复资源；
- 边界：持久化执行历史不自动提供业务级 exactly-once；外部写操作仍需要幂等键或先查询后创建。

### 4. 后端可靠执行对照：Temporal Python SDK Samples

- Repository: <https://github.com/temporalio/samples-python>
- 观察点：Workflow/Activity 边界、Activity Retry、超时、取消、Signal、Query、OpenTelemetry、外部存储和长任务恢复；
- 实验：把 `submit_order` 作为 Activity，模拟“业务服务已成功、Worker 在记录结果前崩溃”，验证为什么 Activity 本身必须幂等；
- 边界：Temporal 不是权限系统，也不会自动让第三方 API 变成幂等；它用于学习可靠编排和失败恢复。

### 5. 权限策略对照：OpenFGA 或 Open Policy Agent

- OpenFGA: <https://github.com/openfga/openfga>
- Open Policy Agent: <https://github.com/open-policy-agent/opa>
- OpenFGA 观察点：用户、关系、资源与细粒度访问控制，例如“客服是否能读取/操作这个客户的订单”；
- OPA 观察点：把调用者、Tool、资源、金额、环境和审批状态作为上下文，返回允许/拒绝策略决定；
- 实验：实现“用户可查自己的订单；客服可查被分配客户的订单；Agent 只能在用户权限与自身 Scope 交集内行动”；
- 边界：策略引擎给出 Decision，Tool Gateway 和业务服务必须真正 Enforcement；不能把 `allow: true` 只写进 Prompt。

资料初步检索日期：2026-09-04。

## Learning Plan

### Track A：Tool 契约与风险分级

- 将 Tool 分成只读、可逆写入、幂等写入、非幂等写入、高价值/不可逆操作；
- 为每个 Tool 写输入/输出 Schema、调用身份、权限、审批、幂等、超时、重试、补偿和审计契约；
- 区分“模型建议调用”“Harness 准许调用”“业务服务授权执行”三种不同状态；
- 设计机器可读的拒绝结果：缺少权限、等待审批、永久禁止、参数冲突和业务状态不允许。

### Track B：身份与授权传播

- 区分最终用户、Agent Runtime、Tool Gateway、后台服务账号和审批人；
- 研究用户代理/委托身份、短期凭证、Scope、Audience、租户和资源级权限；
- 比较前端与 Agent 共用同一 API、使用不同 BFF、共同调用领域服务三种结构；
- 验证请求体伪造 `source`、用户 ID 或租户 ID 时服务端仍会拒绝。

### Track C：幂等、重试与执行结果不确定

- 定义幂等键生成者、唯一索引、作用域、TTL、请求参数 Hash 和冲突处理；
- 区分请求发送失败、业务执行失败、执行成功但响应丢失、部分成功；
- 设计 `operation_id` 状态查询和 reconciliation（对账/核对）流程；
- 注入网络超时、消息重复、并发请求、Worker 崩溃和恢复重放；
- 证明最终副作用次数符合预期，而不只验证 Agent 最终回答。

### Track D：HITL、撤销与补偿

- 风险策略决定哪些 Tool 无需审批、条件审批、每次审批或永久禁止；
- 审批界面展示最终对象、金额、收件人/地址和不可逆影响；
- 审批绑定 `tool_call_id` 与参数 Hash，参数变化后旧批准失效；
- 对创建工单设计关闭/撤销，对订单设计取消/退款，对不可逆动作设计人工升级；
- 处理等待审批期间状态变化、超时、拒绝、取消和断线恢复。

### Track E：Result、Context、Trace 与 Audit

- 区分模型可见的 Tool Result、Harness State、业务数据库权威状态、Trace 和 Audit Log；
- 为有副作用结果保留资源 ID、操作 ID、幂等键、状态、重试策略和原结果引用；
- Trace 关联 Run、Tool Call、审批与业务操作，但敏感正文最小化；
- Audit Log 使用不可混淆的 Actor、On-behalf-of User、Decision、Reason 和业务结果；
- 与 [`W-2026-006`](./W-2026-006-study-tool-result-compaction-and-recovery.md) 联动验证压缩后的恢复安全，不重复维护其压缩算法细节。

## Minimal Implementation Exercise

构造一个不接真实支付的本地客服系统：

```text
query_order(order_id)
create_ticket(order_id, reason, idempotency_key)
prepare_order(items) -> quote_id
submit_order(quote_id, idempotency_key) -> approval -> order_id
get_operation(operation_id)
cancel_order(order_id, idempotency_key)
```

至少实现：

- 假身份与资源级授权；
- Harness Tool allowlist 和风险策略；
- `submit_order` 参数预览与人工批准；
- 数据库唯一约束或等效幂等记录；
- 操作状态查询、超时恢复与重复请求；
- Tool Result 压缩和原结果引用；
- Trace/Audit 中 Actor、Tool Call、Approval、Operation、Resource 的关联。

## Eval And Failure Injection

冻结 15-25 条用例，至少覆盖：

1. 用户查询自己的订单成功，查询他人订单被业务服务拒绝；
2. Agent 拥有高权限服务凭证但用户无权操作时仍被拒绝，防止 Confused Deputy；
3. 相同工单请求重复三次只创建一个资源；
4. 相同幂等键携带不同参数时拒绝并记录冲突；
5. 下单审批后参数被修改，旧批准不可复用；
6. 下单成功但响应丢失，Agent 查询状态而不是重新下单；
7. Worker 在副作用后崩溃并恢复，订单数仍为一个；
8. Tool Result 被恶意文本注入时不能绕过权限或审批；
9. Tool Result 压缩后仍能恢复业务状态且不会盲目重试；
10. Trace 与 Audit 能还原调用者、代理用户、批准人、参数摘要和业务结果；
11. 敏感字段不会进入模型 Context、普通日志或无权限调用者响应；
12. 业务服务、策略引擎或审批服务不可用时，高风险动作 fail closed（默认拒绝或暂停）。

优先使用确定性断言：数据库行数、唯一索引、资源状态、幂等记录、权限 Decision、参数 Hash、审批状态、审计事件和副作用调用次数。LLM Judge 只评价自然语言解释质量。

## Boundaries

- Always：业务服务执行最终鉴权；副作用有稳定操作凭证；自动重试前先确认幂等与错误类型；批准绑定具体参数；记录可审计的身份与状态变化。
- Ask first：连接真实客服、工单、订单或支付系统；使用真实用户凭证；执行会产生费用、通知或外部资源的 Tool；安装或运行候选开源项目。
- Never：用 Prompt 或 `source: agent` 代替授权；超时后盲目重做写操作；把 Harness 审批当作业务服务授权；在日志/Context 中无边界保存订单、地址、支付或凭证数据。

## Start Trigger

当前任务只进入 Work Pool，不自动开始。建议完成 `s08_context_compact`、`s11_error_recovery` 和基础 Tool Calling 学习后，先启动场景 A-B；学习后台任务与持久状态后再进行场景 C 和 Worker 崩溃恢复实验。

## Success Criteria

完成后应能够：

1. 画出模型、Harness、Tool Gateway、业务服务、压缩器、Trace 与 Audit 的责任边界；
2. 为查询订单、创建工单和代用户下单分别设计权限、审批、幂等与恢复策略；
3. 从至少三个开源项目追踪审批、耐久执行、授权或幂等的一条真实代码路径；
4. 用故障注入证明超时、重复消息、恢复重放不会重复产生关键副作用；
5. 用确定性测试证明用户权限与 Agent 权限的交集被真正执行；
6. 解释为什么 Guardrail、HITL、业务鉴权、幂等和 Tool Result 压缩缺一不可且不能互相替代。
