# s17 Autonomous Agents 学习笔记

> 学习状态：核心机制已建立，主流程和关键边界已完成校准；运行实验、并发竞态和生产级持久化仍未验收。
>
> 事实范围：当前教学代码、s16/s17 README 和本轮代码审阅属于已核对范围；README 中关于真实 Claude Code 的源码映射是版本相关资料，本轮没有重新固定版本并核验真实源码。

## 1. 本章核心结论

### 1.1 s17 不是重新实现 Task System，而是改变任务的消费方式

我的原始理解是：

> 这章的目的就是 task system + 多 agent 协作。s12 里主要是主 Agent 按部就班地捞取任务，s17 变成 Teammate 自己从 tasks 列表捞取能够执行的任务。

判断：🟡 **部分正确，核心方向正确但需要区分实现层次。**

专业准确表述：

> s12 已经提供 Task System（任务系统）：任务持久化、依赖检查、认领和完成状态；s17 复用这套系统，并把“发现和认领任务”的动作放入 Teammate 的 IDLE 生命周期，使多个 Teammate 可以自主消费共享任务板。

Task Board（任务看板）在这里是共享状态，不是 FIFO 队列：任务不会被取走，而是通过 JSON 文件中的 `owner` 和 `status` 发生状态变化。

```text
Lead.create_task()
  → .tasks/task_id.json: pending, owner=null

Teammate WORK 结束
  → IDLE / idle_poll()
  → scan_unclaimed_tasks()
  → claim_task()
  → owner=name, status=in_progress
  → 下一次 WORK 的 Teammate LLM 决定如何执行
```

### 1.2 s17 的“主动性”主要发生在 Runtime 层

这里的 Autonomous Agent（自治 Agent）不是指模型可以无限自由行动，而是指 Harness/Runtime 在 Teammate 空闲时主动执行任务发现和认领逻辑。

```text
Runtime：发现任务、检查依赖、尝试认领
LLM：理解任务、选择 bash/read/write/complete 等工具
Task System：保存 owner/status/blockedBy
```

Lead 仍然负责：

- 创建任务；
- 启动 Teammate；
- 必要时发送直接消息或 shutdown 请求；
- 查询任务状态并协调整体进度。

Teammate 当前暴露的是 `list_tasks`、`claim_task`、`complete_task`，没有 `create_task`。因此它是自主领取工作，不是自主产生整个任务图。

### 1.3 Lead 感知任务完成有两条路径

我的原始疑问是：

> 主要是 Teammate 捞取 task 执行，最后 Lead 怎么感知？

当前实现有两种不同的感知来源：

#### 状态路径：共享任务板

```text
Teammate LLM 调用 complete_task(task_id)
  → load_task()
  → status: in_progress → completed
  → save_task()
  → .tasks/task_id.json
```

Lead 之后调用 `list_tasks()` 或 `get_task()`，可以看到任务文件中的 `completed`。

#### 结果路径：Teammate 汇报消息

```text
Teammate 进入 shutdown/timeout
  → 生成最后一条 assistant 文本作为 summary
  → BUS.send(name, "lead", summary, "result")
  → .mailboxes/lead.jsonl
  → Lead.check_inbox() 或 consume_lead_inbox()
  → 注入 Lead history
```

重要边界：`complete_task()` 本身不会发送 `task_completed` 消息。Teammate 完成一个任务后，可能马上进入 IDLE 并认领下一个任务；Lead 不一定立刻收到逐任务汇报。

因此更准确的说法是：

> Lead 通过共享任务板感知结构化状态，通过 Teammate 的 `result` 消息感知汇报摘要；两条路径的时机和可信度不同。

### 1.4 Lead 的一次 Loop 结束不会自动关闭 Teammate

Lead 的顶层流程是：

```text
main 读取用户输入
  → Lead agent_loop()
  → LLM 调用 create_task / spawn_teammate 等工具
  → Lead 返回非 tool_use
  → 本次 Lead turn 结束
```

`agent_loop()` 返回并不等于 Teammate 被 shutdown。`spawn_teammate_thread()` 已经启动了独立的 daemon thread；Teammate 会继续自己的 WORK → IDLE 循环。

在 Teammate 仍然存活时，Lead 后续可以在新的用户 turn 中继续创建任务，Teammate 会在自己的轮询中发现它。Lead 不需要等到第二次 loop 才能让任务存在；任务文件一写入，Teammate 下一次轮询就可能看到它。

当前实现中，Teammate 只有在以下情况结束：

- Lead 明确发送 `shutdown_request`；
- `idle_poll()` 在 60 秒窗口内没有收到消息，也没有成功认领任务，返回 `timeout`；
- 工作阶段或模型调用异常会先跳出当前 WORK 阶段，之后仍按外层生命周期进入 IDLE；如果随后 timeout 或收到 shutdown，才会离开生命周期。

### 1.5 `timeout` 是有限等待窗口结束，不是永久 idle

```text
IDLE_POLL_INTERVAL = 5 秒
IDLE_TIMEOUT = 60 秒
```

`idle_poll()` 最多执行 12 次轮询。每次优先检查 inbox，然后扫描任务板；如果整个窗口内没有收到可处理消息，也没有成功认领任务，就返回 `timeout`。

随后 Teammate 外层循环执行：

```python
if idle_result == "timeout":
    break
```

然后发送 summary，清理 `active_teammates`，线程结束。所以：

```text
任务在 60 秒内出现
  → 当前 Teammate 可能发现并认领

任务在 Teammate timeout 之后出现
  → 当前 Teammate 已退出
  → 需要新的 Teammate 或其他仍存活的 Worker
```

`timeout` 通常表示“本次等待窗口没有可继续工作的事情”，但不是严格证明任务板为空。也可能是任务仍被依赖阻塞、认领失败或消息没有成功到达。

## 2. 核心术语与层次

| 术语 | 中文理解 | 所在层次 | 与相邻概念的边界 |
|---|---|---|---|
| Task System | 保存任务、依赖、owner 和状态的任务系统 | Harness/Runtime 状态层 | 不等于后台执行机制 |
| Task Board / Blackboard | Agent 共享查看和更新的任务状态面 | 协调/共享状态层 | 不等于 FIFO 消息队列 |
| Task | 一个可认领、执行和完成的工作项 | 业务任务状态层 | 不等于 s13 的 Background Task |
| Background Task | 某次 Tool Call 的后台执行实例 | Tool 执行/异步层 | 由 `run_in_background` 和 `bg_id` 追踪，不负责 owner/blockedBy |
| `blockedBy` | 当前任务依赖的上游任务 ID | Task System | 不是自然语言依赖；依赖通过 ID 关联 JSON 文件 |
| `can_start` | 检查依赖是否存在且全部 completed | Runtime 防护 | 只判断能否开始，不证明任务完成 |
| `claim_task` | 把 pending 任务变为 in_progress 并写入 owner | Runtime 状态迁移 | claim 是动作，`in_progress` 是状态 |
| `idle_poll` | Teammate 空闲时等待消息并扫描任务 | Teammate Runtime | 不是永久调度器，也不是模型自主意识 |
| WORK | Teammate 调用 LLM 和工具执行工作的阶段 | Agent Loop | 最多 10 轮 LLM/tool 交互 |
| IDLE | Teammate 仍存活，等待 inbox 或可认领任务 | 生命周期/调度层 | 不等于 completed 或 durable |
| SHUTDOWN | Teammate 退出前发送 summary 并结束线程 | 生命周期层 | 当前 timeout 也会进入这条退出路径 |
| Lead | 创建任务、启动成员、观察和协调团队的 Agent 角色 | 协调层 | 一次 Lead turn 结束不等于团队结束 |
| Teammate | 拥有独立上下文、工具和生命周期的工作 Agent | Agent Runtime | 当前是进程内 daemon thread |
| `result` / summary | Teammate 发给 Lead 的结果汇报 | MessageBus/上下文层 | 不等于任务 JSON 的权威状态，也不等于验证证据 |
| Harness / Runtime | 包围模型、工具、状态和生命周期的执行框架 | 系统控制层 | 模型可以提出意图，但状态门控由 Runtime 执行 |

## 3. 我的原始理解与校准

### 3.1 `can_start` 主要检查依赖

我的原始理解：

> 这边主要是检查 task 的依赖项是否都完成了。

判断：🟡 **部分正确。**

`can_start()` 对 `blockedBy` 中每个依赖做两项检查：

1. 依赖文件是否存在；
2. 依赖任务的 `status` 是否为 `completed`。

所以准确表述是：

> `can_start` 判断任务是否具备开始条件；依赖缺失和依赖未完成都会返回 `False`。

### 3.2 `claim_task` 的 owner/status 判断属于 Harness 防护

我的原始理解：

> 认领任务有两个判断：不能处于非 pending，不能已经有 owner，这是 Harness 层防护。

判断：🔴 **已验证理解，但不完整。**

前两道检查确实是：

```text
status == pending
owner 为空
```

之后还会调用 `can_start()` 检查依赖。因此当前教学实现的认领门槛是：

```text
pending + 无 owner + 依赖可启动
```

这些检查位于 Runtime/Task System，而不是依赖 LLM 自己遵守提示。

### 3.3 `deps` 和 `missing` 是两类不同阻塞原因

我的原始疑问：

> 依赖项没了，岂不是出问题了？

判断：🔴 **已验证理解。**

当前代码把阻塞原因分成两类：

```text
deps    = 文件存在，但状态不是 completed
missing = blockedBy 引用的文件不存在
```

`missing` 通常说明任务数据不完整、依赖 ID 填错或依赖文件被删除。当前实现不会自动创建或修复依赖，而是返回错误信息并拒绝认领，属于 fail-closed（失败即不放行）。

### 3.4 Teammate 在 IDLE 中主动认领，下一轮仍由 LLM 执行

我的原始理解：

> 主动在一次 loop 结束之后捞一个任务，下次 loop 的时候直接执行；之前的 Teammate 是 Lead 发 inbox 后被动处理。

判断：🟡 **部分正确。**

正确部分：

- s16 主要依赖 Lead 通过 inbox 发送新任务；
- s17 在 IDLE 阶段加入任务板扫描和自动认领；
- 认领成功后返回 `work`，进入下一次 WORK 阶段。

需要修正“直接执行”：

```text
idle_poll() 自动 claim
  → messages.append(<auto-claimed>...)
  → 下一轮 Teammate LLM 看到消息
  → LLM 决定调用 bash/read/write/complete
```

Runtime 自动的是发现和认领，不是代替 LLM 完成实际代码工作。

### 3.5 “其他逻辑都一样”不准确

我的原始理解：

> 除了主动捞任务，其他逻辑似乎看起来都一样。

判断：🟡 **部分正确。**

基础的 LLM ↔ Tool 交互结构相似，但 s17 还新增或调整了：

- `scan_unclaimed_tasks()`；
- `idle_poll()`；
- Teammate 的 `list_tasks`、`claim_task`、`complete_task`；
- WORK → IDLE → SHUTDOWN 外层生命周期；
- IDLE 阶段对 shutdown 的优先处理；
- 自动认领消息注入；
- Lead 侧统一消费 inbox 的结果路径。

### 3.6 Teammate 任务工具不只是“认领和完成”

我的原始理解：

> 子 Agent 认领任务、完成任务的几个工具。

判断：🟡 **基本正确。**

当前 Teammate 的三个任务工具是：

```text
list_tasks     查看任务板
claim_task     认领任务
complete_task  标记任务完成
```

Teammate 没有 `create_task`，所以任务生产仍主要由 Lead 完成。

### 3.7 WORK 的 10 轮与 s15/s16/s17 的区别

我的原始理解：

> 这里还是一个有限 loop，可以形成 claim_task → run_bash → complete_task；之前 10 次之后 Teammate 就休息了，现在会进入 idle_poll。

判断：🟡 **部分正确，需要修正章节对照。**

当前 s17 的确有：

```python
for _ in range(10):
    # 最多 10 轮 LLM ↔ Tool 交互
```

但历史差异应这样记：

```text
s15：工作轮次结束后退出
s16：完成一轮后进入 idle，主要等待 inbox
s17：WORK 阶段最多 10 轮，结束后进入 idle_poll，既等待 inbox 又扫描任务板
```

因此 s17 的变化不只是“休息方式改变”，而是把 IDLE 从被动等待扩展为任务发现和自动认领阶段。

## 4. 关键调用链

### 4.1 Lead 创建任务，Teammate 自动领取

```text
Lead LLM
  → create_task(subject, description, blockedBy)
  → save_task()
  → .tasks/task_id.json
       status=pending, owner=null

Teammate WORK 阶段结束
  → idle_poll()
  → BUS.read_inbox(name)       # inbox 优先
  → scan_unclaimed_tasks()
  → 选择排序后的第一个候选
  → claim_task(task_id, owner=name)
  → status=in_progress, owner=name
  → messages.append(<auto-claimed>)
  → return "work"

下一次 WORK
  → Teammate LLM 看到 auto-claimed 消息
  → 调用 bash/read_file/write_file
  → 调用 complete_task(task_id)
```

### 4.2 完成状态与 Lead 汇报

```text
complete_task(task_id)
  → 仅检查 status == in_progress
  → 写 status=completed
  → 返回 Tool Result 给 Teammate
  → 不直接 BUS.send 给 Lead

Teammate 后续可能：
  → 继续 IDLE 并领取下一个任务
  → 收到 shutdown_request 后退出
  → 60 秒无新工作后 timeout 退出

退出路径
  → 取最后一条 assistant 文本作为 summary
  → BUS.send(name, "lead", summary, "result")
  → Lead inbox
```

Lead 感知方式：

```text
结构化任务状态：Lead.list_tasks() / get_task()
自然语言汇报：Lead.check_inbox() / consume_lead_inbox()
```

这两条路径不能混为一谈：任务文件表达状态，`result` 消息表达 Teammate 的汇报。

### 4.3 Lead Loop 与 Teammate 生命周期并行

```text
main
  → 读取用户输入
  → Lead.agent_loop()
       → create_task()
       → spawn_teammate_thread()
       → 本次 Lead turn 结束

spawn_teammate_thread()
  → threading.Thread(..., daemon=True).start()
  → Teammate 独立执行 WORK/IDLE

Lead turn 结束
  ≠ Teammate shutdown
```

Lead 后续创建任务与 Teammate 轮询是并发关系，而不是“Lead 第二次 loop 才把任务交给 Teammate”。只要 Teammate 尚未 timeout，任务文件出现后下一次轮询就可能触发认领。

### 4.4 IDLE、timeout 与后续任务时间线

```text
t0       Lead 创建任务，Teammate 进入 IDLE
t0~t0+5  Teammate 下一次轮询发现任务并尝试 claim

t20      Lead 在后续 turn 创建任务
t20~t25  仍存活的 Teammate 发现并认领

t60      60 秒内没有消息或成功 claim
         → timeout
         → summary
         → Teammate 线程结束

t>60     Lead 才创建任务
         → 当前 Teammate 不会再领取
         → 需要 spawn 新 Teammate 或依赖其他 Worker
```

## 5. 状态模型

### 5.1 Task 状态

```text
pending
  └─ claim_task + can_start
       → in_progress
            └─ complete_task
                 → completed
```

当前教学代码没有：

- `in_progress → pending` 的 release/recovery 路径；
- lease（租约）或 heartbeat（心跳）；
- 原子 claim；
- 任务完成验证；
- 依赖环检测。

### 5.2 Teammate 生命周期

```text
spawned
  → WORK
  → IDLE
      ├─ inbox message → WORK
      ├─ shutdown_request → SHUTDOWN
      ├─ 可认领任务 → WORK
      └─ 60 秒无进展 → timeout → SHUTDOWN
  → result summary
  → thread ended
```

`idle` 只表示仍然存活并等待工作；不表示任务已完成，也不表示状态可以跨进程恢复。

### 5.3 MessageBus 消费状态

```text
BUS.send()
  → .mailboxes/<agent>.jsonl
  → read_inbox()
  → 读取后删除文件
  → Runtime 路由或注入 history
```

当前是教学版文件消费语义，不是可靠消息队列：没有 ack、重试、消息 ID、原子消费或崩溃恢复。

## 6. 关键伪代码

### 6.1 Teammate 主循环

```python
while True:
    # WORK：最多 10 轮 LLM ↔ Tool 交互
    work_phase(max_rounds=10)

    # IDLE：等待消息或主动领取任务
    result = idle_poll(name, messages, name, role)

    if result == "work":
        continue
    if result in ("shutdown", "timeout"):
        break

# SHUTDOWN：汇报后退出
send_result_summary_to_lead()
```

### 6.2 IDLE 自动认领

```python
for each poll in 12 times:
    sleep(5)

    inbox = read_inbox(teammate)
    if inbox:
        if contains_shutdown_request(inbox):
            reply_shutdown()
            return "shutdown"
        inject_inbox(messages, inbox)
        return "work"

    candidates = scan_unclaimed_tasks()
    if candidates:
        result = claim_task(candidates[0].id, owner=teammate)
        if result indicates success:
            inject_auto_claimed(messages, candidates[0])
            return "work"

return "timeout"
```

这个伪代码体现了本章最重要的优先级：`inbox` 优先于任务板；shutdown 优先于普通消息和任务认领。

## 7. 当前代码映射

| 机制 | 当前实现位置 | 已核对行为 |
|---|---|---|
| Task 持久化 | `code.py:47-97` | `.tasks/*.json`，`Task` 含 status/owner/blockedBy |
| 依赖检查 | `code.py:100-109` | 缺失依赖或未完成依赖返回 False |
| 认领状态迁移 | `code.py:111-144` | pending + 无 owner + can_start 后写入 in_progress |
| 自动发现 | `code.py:346-359` | 只收集 pending、无 owner、可启动任务 |
| IDLE 轮询 | `code.py:362-418` | 每 5 秒检查 inbox，再扫描任务板，最多 60 秒 |
| Teammate 工具 | `code.py:474-578` | list/claim/complete，不包含 create_task |
| Teammate WORK/IDLE | `code.py:592-653` | WORK 最多 10 轮，之后进入 idle_poll |
| Teammate 汇报 | `code.py:654-667` | 退出时发送 `result` summary 给 Lead |
| Lead inbox | `code.py:785-817`、`1024-1051` | check_inbox 或主循环末尾消费并注入 history |
| Lead CLI 与 Loop | `code.py:1024-1051` | main 读取输入，调用 Lead agent_loop；不自动 shutdown Teammate |

## 8. 容易混淆的边界与失败场景

### 8.1 没有可认领任务不等于任务板为空

任务板可能还有：

- `in_progress` 任务；
- `pending` 但被未完成依赖阻塞的任务；
- `pending` 但依赖文件缺失的坏任务；
- 已被其他 Teammate 认领的任务。

因此 `scan_unclaimed_tasks()` 返回空，只能说明当前没有满足候选条件的任务。

### 8.2 scan 和 claim 之间存在竞态

教学代码先扫描再认领，且没有文件锁：

```text
Alice scan → 看到 Task A
Bob   scan → 也看到 Task A
Alice/Bob → 分别 load → check → save
```

显式 owner 检查可以拒绝一部分冲突，但不能把整个读-检查-写过程变成原子操作。真实生产需要文件锁、CAS、租约或单写者协调。

### 8.3 `completed` 不等于“真实完成”

当前 `complete_task()` 只检查任务是 `in_progress`，随后直接写 `completed`。它不验证：

- Bash 是否成功；
- 文件是否符合要求；
- 测试是否通过；
- 外部资源是否真正更新；
- 任务是否由正确 owner 完成。

因此任务状态、Teammate summary 和真实完成证据必须分开。完成验证属于 `W-2026-013`。

### 8.4 timeout 后任务可能无人领取

Teammate timeout 后不会重新等待。若 Lead 在这之后创建任务，必须重新启动 Worker，或者依赖其他尚未退出的 Teammate。这个问题连接到持久 Teammate、Registry、恢复和调度策略。

### 8.5 多 Agent 认领成功不代表文件写入安全

Alice 和 Bob 共享同一个 `WORKDIR`。即使任务认领没有重复，也可能同时修改同一个文件。任务分配隔离和工作区隔离是两个问题，后者引出 s18 Worktree Isolation。

### 8.6 教学版不等于生产版

当前实现省略或简化了：

- 文件锁与原子 claim；
- ack、重试、去重和可靠消息；
- lease/heartbeat 和崩溃恢复；
- 持久 Teammate Registry；
- 完成验证和证据链；
- 权限、审批和副作用治理；
- 跨进程/跨 Session Checkpoint。

README 中关于真实 CC 的 `idle_notification`、task watcher、文件锁和无固定 timeout 描述，只能作为版本相关的对照入口，不能直接当作当前本地教学代码事实。

## 9. 本章掌握状态

### 已达到或基本达到

1. 能区分 s12 的 Task System、s13 的 Background Task 和 s17 的自动消费机制；
2. 能说明 Lead 创建任务、Teammate 在 IDLE 中扫描并认领；
3. 能区分 Runtime 自动认领和 LLM 实际执行工具；
4. 能解释 `pending → in_progress → completed`；
5. 能说明 Lead 通过任务板状态和 `result` summary 感知 Teammate 工作；
6. 能解释 Lead 一次 loop 结束不会自动 shutdown Teammate；
7. 能区分 idle、timeout、shutdown 和线程结束；
8. 能指出缺失依赖、认领竞态、完成验证缺失和共享工作区冲突。

### 仍需验收

- 不看代码独立写出 `idle_poll` 的 inbox 优先伪代码；
- 用一个具体时间线说明 Lead 在 Teammate timeout 前后创建任务的不同结果；
- 通过确定性实验观察两个 Teammate 同时 claim 的结果；
- 观察任务完成后 Lead 是否立即收到逐任务通知；
- 区分“任务状态为 completed”和“任务已有完成证据”。

本章理论主线已经基本达到，但没有运行真实 Demo；因此“已理解”主要是代码和调用链层面的确认，不是运行时验收。

## 10. 暂缓 Work Pool

- [`W-2026-013：Task Completion Verification`](../specs/work-pool/W-2026-013-study-task-completion-verification.md)：完成状态与真实证据；
- [`W-2026-017：Python 锁与 Agent 并发状态治理`](../specs/work-pool/W-2026-017-study-python-locks-and-agent-concurrency.md)：scan/claim 竞态、文件锁和原子性；
- [`W-2026-018：Agent Team 层级设计与委派拓扑权衡`](../specs/work-pool/W-2026-018-study-agent-team-hierarchy-and-delegation.md)：层级 Team 与委派拓扑；
- [`W-2026-019：持久 Teammate 生命周期、Idle Loop 与唤醒`](../specs/work-pool/W-2026-019-study-persistent-teammate-lifecycle.md)：持久驻留、恢复和 timeout 策略；
- [`W-2026-020：Agent-to-Agent 协作方式与通信拓扑`](../specs/work-pool/W-2026-020-study-agent-to-agent-collaboration-patterns.md)：Task Board、Lead-Worker 和其他协作模式；
- [`W-2026-021：生产级 Agent 权限、授权与审批治理`](../specs/work-pool/W-2026-021-study-production-agent-permissions-and-approval.md)：多 Agent 权限和审批边界。

这些 Work Pool 仍然是后续学习主题，不因本章笔记完成而自动启动。
