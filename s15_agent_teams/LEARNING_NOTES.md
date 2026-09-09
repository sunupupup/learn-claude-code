# s15 Agent Teams 学习笔记

## 本章核心结论

🔴 **已验证理解**：Agent Team 首先是一种 Harness / Agent Runtime 层的协作拓扑，不是模型本身的一种新类型。Lead、Teammate 和 Subagent 的差异，主要来自它们在团队中的角色、生命周期、上下文边界和通信方式。

本章教学代码在 s14 的单 Agent 基础上增加了三件事：

1. `MessageBus`：使用每个 Agent 独立的文件收件箱传递消息；
2. `spawn_teammate_thread`：在 daemon thread 中启动拥有独立 messages、system prompt 和工具集的 Teammate Loop；
3. Lead inbox 注入：把队友发来的消息在合适的时机加入 Lead 的上下文，让 Lead 能继续决策。

当前实现支持的是**进程内、线程生命周期内的临时驻留 Teammate**，不是跨进程、跨 Session 可恢复的 Durable Teammate。生产级实现还需要 Registry、可靠消息、生命周期协议、权限、Checkpoint、恢复和验收机制。

本章的完整学习目标可以概括为：

> 看懂一个 Lead 如何创建队友、队友如何运行自己的 Loop、双方如何通过 inbox 传递状态，以及为什么“线程仍然活着”不等于“Agent 已经持久化”。

## 本次确认：角色定位与委派层级

### 我的原始理解

> 不对，甚至可以理解为：Agent Team 只是每个 Agent 定位不同。其实每个非 Lead Agent，如果做得很广泛，都可以变成自己另外一个小 Team 的 Lead；只是一般情况下，非 Lead Agent 最多创建一次性的 Subagent 就差不多了，不用设计嵌套层级太深。

### 判断

🔴 **已验证理解**：Lead 和 Teammate 主要是协作角色和拓扑位置的差异，不是两种完全不同的 Agent 类型。一个 Teammate 在承担较大领域任务时，理论上可以成为局部子团队的协调者。

### 校准后的专业表述

> Agent Team 是一种多 Agent 协作拓扑。Lead 表示当前团队中的协调与汇总角色，Teammate 表示被分配工作的协作节点；同一个 Agent 在不同层级可以承担不同角色。持久子团队在架构上可行，但通常应限制嵌套深度和委派权限；非 Lead Agent 默认使用边界清晰的一次性 Subagent，只有在确实需要独立协调域时才建立持久子团队。

### 为什么需要 Teammate

> Teammate 的目的，是拆分职责，避免主 Agent 的上下文爆炸；有些任务主 Agent 只需要知道结果。

🔴 **已验证理解**：Teammate 通过独立上下文和并行执行，把不同领域的细节从 Lead 的主上下文中分离出去；Lead 仍然需要接收结果、判断证据并负责最终整合，不能把“收到摘要”直接当成“任务已正确完成”。

专业表述：

> Agent Team 的主要价值是上下文隔离、职责分工和并行协作，而不是单纯增加 Agent 数量。委派后，Lead 只保留完成决策所需的结果、证据和状态；具体实现细节留在 Teammate 的局部上下文中。

### 机制与分层

```text
Root Lead
  ├─ Backend Teammate / Backend Lead
  │    ├─ 一次性 DB Subagent
  │    └─ 一次性 Test Subagent
  └─ Frontend Teammate
```

- 这是 Harness / Agent Runtime 的协作拓扑，不是模型本身的能力分类；
- Lead 负责拆分、授权、汇总和验收；
- Teammate 默认负责一个边界明确的执行域；
- 一次性 Subagent 适合短任务和单次结果返回；
- 持久子团队需要额外的成员管理、消息路由、生命周期、权限、预算和故障传播机制。

### 当前教学实现的边界

- s15 教学版只让 Lead 使用 `spawn_teammate`；
- Teammate 的简化工具集中没有 `spawn_teammate`，因此当前代码没有实现持久嵌套 Team；
- “非 Lead 默认最多创建一次性 Subagent”是一个待研究的架构策略，不是当前 s15 代码已经实现的行为；
- README 中关于真实项目禁止队友继续创建队友的说明，后续仍需固定版本重新核验。

### 待后续学习

- 扁平 Team、层级 Team 和一次性 Subagent 的适用边界；
- 最大嵌套深度、扇出数量、预算和权限如何设计；
- 子团队结果如何向 Root Lead 汇总、验收和归责；
- 生产系统和开源项目为什么限制或允许嵌套委派。

## 进程内驻留与跨 Session 持久化

### 我的原始理解

> 跨主 loop 没有持久化，但是在 loop 里面它是一直存在的。比如一个主 loop 开始时创建 frontend 和 backend 两个 teammate，后面就可以不断 `send_message` 通知它们干活。

### 判断

🔴 **已验证理解**：当前 s15 的 Teammate 线程独立于某一次 Lead `agent_loop()`；只要线程仍在自己的有限循环中运行，Lead 就可以跨多个 Lead Turn 向它的 inbox 发送消息。

### 校准后的专业表述

> 当前教学版支持“进程内、线程生命周期内”的临时驻留：Teammate 通过 daemon thread 独立运行，最多执行 10 轮，并可跨越多个 Lead Turn 收发消息；但它没有跨进程、跨 Session 的 Durable 状态、checkpoint 或自动恢复机制。

```text
Lead Turn 1 → spawn frontend/backend → send_message
Teammate threads → 独立运行并读取各自 inbox
Lead Turn 2 → 继续向仍存活的 Teammate 发送消息
Teammate 退出 → 后续消息不会自动恢复一个新的 Teammate
```

因此，“Lead 的 agent_loop 返回”和“Teammate 线程结束”不是同一件事；而“线程仍存活”也不等于“跨 Session 持久化”。

## Agent-to-Agent 协作方式

本章先只讨论 Agent 之间的协作，不把普通 Background Task 或确定性 Workflow 当成 Agent 协作类别。后续重点比较：

| 协作方式 | 核心关系 | 主要通信方式 |
| --- | --- | --- |
| 一次性委派 | 父 Agent → 临时 Subagent | 返回一次结果 |
| 持久队友 | Lead ↔ Teammate | 定向 inbox、多轮消息 |
| Handoff | Agent A → Agent B 转移控制权 | 上下文/任务交接 |
| 层级子团队 | Root Lead → Domain Lead → Workers | 分层委派和结果汇总 |
| 任务板协作 | 多个 Agent 竞争或认领任务 | 共享任务板、claim、状态更新 |
| Peer-to-Peer | 同级 Agent 互相协商 | 点对点消息或共享总线 |
| Durable Agent 协作 | 跨进程或跨 Session 的逻辑 Agent | 持久事件、队列、checkpoint |

需要区分三个维度：

```text
协作方式 = 拓扑结构 × 生命周期 × 通信/状态边界
```

“跨 Session”主要描述持久化边界，不自动代表多个同级主 Agent；跨 Session 的 Agent 仍然可以是父子、Lead-Worker 或任务板协作关系。

## Durable Teammate 与 `teammate_list`

### 我的原始理解

> 一旦有 Durable Teammate Agent，那就必然有 `teammate_list` 这种额外 Tool 了吧？

### 判断

**部分正确**。

🔴 **已验证理解**：Durable Teammate 必须在 Runtime 层拥有成员身份、生命周期和状态注册能力，否则系统无法知道有哪些 Teammate、它们是否仍然存活、如何路由消息或恢复任务。

但不一定必须把它暴露成模型可调用的 `teammate_list` Tool。成员信息也可以由 Harness 自动注入 Context、由内部控制面 API 查询，或通过事件通知 Lead。只有当 Lead 需要动态发现和选择队友时，`list_teammates` 才适合作为 Tool 暴露。

当前 s15 的 `active_teammates` 只是进程内的名称登记表，不是 Durable Registry；当前工具集中也没有 `teammate_list`。

### 专业表述

> Durable Teammate 必然需要 Runtime-level Team Registry；是否需要模型可见的 `list_teammates` Tool，取决于 Agent 是否需要自主发现、选择和管理队友。

### 待验收

- Registry 保存哪些字段：Agent ID、角色、状态、能力、权限、心跳、checkpoint 还是当前任务？
- 成员列表由模型主动查询，还是由 Runtime 根据消息和状态自动注入？
- Teammate 退出、崩溃、重启和同名重建时，Registry 如何更新？
- `list_teammates`、`send_message`、`spawn_teammate` 和 `shutdown_teammate` 的权限边界如何设计？

## s15 的完整机制地图

### 组件与职责

| 组件 | 当前代码 | 作用 | 当前边界 |
| --- | --- | --- | --- |
| Lead 外层输入循环 | `__main__` 的 `while True` | 接收用户 Query，调用一次 Lead `agent_loop`，随后消费 Lead inbox | 不会因为队友来信自动再次调用 `agent_loop`；下一次用户 Query 才会继续处理注入的消息 |
| Lead Agent Loop | `agent_loop(messages, context)` | 调用模型、处理 Tool、追加 Tool Result，直到模型不再请求 Tool 或发生错误 | 只覆盖当前一次用户 Turn；没有完整的持久 Run/Checkpoint 恢复 |
| Team Tool 分发 | `execute_tool()` | 把模型产生的 `tool_use` 路由到 `run_spawn_teammate`、`run_send_message`、`run_check_inbox` 等处理器 | Tool Schema 暴露能力，但真正权限仍由 Runtime 处理器决定；当前校验很简化 |
| MessageBus | `MessageBus.send/read_inbox` | 以 `{to_agent}.jsonl` 作为收件箱，追加和消费 JSON 消息 | 没有文件锁、ack、重试、消息 ID 或原子 claim；`read + unlink` 存在竞态 |
| Teammate 状态表 | `active_teammates` | 防止当前进程内重复创建同名活跃队友 | 只有名称到布尔值的登记，不是 Registry；没有线程句柄、心跳、状态、权限或 checkpoint |
| Teammate Loop | `spawn_teammate_thread()` 内部 `run()` | 在 daemon thread 中运行独立的模型循环，并读取自己的 inbox | 最多 10 轮；异常和非 Tool 停止都会结束线程；没有 idle、shutdown 或自动恢复 |
| Background Task | `start_background_task()` / `collect_background_results()` | 异步执行慢 Tool，并在 Lead 后续循环中注入结果 | 使用内存字典和 `background_lock`，不是 MessageBus，也不是 Agent-to-Agent 协作 |
| Cron Scheduler | `cron_scheduler_loop()` / `consume_cron_queue()` | 独立线程产生定时任务，Lead Loop 消费队列 | durable 只持久化任务定义；当前进程停止期间不会执行，也不会自动唤醒 Lead |
| Context Builder | `update_context()` / `get_system_prompt()` | 从 `.memory/MEMORY.md` 读取记忆并组装 System Prompt | 当前没有把 Teammate Registry 或队友列表动态注入 Prompt；详见[运行时上下文注入](./运行时上下文注入.md) |

### Lead 和 Teammate 的工具边界

Lead 使用完整的 `TOOLS`，包括任务、Cron 和三个团队工具：

- `spawn_teammate`：只在 Lead 工具集中出现，用于创建队友；
- `send_message`：Lead 通过它向指定 Agent 的 inbox 写消息；
- `check_inbox`：Lead 在当前模型 Turn 内主动消费 `lead.jsonl`。

Teammate 使用局部的 `sub_tools`：

- `bash`、`read_file`、`write_file`：完成局部执行工作；
- `send_message`：把进度或结果发给其他 Agent；
- 没有 `spawn_teammate`，所以当前教学代码没有实现持久嵌套 Team。

这里要区分**工具可见性**和**实际授权**：模型看到某个 Tool Schema，只代表它可以提出调用；`execute_tool()`、目标校验、凭证和外部系统仍应在 Runtime 层完成。当前代码对 `send_message` 的目标和权限校验非常少，属于教学简化。

## 关键调用链与真实代码映射

### 1. 用户 Query 到 Lead Loop

```text
__main__.input()
  → history.append(user query)
  → agent_loop(history, context)
  → get_system_prompt(context)
  → client.messages.create(..., tools=TOOLS)
  → 模型返回 text 或 tool_use
```

对应代码：

- `__main__` 的外层 `while True` 接收 Query；
- `agent_loop()` 在每轮模型调用前读取 Cron 队列；
- `client.messages.create()` 使用 Lead 的 `TOOLS`；
- `response.stop_reason != "tool_use"` 时结束本次 Lead Loop；
- 如果是 `tool_use`，逐个执行并把 `tool_result` 追加为下一条 user message，继续同一个 Lead Loop。

因此，Lead 的 `agent_loop` 是一个**当前 Turn 内的工具循环**，不是永远驻留的全局 Team Loop。

### 2. Lead 创建 Teammate

```text
模型选择 spawn_teammate
  → execute_tool(block)
  → run_spawn_teammate(name, role, prompt)
  → spawn_teammate_thread(...)
  → active_teammates[name] = True
  → threading.Thread(target=run, daemon=True).start()
```

`spawn_teammate_thread()` 随后为队友创建：

- 独立的 `system` 字符串；
- 独立的 `messages = [{"role": "user", "content": prompt}]`；
- 独立的 `sub_tools` 和 `sub_handlers`；
- 独立的 daemon thread。

所以 Teammate 不是 Lead Loop 中普通的同步函数调用，而是另一个拥有自己模型调用链的 Agent Loop。

### 3. Teammate 收消息并工作

```text
Teammate thread 启动
  → for _ in range(10)
  → BUS.read_inbox(name)
  → <inbox>...</inbox> 追加到 teammate messages
  → client.messages.create(..., system=teammate system)
  → 执行 bash/read/write/send_message
  → 追加 tool_result
  → 下一轮继续，或停止
```

几个容易忽略的点：

- 队友只在每轮模型调用前读取自己的 inbox；模型调用正在进行时不会被消息强行打断；
- `messages[-20:]` 只把最近 20 条消息交给队友模型，属于教学版的简单上下文裁剪；
- 异常直接 `break`，没有把失败原因结构化汇报给 Lead；
- 非 `tool_use` 的响应也会结束队友循环；
- 固定 `10` 轮是有限循环，不是 idle loop。

### 4. Lead 向 Teammate 发消息

```text
Lead 模型选择 send_message
  → run_send_message(to, content)
  → BUS.send("lead", to, content)
  → .mailboxes/<to>.jsonl 追加一行 JSON
  → Teammate 下一轮 BUS.read_inbox(name) 时消费
```

当前 `BUS.send()` 的消息包含 `from`、`to`、`content`、`type` 和时间戳，但没有唯一消息 ID、版本号、ack 或幂等键。

### 5. Teammate 把结果发回 Lead

```text
Teammate for-loop 结束
  → 从最近的 assistant 内容提取 summary
  → BUS.send(name, "lead", summary, "result")
  → active_teammates.pop(name, None)
  → 线程结束
```

Lead 有两种消费结果的路径：

1. 当前 Lead Loop 内模型主动调用 `check_inbox`，执行 `run_check_inbox()`；
2. 当前 Lead Loop 返回后，`__main__` 直接 `BUS.read_inbox("lead")`，把内容追加为 `[Inbox]`，等待下一次用户 Query 时进入 Lead 上下文。

两条路径都具有消费语义。若一条路径先读走消息，另一条路径就看不到同一批消息；生产实现需要明确唯一消费者或使用可确认的消息状态。

### 6. 后续用户 Query 如何继续协作

```text
Lead Turn 1：创建 frontend/backend Teammate
  → Teammate threads 独立运行
  → Lead Turn 1 结束，外层循环等待用户输入
  → 队友把结果写入 lead.jsonl
用户发送 Query 2
  → history 已包含上一轮追加的 [Inbox]
  → agent_loop(history, context)
  → Lead 模型看到队友结果并继续决策
```

当前版本不会因为 `lead.jsonl` 出现新消息而自动再次调用 `agent_loop()`；这正是“进程内可通信”与“事件驱动、可自动唤醒的生产 Runtime”之间的差异。

## 状态变化与生命周期模型

### Lead 的状态路径

```text
等待用户输入
  → 进入当前 Lead agent_loop
  → 模型调用 / Tool 调用循环
  → 返回文本、异常或完成当前 Turn
  → 外层读取 Lead inbox 并注入 history
  → 再次等待用户输入
```

注意：外层循环继续存在，不代表当前 `agent_loop` 会自动继续；两层 Loop 的生命周期不同。

### Teammate 的状态路径

```text
未创建
  → active_teammates 登记
  → daemon thread 启动
  → 最多 10 次模型/工具循环
  → 发送 result 给 Lead
  → 从 active_teammates 移除
  → 线程结束
```

它可以在一个 Lead Turn 返回之后仍然存活，因此能跨多个 Lead Turn 收发消息；但它不能跨进程存活。由于线程是 daemon thread，主进程退出时不会等待它完成，也没有从磁盘恢复其 messages、当前轮次或未完成副作用的机制。

### 消息的状态路径

```text
send：内存中的消息对象
  → append 到目标 .jsonl
  → read_inbox 读取整个文件
  → unlink 删除整个文件
  → 返回调用方上下文
```

这不是可靠消息队列：

- 写入没有文件锁；
- 读取和删除不是原子操作；
- 进程崩溃可能导致消息丢失或重复消费；
- 没有 pending / delivered / acknowledged 状态；
- 没有重试、过期、顺序和幂等语义。

这些是后续 Python 锁、消息交付和持久生命周期学习的边界，不应被当前 Demo 的“能看到消息”误认为生产可靠性。

## 状态访问：Tool Pull 与 Runtime Context Injection

本章进一步确认了一个通用的 Context Engineering（上下文工程）知识点：Runtime 获取外部状态后，可以让 Agent 主动 Pull，也可以提前 Push 一份快照。

- `list/get/search` Tool：Agent 按需查询，适合大量、变化快或需要精确详情的数据；
- Runtime Context Injection：Runtime 在模型调用前注入少量、常用状态，例如当前任务或队友摘要；
- 混合模式：注入摘要，细节通过 Tool 获取，生产系统更常见。

当前 s15 的 `update_context()` 只读取 `.memory/MEMORY.md` 并组装 System Prompt，没有注入 Teammate Registry；`check_inbox` 是 Tool Pull，不是动态 System Prompt 注入。

完整说明见：[运行时上下文注入.md](./运行时上下文注入.md)。

关键边界：

1. Prompt 中的状态只是 Registry 的视图或快照，不是事实来源本身；
2. 注入队友信息不会自动创建 `send_message` 或 `shutdown_teammate` 能力；
3. 写操作前仍需要 Runtime 做目标、权限和状态的重新校验；
4. 当前 `active_teammates` 不能替代 Durable Team Registry。

## 与 s13 / s14 继承机制的关系

s15 是在前面章节能力上叠加 Team 机制，不是一个只包含 MessageBus 的独立程序。

### Background Task 与 Teammate 的区别

两者都体现了“异步生产，稍后把结果交回 Agent 上下文”，但协议不同：

| 维度 | Background Task | Teammate |
| --- | --- | --- |
| 执行对象 | 一个后台 Tool 调用 | 一个拥有独立 Loop 的 Agent |
| 结果存放 | `background_results` 内存字典 | 目标 Agent 的 `.jsonl` inbox |
| 通信关系 | Tool → Lead | Agent ↔ Agent |
| 上下文 | 不拥有独立 Agent messages | 有独立 system、messages 和工具集 |
| 当前完成机制 | `task_notification` | Teammate 发 `result` 消息 |
| 是否支持持续协作 | 否，通常一次 Tool 执行 | 教学版可在 10 轮内多次收消息 |

因此，不能因为 Background Task 也在后台线程运行，就把它称为 Teammate。

### Cron Scheduler 与 Teammate 的区别

- Cron Scheduler 的 daemon thread 根据时间把 `CronJob` 放入 `cron_queue`；
- `agent_loop()` 调用 `consume_cron_queue()` 时才把定时 Prompt 注入 Lead messages；
- `durable=True` 只保存任务定义到 `.scheduled_tasks.json`，不代表进程停止期间仍会执行；
- 这与 Teammate 的 inbox 消息机制相似之处是“异步事件稍后进入上下文”，但触发源、状态模型和协作语义不同。

### 共享状态与锁的边界

s15 当前使用了 `background_lock` 和 `cron_lock` 保护部分内存字典/队列，但 `MessageBus` 和 `active_teammates` 没有对应的显式锁。尤其是：

- `active_teammates` 的检查与写入不是一个受保护的原子创建操作；
- `MessageBus.read_inbox()` 的 read + unlink 不是原子消费；
- 多个 Agent 对共享工作区文件的写入也没有文件级协调。

Python 锁与 Agent 并发状态治理暂放在 [W-2026-017](../specs/work-pool/W-2026-017-study-python-locks-and-agent-concurrency.md)。

## 教学实现、通用原理与版本相关事实

### 当前教学代码中已经能直接核验的事实

- `BUS = MessageBus()` 是当前进程共享的一个总线辅助对象；
- 每个 Agent 通过自己的 `<agent_id>.jsonl` 收件箱收消息；
- Teammate 使用 daemon thread、独立 messages、独立 system 和简化工具集；
- Teammate 最多运行 10 轮，结束后发送 `result` 并从 `active_teammates` 移除；
- Lead 可通过 `check_inbox` 或外层循环消费 `lead.jsonl`；
- 新用户 Query 不会自动重启已结束的 Teammate，也不会让 Lead 自动被 inbox 唤醒。

### 从当前实现推导出的通用原理

- 多 Agent 的价值来自职责拆分、上下文隔离和并行执行，而不是 Agent 数量本身；
- Agent 之间的通信必须和生命周期、状态来源、权限及最终验收一起设计；
- in-process residence（进程内驻留）和 cross-session durability（跨 Session 持久化）是不同维度；
- 动态上下文是状态的视图，不应替代权威 Registry 或执行时校验；
- 异步线程能完成 Demo，不等于消息可靠、状态可恢复或副作用可安全重试。

### README 中真实项目部分的证据范围

README 的“深入 CC 源码”部分提到了 `proper-lockfile`、结构化消息、权限冒泡、idle loop、Team Config 和禁止队友继续创建队友等内容。这些是教程 README 对特定版本/源码分析的记录，不是当前 `s15_agent_teams/code.py` 的行为，也不应未经重新核验就当作所有生产 Agent 平台的通用事实。

当前章节已使用这些内容帮助建立待验证问题，但没有把它们标记为本地代码已实现。后续若要确认真实项目行为，应固定仓库版本/Commit，再对照源码和官方资料核验。

## 案例：权限控制消息不是 Tool

### 我的原始疑问

> `permission_request` 到底是什么？是一个 Tool 吗？
>
> 用户批准后，Teammate 怎么收到 `permission_response`？

### 判断与校准

🔴 **已验证理解**：在 s15 README 描述的语境中，`permission_request` 不是普通的模型可调用 Tool，而是权限 Runtime 生成的结构化控制消息；`permission_response` 也是控制面返回给 Teammate 的结构化响应。

需要区分三类东西：

| 类型 | 方向 | 含义 |
| --- | --- | --- |
| Tool Call | Agent → Runtime | Agent 想调用 `bash`、写文件或其他 Tool |
| `permission_request` | Teammate Runtime → Lead / 控制面 | 当前 Tool 调用需要审批 |
| `permission_response` | Lead / 控制面 → Teammate Runtime | 审批结果和授权范围 |

某些框架可以把权限请求包装成内部 Tool，但那只是实现形式；它的核心语义仍然是**控制面事件**，不是普通业务 Tool。

### 完整调用链

```text
Teammate 准备调用敏感 Tool
  → Runtime 权限层拦截
  → 生成 permission_request
  → 写入 Lead 的 inbox
  → Lead poller 读取并路由到审批队列 / 用户界面
  → 用户批准或拒绝
  → 生成 permission_response
  → 写入 Teammate 自己的 inbox
  → Teammate poller 读取并匹配 request_id
  → 恢复原始 Tool，或返回 Permission Denied
```

这里的“权限冒泡”表示：子 Agent 的权限请求沿着协作拓扑传给拥有用户交互能力的上层；它不表示 Lead 自动继承了所有权限，也不表示 Agent 可以自行授予权限。

### Teammate 如何恢复原来的 Tool

生产实现需要维护挂起请求，例如：

```text
pending_permissions[request_id] = {
    tool: "bash",
    args: {"command": "git push origin main"},
    status: "waiting"
}
```

收到响应后，根据 `request_id` 恢复对应状态：

- `approved`：在授权范围内继续执行原始 Tool；
- `rejected`：返回权限拒绝，让 Agent 选择其他方案；
- `expired` / `revoked`：不能继续执行。

因此，`permission_response` 不能只是普通文本，而应包含请求 ID、决策、授权范围和必要的过期信息。

### 与 `AskUserQuestion` 的边界

- `AskUserQuestion`：询问用户偏好或补充信息，例如“使用 PostgreSQL 还是 SQLite？”；
- `permission_request`：请求授权执行具体副作用，例如“是否允许执行 `git push origin main`？”

前者是业务沟通，后者是安全控制；二者都可能在用户界面中显示，但不会因此变成同一种消息。

### 当前教学代码的边界

当前 s15 只有普通 `send_message`，没有真正的权限控制链：

- 没有 `permission_request` / `permission_response` 处理器；
- 没有 pending permission 状态表；
- 没有权限 poller；
- 没有恢复原始 Tool 调用的逻辑；
- `run_bash()` 直接执行 Shell。

所以，给当前 Teammate 发送一条“permission approved”文本，只会得到一条普通消息，不会自动解除某个 Bash 调用的阻塞。

本案例对应的生产级延伸主题已登记在 [W-2026-021：生产级 Agent 权限、授权与审批治理](../specs/work-pool/W-2026-021-study-production-agent-permissions-and-approval.md)。

## 本章掌握状态

### 已达到的学习目标

在 s15 教学实现范围内，已经能够：

1. 解释为什么 Teammate 通过独立上下文、独立 Loop 和并行执行缓解 Lead 上下文压力；
2. 区分一次性 Subagent、进程内多轮 Teammate 和跨 Session Durable Agent；
3. 描述 `spawn_teammate → daemon thread → own inbox → own Agent Loop → result to lead` 的完整调用链；
4. 解释 Lead inbox 如何被 `check_inbox` 或外层循环消费并注入 history；
5. 识别固定 10 轮、daemon thread、文件 read + unlink、内存状态表等教学简化；
6. 解释为什么 Durable Teammate 需要 Runtime-level Team Registry，但不一定需要模型可调用的 `list_teammates` Tool；
7. 区分 Agent-to-Agent 协作和普通 Background Task / Cron Scheduler。

### 尚未在本章内完成、明确暂缓的内容

- 体面的 `shutdown_request → shutdown_approved` 关机协议和消息类型：进入 s16；
- idle loop、唤醒、ack、重试、崩溃恢复和 Checkpoint：进入 [W-2026-019](../specs/work-pool/W-2026-019-study-persistent-teammate-lifecycle.md)；
- Python 锁、文件锁、原子消费和共享状态治理：进入 [W-2026-017](../specs/work-pool/W-2026-017-study-python-locks-and-agent-concurrency.md)；
- 扁平 Team、层级 Team、嵌套委派与权限/预算边界：进入 [W-2026-018](../specs/work-pool/W-2026-018-study-agent-team-hierarchy-and-delegation.md)；
- Agent-to-Agent 协作模式、Handoff、任务板、Peer 和 Durable Team 的生产比较：进入 [W-2026-020](../specs/work-pool/W-2026-020-study-agent-to-agent-collaboration-patterns.md)；
- 真实 CC 源码的当前版本核验：不在本章中把 README 的版本性描述当作最终证据。

### 完成判定

> **s15 学习目标已达到：教学版 Agent Team 的通信、Loop 和进程内生命周期已经掌握。**
>
> **生产级 Team Runtime 尚未完成，这是有意保留的学习边界，不属于本章遗漏。**

本章不应继续向前扩展成完整的分布式 Agent 平台；下一步应按需要从 s16 或 Work Pool 中选择一个边界继续深入。
