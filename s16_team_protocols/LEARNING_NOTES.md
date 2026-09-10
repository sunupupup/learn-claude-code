# s16 Team Protocols 学习笔记

> 学习状态：核心概念已建立，部分问答已通过，继续进行本章验收。
>
> 事实范围：当前教学代码和本地补充演示是已核验事实；README 中关于真实 CC 的源码说明属于版本相关资料，当前没有在本地重新核验对应 CC 源码。
>
> 本轮整理依据：`PROMPT_2_analysis_my_note.md`、当前章节 README、`code.py` 的本次 Git Diff、已有学习笔记和相关 Work Pool。

## 1. 本章核心结论

### 1.1 本章增强的是消息的消费方式

Inbox / MessageBus 仍然是统一的消息传输通道。变化在于：Runtime 根据消息的 `type` 选择不同的消费者。

```text
普通 message
  → 注入 Agent 上下文
  → 由模型理解和决定

协议消息
  → Runtime 根据 type 路由
  → handler 执行确定性动作
  → 必要时更新状态或再次注入上下文
```

专业表述：

> Inbox 是统一的消息传输通道，`type` 是消费路由键。普通消息进入 Agent 上下文，协议消息进入 Runtime Handler；Runtime 负责确定性地执行状态迁移或生命周期动作。

这并不表示协议消息使用了另一条传输通道。`shutdown_request` 仍然是一条 Message，只是它带有更强的协议语义。

### 1.2 Message、Protocol、Workflow 不是同一个概念

```text
Message  = 一条数据
Protocol = 消息 + 类型 + 字段约束 + 顺序 + 回复规则
Workflow = 多个步骤 + 状态 + 失败处理组成的固定流程
```

例如，`shutdown_request` 是一条 typed message；“请求 → 确认 → 退出”才是 shutdown protocol；如果再加入安全边界、清理、超时和重试，就形成更完整的 shutdown workflow。

### 1.3 Runtime 和模型各自负责什么

适合固化为 Runtime 行为的特征是：输入结构明确、动作确定、状态可定义，并且不需要模型猜测语义。

```text
LLM：提出意图或做需要理解的判断
  → Runtime：校验、路由
  → Workflow：执行确定性步骤
  → Runtime：返回状态和结果
  → LLM：决定下一步
```

关机、状态迁移、审计日志等适合下沉到 Runtime；判断一个计划是否合理，通常仍需要 Lead、模型或人工。当前 s16 的计划审批是混合模式：Runtime 维护协议状态，模型仍可能参与下一步行为，而且教学代码没有真正的 Tool 执行门控。

### 1.4 协议的价值不在于“多发了一条消息”

从传输层看，用户的直觉完全成立：`shutdown_request` 仍然是通过 `BUS.send()` 写进对方 inbox 的一条 Message，和普通 `send_message` 共享同一个通道。新增的价值来自**消费路径和约束**：

```text
普通 message
  → 注入模型上下文
  → 由 LLM 理解“这句话要我做什么”

typed protocol message
  → Runtime 按 type 路由
  → handler 校验字段、匹配请求、更新状态
  → 必要时再把结果注入模型上下文
```

因此，协议化并不是为了让消息“更容易传过去”，而是为了让某些结果不依赖模型猜测，并且能被 Runtime 追踪和校验。当前教学版能证明的是路由、匹配和状态转换；它还没有提供可靠队列、完整清理、权限门控或崩溃恢复，所以用户体感上确实可能只是“增强了消息处理方式”，而不是获得了完整生产能力。

## 2. 核心术语

| 术语 | 中文理解 | 当前代码中的位置 | 重要边界 |
|---|---|---|---|
| Harness | 包围模型的执行框架 | 整个 `code.py` | 不等于模型能力 |
| Runtime | 驱动模型、Tool、消息和状态的运行时 | `agent_loop`、线程和 handler | 负责确定性控制 |
| Lead | 团队协调与汇总者 | 主 Agent | 通常承担最终验收责任 |
| Teammate | 有独立上下文和 Loop 的队友 | `spawn_teammate_thread` | 当前只在进程内存活 |
| MessageBus | 消息传输通道 | `MessageBus.send/read_inbox` | 当前没有可靠队列语义 |
| Inbox / Mailbox | 某个 Agent 的收件箱 | `.mailboxes/*.jsonl` | 当前读取会删除文件 |
| Envelope | 消息外壳 | `from/to/type/metadata/content` | 包装数据，不等于协议本身 |
| Payload | 消息的具体内容 | `content`、`payload` | 需要和控制字段分开理解 |
| Message Type | 消息类型和路由键 | `message`、`shutdown_request` 等 | 不同 type 进入不同消费者 |
| Protocol | 消息交互契约 | shutdown、plan approval | 不一定需要独立传输通道 |
| Request-Response | 请求与响应成对出现 | request / response | 需要关联规则 |
| Handshake | 请求方与接收方完成确认 | shutdown 握手 | 不是立即强杀线程 |
| `request_id` | Correlation ID，关联请求与响应 | `pending_requests` 的 key | 不自动等于幂等键 |
| ProtocolState | 一次协议请求的状态记录 | `ProtocolState` | 当前只在内存中 |
| Pending Request | 已发送但尚未结束的请求 | `status="pending"` | 不等于任务看板任务 |
| FSM | Finite State Machine，有限状态机 | `pending → approved/rejected` | 当前状态集合很简化 |
| Dispatch / Route | 根据 type 选择处理路径 | `handle_inbox_message` | 是消费入口，不是业务完成证明 |
| Handler | 处理某类消息的函数 | shutdown / plan 分支 | 应有明确输入和副作用 |
| Consumer | 实际消费消息的组件 | Runtime 或 Agent Context | 不同消息可有不同 Consumer |
| Context Injection | 将消息放入模型上下文 | 追加到 `messages/history` | 注入后仍需模型理解 |
| Idle Loop | 暂时无工作但不退出 | Teammate 内层等待循环 | 不等于 completed 或 durable |
| Graceful Shutdown | 收尾、确认后退出 | `shutdown_request` handler | 当前没有完整清理流程 |
| Approval Gate | 批准后才能进入下一阶段 | plan approval 的概念 | 当前没有真正拦截 Tool |
| Permission Gating | 对具体高风险动作做授权拦截 | 当前教学版省略 | 不等同于普通 plan approval |
| Durable | 可跨进程或 Session 恢复 | 当前未实现 | 需要持久状态和恢复协议 |
| Workflow | 多步、带状态和失败处理的流程 | 可由协议 handler 组成 | route 只是 Workflow 的入口 |

## 3. 我的原始理解与校准

### 3.1 “统一 Message + 不同 type”

我的原始理解：

> 对 `send_message` 的各种 message 进行区分，通过统一的 message 和不同的 type，代替传统的一个行为一个 Tool。

判断：🟡 部分正确。

🔴 已验证理解：MessageBus 层确实复用同一个消息结构和 inbox，通过 `type + metadata` 区分消费路径。

校准后的专业表述：

> MessageBus 是统一传输层；`type` 是路由键。是否给模型暴露独立 Tool，是模型 API 设计选择，不是传输层的必然要求。

当前 `run_send_message()` 只能发送默认的 `type="message"`，而 `run_request_shutdown()` 还会创建 `ProtocolState`、生成 `request_id`，所以当前实现并不是所有行为都由同一个 `send_message` Tool 完成。

证据：`./code.py:376-413`、`./code.py:746-801`。

### 3.2 “重复利用空闲 Teammate”

我的原始理解：

> 这边要重复利用空闲 teammate 了？

判断：🟡 部分正确。

🔴 已验证理解：同一个 Teammate 线程完成一轮后进入 idle，收到普通消息后继续使用自己的上下文和身份；这不是线程池把一个新任务随意分配给陌生 Worker。

准确表述：

> s16 支持进程内、线程生命周期内的 Teammate 驻留和唤醒，但不是跨进程、跨 Session 的 Durable Teammate。

证据：`./code.py:618-682`。生产级 idle、ack、重试、崩溃恢复和 checkpoint 暂缓到 [W-2026-019](../specs/work-pool/W-2026-019-study-persistent-teammate-lifecycle.md)。

### 3.3 “为什么 Lead 要新增 Tool”

我的原始疑问：

> 为什么不把 request shutdown 放进 send_message？

判断：🟡 这是合理的架构选择问题，不存在唯一答案。

可以使用：

```text
request_shutdown(teammate)
```

也可以使用：

```text
send_message(to, content, type="shutdown_request")
```

如果采用第二种方式，通用入口仍必须负责创建状态、生成 ID、校验字段、验证权限并路由 handler；此时它实际上就是一个通用协议消息入口。

当前实现将 `request_shutdown` 作为高层 Tool，主要是让模型看到更明确的能力边界。这个 Tool 划分不是协议成立的必要条件。

### 3.4 `match_response` 的作用

我的原始理解：

> 它是不是只改了一个全局变量？上面拦了错误的 pair，正确的 pair 就把 status 改成 approved 或 rejected。

判断：🟡 基本正确，但“唯一有用”过窄。

🔴 已验证理解：`match_response()` 通过全局 `pending_requests` 找到对应的 `ProtocolState` 对象，并完成：

1. 检查 `request_id` 是否存在；
2. 检查 response type 是否匹配请求类型；
3. 忽略已经结束的重复响应；
4. 将 pending 状态迁移为 `approved` 或 `rejected`。

它修改的是字典中对象的 `status` 字段，不是重新替换整个全局字典。它本身不会插入新的模型消息，也不会自动让 Agent 调整行为。

证据：`./code.py:440-472`。

### 3.5 “为什么只处理这两个 type”

我的原始疑问：

> 为什么这里只处理这俩 type？这俩 type 有什么特殊？

判断：🔴 已验证理解。

`match_response()` 处理的是已注册协议的响应类型，而不是所有 inbox 消息：

```text
shutdown_response
plan_approval_response
```

当前 `ProtocolState.type` 只有：

```text
shutdown
plan_approval
```

`message`、`result`、`shutdown_request` 和 `plan_approval_request` 分别属于普通消息、结果通知、请求消息，不是该函数要匹配的 response。

### 3.6 `request_plan`、`submit_plan`、`review_plan`

我的原始理解：

> `request_plan` 和 `send_message` 没什么区别；Teammate 创建 pending，Lead 更新状态。

判断：🟡 部分正确，并发现了当前实现中一个重要的语义差异。

🔴 已验证理解：`request_plan` 确实只是普通提示消息；真正创建 `pending` 并等待审批的是 `submit_plan`。

准确调用链：

```text
Lead.request_plan
  → 发送普通 type="message"
  → 不创建 pending_requests

Teammate.submit_plan
  → 创建 pending ProtocolState
  → 发送 plan_approval_request

Lead.review_plan
  → 根据 request_id 修改状态
  → 发送 plan_approval_response
```

因此，`request_plan` 是普通提示消息；真正的 plan approval 协议从 `submit_plan` 开始。

“Lead 全权 review”也需要修正：当前 `review_plan()` 不分析计划内容，只接收 Lead/模型传入的 `approve` 布尔值，并执行状态迁移和响应发送。

证据：`./code.py:720-789`。

### 3.7 “某些明确任务可以固化为 Runtime Workflow”

我的原始理解：

> 我让你做一件非常明确的事，例如关机、同意、打日志，这种完全 Runtime 的功能可以用 message route 实现。

判断：🟡 部分正确；“明确”是必要方向，但不是唯一条件。

🔴 已验证理解：输入结构、消费路由和 Runtime handler 可以把关机这类确定性动作从 LLM 判断中拿出来。

更完整的判断条件是：输入结构明确、动作确定、权限主体清楚、状态迁移可定义，并且不需要模型猜测语义。

关机可以固化成：

```text
shutdown_request
  → 校验请求
  → 到达安全边界
  → 回复确认
  → 清理状态
  → 退出线程
```

“是否应该批准计划”通常不是纯 Runtime 决策；但收到明确的 `approve=true` 后，Runtime 可以确定性地更新状态并发送响应。

### 3.8 “没有 `request_id` 和 `pending` 也能工作吗”

我的原始理解：

> 这边就算没有 `request_id` 和 `pending` 状态，照样能工作吧？Lead 给 Teammate 发一句“我同意你刚才的 xxx plan”，完全也能实现这个功能。

判断：🟡 部分正确。

🔴 已验证理解：在单请求、顺序稳定的 happy path 中，没有 `request_id` 和 `pending` 也可能完成批准；它们主要用于可靠关联和生命周期追踪。

这里要区分两个问题：

1. **功能是否能跑通（functional sufficiency）**：如果同一时间只有一个计划、消息严格按顺序到达、双方共享足够上下文、没有重试或延迟，那么自然语言确实可以完成批准。此时 `request_id` 和 `pending` 不是功能成立的绝对前提。
2. **协议是否能可靠工作（protocol robustness）**：一旦出现并发计划、乱序、延迟、重复响应、进程重启、超时重试或审计需求，仅靠“你刚才的计划”就不够了。字段和状态用于消除歧义、跟踪生命周期，而不是为了让最短路径勉强跑起来。

最典型的歧义是：Alice 先后提交 Plan A 和 Plan B，Lead 只回复“我同意你刚才的计划”。Alice 可能必须反问“你同意的是哪个？”；如果她猜错，就可能执行错误的计划。`request_id` 让响应明确关联某一次请求，`pending` 则记录该请求是否仍在等待结果：

```text
没有 request_id：靠上下文猜“刚才是哪一个”
有 request_id：按 ID 精确关联 request ↔ response

没有 pending：只能看到一条消息
有 pending：知道请求是否 in-flight、已结束或已被重复响应
```

因此，`request_id` 主要解决 **correlation（关联）**，`pending` 主要表达 **lifecycle state（生命周期状态）**。二者也不是万能的：`request_id` 不自动提供幂等性、权限或投递保证；`pending` 不代表计划内容正确，也不等于真正的执行拦截。它们把“能沟通”提升为“可追踪、可校验、可恢复的协议”。

这也解释了本章的核心取舍：`MessageBus/inbox` 可以保持统一，消息是否成为严格协议，取决于它是否定义了结构化字段、状态转换、响应匹配和失败处理。

### 3.9 本次 inline comments 的结论速览

| 我的注释关注点 | 校准后的结论 |
|---|---|
| “为什么不能全部用 `send_message`？” | 可以统一为一个传输入口；独立 Tool 只是让模型看到更清晰的能力边界。统一入口仍需要按 `type` 路由并执行协议校验。 |
| “是不是要重复利用空闲 Teammate？” | 是驻留线程进入 idle 并等待唤醒，不是创建新 Worker；当前只在进程内成立。 |
| “为什么多了三个 Lead Tool？” | `request_shutdown`、`request_plan`、`review_plan` 是高层 API 设计，不是 MessageBus 的硬性要求。 |
| “`match_response` 只是改全局变量吗？” | 它通过 `request_id` 和 response type 做关联、类型校验、重复保护，并更新 `ProtocolState.status`；它本身不负责让 LLM 改变行为。 |
| “为什么只处理两个 response type？” | 因为当前状态机只注册 shutdown 和 plan approval 两类请求，匹配函数只消费它们的响应。 |
| “Teammate 还是 Agent Loop 处理 inbox 吗？” | 是，但先经过 Runtime dispatch；普通消息进入上下文，shutdown 由 handler 直接回复并退出，plan response 才注入上下文。 |
| “最外层 loop 看起来只是把 inbox 放进 history？” | 外层负责 Lead 侧统一消费、协议状态更新和上下文注入；Teammate 内层 loop 才展示收到消息后的继续工作或退出行为。 |
| “没有 ID 也可以工作吧？” | 简单线性场景可以；并发计划、乱序、重试、重复响应和审计场景必须显式关联。 |

这组注释的共同主题不是“增加了多少 Tool”，而是：**同一条 Message 进入哪个 Consumer，以及这个 Consumer 是否需要确定性地维护状态和副作用。**

## 4. 关键调用链

### 4.1 Shutdown request-response

```text
Lead.request_shutdown(teammate)
  → new_request_id()
  → pending_requests[req_id] = ProtocolState(status="pending")
  → BUS.send(type="shutdown_request", metadata={request_id})
  → Teammate.read_inbox()
  → handle_inbox_message()
  → BUS.send(type="shutdown_response", approve=True)
  → Lead.consume_lead_inbox()
  → match_response()
  → pending_requests[req_id].status = "approved"
  → Teammate 退出 Loop
```

注意：当前 Teammate 收到 shutdown 后直接回复 `approve=True`，没有真正验证所有副作用已经完成。它也只在 inbox 检查边界处理请求，不是实时强制中断。

### 4.2 Plan approval

```text
Lead.request_plan()
  → 普通 message，提醒 Teammate 提交计划

Teammate.submit_plan(plan)
  → 生成 request_id
  → 创建 pending ProtocolState(type="plan_approval")
  → 发送 plan_approval_request

Lead.check_inbox()
  → 看见计划
  → Lead.review_plan(request_id, approve)
  → 更新 ProtocolState
  → 发送 plan_approval_response

Teammate inbox handler
  → 追加 [Plan approved] 或 [Plan rejected]
  → 下一次 LLM 调用看到上下文
```

教学版没有实现“未批准就禁止 bash/write_file”的执行门控，所以批准状态不等于 Tool 已被 Runtime 阻止或允许。

### 4.3 Lead inbox 的两条后续路径

```text
consume_lead_inbox()
  → 先对 response 调用 match_response()
  → 返回原始 msgs

路径 A：Lead 在当前 Turn 调用 check_inbox
  → msgs 作为 Tool Result 返回
  → 模型可以在当前 Turn 继续反应

路径 B：外层 main loop 末尾消费
  → msgs 被追加为 history 中的 user message
  → 通常等下一次用户输入才再次调用 Lead agent_loop
```

`match_response()` 负责 Runtime 状态；消息注入负责让模型知道发生了什么。这是两条并行路径。

### 4.4 Teammate idle loop

```text
LLM 返回非 tool_use
  → 进入 idle
  → 每秒轮询 inbox
  → 普通消息：追加 messages，回到 LLM
  → shutdown_request：回复并退出
```

本地补充文件 [code_idle_notification.py](./code_idle_notification.py) 是一个无 LLM 的模拟演示，用两层循环展示：

```text
完成工作
  → result
  → idle_notification
  → Lead 分配新任务或请求 shutdown
  → 再次工作或退出
```

它补充演示了 README 提到、但基础 `code.py` 省略的 `idle_notification`；它不是对基础实现已经具备该能力的证明。

## 5. 状态模型

### 5.1 协议状态

```text
不存在
  → pending
  → approved
  → rejected
```

当前代码没有 timeout、expired、revoked、executing、completed 等生产级状态。

### 5.2 Teammate 生命周期

```text
未创建
  → working
  → idle
  → working
  → shutdown_requested
  → terminated
```

`idle` 不是 `completed`：idle 表示仍存活并等待工作；`terminated` 才表示线程退出。`idle` 也不是 `durable`：当前进程退出后，线程上下文不会自动恢复。

### 5.3 消息消费状态

```text
写入 .jsonl
  → read_inbox 读取
  → 路由给 Runtime 或注入 Agent
  → unlink 删除文件
```

这只是教学版的消费式文件通道，不等于可靠消息队列。当前没有文件锁、ack、重试、过期、原子 claim 或持久协议状态。

## 6. 已确认的实现边界和失败场景

### 6.1 `match_response` 已提供的保护

- unknown `request_id`：忽略；
- response type 与 request type 不匹配：忽略；
- 已经结束的请求再次收到 response：忽略。

### 6.2 当前实现仍存在的缺口

1. `run_review_plan()` 没有先检查 `state.type == "plan_approval"`，错误传入 shutdown request ID 时可能提前修改状态；
2. plan approval 没有真正拦截 `bash`、`write_file`；
3. shutdown handler 默认批准，没有完整的收尾证据；
4. `pending_requests` 是进程内全局字典，没有持久化、锁或恢复；
5. MessageBus 使用 read + unlink，没有 ack、重试和可靠消费语义；
6. Teammate 在模型调用或 Tool 执行期间不会实时处理 shutdown；
7. `request_id` 只负责关联请求和响应，不自动提供幂等性；
8. `idle_notification`、崩溃恢复和 Checkpoint 不在基础教学代码中。

### 6.3 普通消息重试不是可靠协议重试

如果 Lead 没收到 response，可以继续轮询或设计重试；但不能只重复发送自然语言提醒。可靠重试至少需要考虑：

```text
逻辑 request_id
  → attempt 次数
  → timeout / backoff
  → 重复请求处理
  → 响应丢失后的幂等
```

这些内容属于后续生产级学习，不应从当前 Demo 的状态机中推断为已经实现。

### 6.4 “能工作”与“可靠工作”不是同一个验收标准

普通自然语言消息在单线程、单请求、顺序稳定的场景里可能已经足够；这证明的是 **happy-path 可行性**，不等于协议设计已经完整。评估一个消息机制时，至少要分别问：

```text
它能不能把意图送到对方？              → 基础通信
它能不能确定这次响应对应哪个请求？      → correlation
它能不能识别 pending / completed / duplicate？ → lifecycle
它能不能在超时、重试、崩溃后恢复？       → reliability / recovery
它能不能阻止未批准的实际动作？           → enforcement / permission gate
```

`request_id` 和 `pending` 主要补强中间两层；它们不能替代语义判断、权限校验、可靠投递或真正的执行 gate。

## 7. 当前掌握状态

### 已达到或基本达到

1. 能解释 Agent Team 是 Harness / Runtime 层的协作拓扑；
2. 能区分普通 Message、typed protocol message 和 Workflow；
3. 能说明 `type` 如何改变 inbox 的消费路径；
4. 能描述 `request_shutdown → response → match_response` 的完整调用链；
5. 能区分 `request_plan`、`submit_plan` 和 `review_plan` 的真实职责；
6. 能解释 `request_id` 是关联键，不等于权限或幂等键；
7. 能区分 Runtime 确定性处理和模型上下文注入；
8. 能区分 idle、completed、terminated 和 durable 的含义；
9. 能指出当前教学版没有真正的 plan execution gate。

### 当前仍需验收

- 能否不看代码写出 shutdown 协议伪代码；
- 能否解释错误 response 为什么不能只靠自然语言判断；
- 能否说明为什么 `request_plan` 不是完整协议入口；
- 能否描述普通消息和协议消息分别由谁消费；
- 能否指出一个当前实现的生产风险并说明原因。

补充：已经能够说明“没有 `request_id/pending` 的简单方案也可以跑通”，并能指出两条计划同时存在时会产生响应关联歧义；还需要继续用伪代码和失败场景独立复述完整协议。

## 8. 暂缓 Work Pool

- [W-2026-017：Python 锁与 Agent 并发状态治理](../specs/work-pool/W-2026-017-study-python-locks-and-agent-concurrency.md)
- [W-2026-019：持久 Teammate 生命周期、Idle Loop 与唤醒](../specs/work-pool/W-2026-019-study-persistent-teammate-lifecycle.md)
- [W-2026-020：Agent-to-Agent 协作方式与通信拓扑](../specs/work-pool/W-2026-020-study-agent-to-agent-collaboration-patterns.md)
- [W-2026-021：生产级 Agent 权限、授权与审批治理](../specs/work-pool/W-2026-021-study-production-agent-permissions-and-approval.md)

这些 Work Pool 仍是后续学习主题，不因本章笔记完成而自动启动。
