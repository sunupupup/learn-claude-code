# W-2026-021：生产级 Agent 权限、授权与审批治理

- Status: ready
- Area: Agent Permission / Authorization / Approval / Runtime Security / Multi-Agent Governance
- Difficulty: D2 → D3（从 Tool 审批流程进入生产级身份、授权、隔离、审计和恢复）
- Discovered From: s15 Agent Teams 对权限冒泡、`permission_request`、`permission_response` 和 Teammate/Lead 审批链路的讨论
- Owner: personal
- Priority: high

## Objective

建立生产级 Agent Permission 的完整心智模型：能够区分模型提出 Tool 调用、Runtime 权限策略、用户审批、Sandbox 隔离和最终执行之间的职责，并能设计多 Agent 场景下的最小权限、授权委派、审批、撤销和审计机制。

核心问题不是“遇到危险 Bash 时弹不弹窗”，而是：

> 哪个主体，以什么身份，在什么资源范围内，基于哪条策略，获得了执行哪个动作的授权；授权如何被审批、限制、撤销、记录和验证。

## Problem Statement

s15 README 展示了权限冒泡：Teammate 发现需要审批的操作后，把 `permission_request` 发给 Lead；Lead 的 poller 将请求路由到审批队列；用户批准后，Lead 再通过 `permission_response` 通知 Teammate。

但这只覆盖了“权限请求如何传递”，没有回答生产系统的完整问题：

- Agent、Lead、Teammate 和用户分别是谁，代表谁执行操作？
- Tool Schema、Runtime Policy、用户授权和 Sandbox 隔离分别负责什么？
- 哪些操作自动允许、需要询问、必须拒绝？
- Teammate 能否继承 Lead 的权限，还是必须获得独立授权？
- 用户的一次批准覆盖一次调用、一个任务、一个 Session，还是一段时间？
- 请求等待审批时，模型调用、Tool、副作用和消息如何暂停与恢复？
- 批准过期、撤销、重复投递、进程崩溃和部分执行时如何处理？
- 如何防止 Agent 变成拥有更高权限的 Confused Deputy？
- 如何证明某次副作用确实经过了正确的策略判断和用户授权？

## Stable Mental Model

```text
User / Tenant Identity
          ↓
Agent Identity + Delegation Scope
          ↓
Policy Engine：Tool × Resource × Action × Condition
          ↓
      allow / ask / deny
          │
          ├─ allow → Sandbox / Executor
          ├─ ask → Approval Workflow → approved / rejected / expired
          └─ deny → 不执行，并返回结构化原因
          ↓
Audit / Trace / Revocation / Evaluation
```

多 Agent 权限冒泡只是其中的消息路径：

```text
Teammate Runtime
  → permission_request
  → Lead / Control Plane
  → User Approval
  → permission_response
  → Teammate Runtime
```

Lead 是请求路由和团队协调节点，不应因为能代收请求就自动拥有无限审批权。

## 需要分开的概念

| 概念 | 解决的问题 | 不能替代什么 |
| --- | --- | --- |
| Tool Schema | Agent 可以提出什么调用 | 不等于已授权或已执行 |
| Agent 判断 | 是否应该尝试调用某个 Tool | 不能作为最终安全边界 |
| Runtime Policy | 当前主体是否可执行当前动作 | 不能代替用户对高风险动作的明确批准 |
| User Approval | 用户是否同意某个具体副作用 | 不等于永久授予所有未来权限 |
| Sandbox / Isolation | 文件、网络、进程和凭证的实际边界 | 不能替代授权策略和审计 |
| Guardrail | 识别或阻止部分风险行为 | 不能替代认证、授权和隔离 |
| `AskUserQuestion` | 询问偏好、补充信息或业务选择 | 不等于 `permission_request` |
| Permission Bubbling | 把子 Agent 的请求路由给有审批能力的上层 | 不等于权限自动继承 |

## Recommended Learning Order

1. 回看 s15：理解权限请求如何通过 inbox 从 Teammate 冒泡到 Lead；
2. 回看前面章节的 Tool 执行、路径限制和用户交互机制，区分“能调用”“被允许”“已执行”；
3. 建立 `allow / ask / deny` 决策模型，研究 Tool、参数、资源、用户策略和环境如何共同影响判断；
4. 研究身份与授权委派：User、Lead、Teammate、Service Account、Tenant 和 Run 如何关联；
5. 研究文件系统、Shell、网络、Secrets、数据库和云资源的 Sandbox/Isolation 边界；
6. 设计异步审批协议：request ID、幂等、范围、TTL、撤销、拒绝原因、超时和恢复；
7. 研究副作用安全：审批前后、取消、重试、部分执行和重复执行的状态管理；
8. 建立审计、Trace、Eval 和安全演练，覆盖越权、权限升级、Prompt Injection 和 Confused Deputy；
9. 选择一个真实项目，固定版本/Commit，使用官方资料和维护者源码核验其权限模型，不把产品名词当作语义证明。

## Core Questions

- Permission 的主体是用户、Lead、Teammate、进程还是服务账号？
- Teammate 是否可以继承 Lead 的权限？如果可以，继承的最大范围是什么？
- `allow / ask / deny` 由谁决定，策略匹配的是 Tool 名称、参数、路径、网络目标还是业务资源？
- 用户批准如何绑定到 request ID、Tool 参数、资源范围、任务、Session 和租户？
- 审批是否一次性、可复用、可撤销、可过期？如何防止旧批准被重放？
- Permission 请求等待期间，模型调用、Tool 执行、消息消费和副作用处于什么状态？
- Teammate 崩溃、Lead 重启或用户断线后，未完成审批如何恢复？
- 如何防止拥有用户凭证的 Agent 代表用户执行超出用户意图的操作？
- `AskUserQuestion`、Permission Prompt、Guardrail、Sandbox 和 IAM 的边界如何测试？
- 审计记录是否能回答：谁、何时、基于哪条策略、批准了哪个参数、产生了什么副作用？

## Expected Output

- 一张 Permission 分层表：身份、能力、策略、审批、隔离、执行和审计；
- 一份 Tool 风险决策矩阵：自动允许、需要审批、明确拒绝；
- 一个 `permission_request` / `permission_response` 的结构化消息契约；
- 一张审批状态机：requested、pending、approved、rejected、expired、revoked、executing、completed、failed；
- 一份多 Agent 权限委派与防止权限升级的设计说明；
- 一份覆盖 Shell、文件、网络、Secrets、数据库和部署副作用的威胁模型；
- 一组覆盖 Prompt Injection、越权、重复审批、过期批准、崩溃恢复和 Confused Deputy 的 Eval；
- 至少一个真实项目的固定版本权限调用链，以及与 s15 教学版的差异报告。

## Success Criteria

完成后应能够：

1. 解释为什么“Agent 觉得危险”不能替代 Runtime 授权；
2. 区分 Tool 能力、Runtime Policy、用户审批、Sandbox 隔离和审计；
3. 设计 Teammate 权限请求冒泡但不自动扩大权限的协议；
4. 为一个具体 Tool 写出主体、资源、动作、条件、allow/ask/deny 和批准范围；
5. 处理审批等待、超时、撤销、重复消息、崩溃和部分副作用；
6. 用代码、策略测试、Trace 和安全 Eval 证明权限控制确实生效。

## Why Deferred

当前 s15 的主线是 Agent Team 的通信、独立 Loop 和进程内生命周期。权限冒泡只是其中一个控制面示例；完整 Permission 主题会同时涉及身份、授权、沙箱、Secrets、工具副作用、并发、审计和安全评测，因此单独登记为生产级学习任务。

## Start Trigger

- 用户明确说“开始 W-2026-021”；
- 或明确说“开始学习 Agent Permission / 权限审批 / Agent 授权”；
- 启动时按 [`specs/README.md`](../README.md) 创建对应 Change，并移除本 Work Pool 文件；
- 进入真实项目调研前，重新核验版本、Commit、许可证、活动状态和当前官方资料。

## Boundaries

- 当前只登记学习任务，不修改 s15 教学行为逻辑；
- 不假设所有敏感操作都必须弹窗，先区分自动允许、审批和拒绝；
- 不把模型自我判断、自然语言承诺或 Prompt 规则当作最终授权边界；
- 不把 Lead 的消息路由能力当作审批权或用户身份的自动继承；
- 不把 `AskUserQuestion` 与 Permission Approval 混为一谈；
- 不把 Sandbox、Guardrail 或 IAM 中任一单独机制当作完整权限系统。

## Non-goals

- 不在本任务中实现通用 IAM、企业 RBAC/ABAC 平台或完整云权限系统；
- 不默认实现生产级 Sandbox、Secrets Manager 或审批 UI；
- 不重复承担 W-2026-007 的全部副作用 Tool 安全学习；
- 不重复承担 W-2026-017 的全部 Python 锁与并发课程；
- 不根据某个厂商 README 的函数名推断所有 Agent Runtime 的通用行为。

## Related

- [`s15 Agent Teams`](../../s15_agent_teams/README.md)
- [`s15 学习笔记`](../../s15_agent_teams/LEARNING_NOTES.md)
- [`W-2026-007：副作用 Tool 安全`](./W-2026-007-study-side-effect-tool-security.md)
- [`W-2026-015：Agent 消息注入、插队与运行时事件交付`](./W-2026-015-study-agent-message-injection-steering.md)
- [`W-2026-017：Python 锁与 Agent 并发状态治理`](./W-2026-017-study-python-locks-and-agent-concurrency.md)
- [`W-2026-019：持久 Teammate 生命周期、Idle Loop 与唤醒`](./W-2026-019-study-persistent-teammate-lifecycle.md)
