# s14 Cron Scheduler 学习笔记

## 学习状态

- 当前状态：**核心静态机制已理解；运行实验和失败场景尚未验收。**
- 已确认范围：本章 `README.md`、当前教学代码、代码注释对照和本次讨论。
- 尚未执行：没有实际运行 `code.py` 验证定时触发、自动交付、持久化恢复或失败路径。
- 证据边界：README 折叠区中的真实 Claude Code（CC）源码映射本轮没有按当前版本重新核验，只能视为教程提供的版本相关说明。

## 章节衔接

s13 解决的是“慢 Tool 不阻塞主 Agent Loop”：Tool 可以在后台执行，完成结果通过通知在后续模型调用中交付。但任务仍由用户先发起。

s14 进一步解决“没有实时用户输入时，如何按时间产生 Agent 工作”：Scheduler 独立判断到期条件，Queue Processor 在 Agent 空闲时自动交付，Agent Loop 将定时 Prompt 作为模型输入继续执行。

## 我的核心直观理解

> Agent 这边的 CronJob，到期后其实就是多一个 user query message，给 LLM 多发一个 user message。

🔴 **已验证理解**：CronJob 到期后，其 `prompt` 会被 Harness 转换为一条带 `[Scheduled]` 标签的 `user` 消息，并加入下一次模型调用的上下文。

校准后的专业表述：

> CronJob 本身是调度数据。任务到期后，Scheduler 产生事件并写入队列；Agent Loop 消费事件，把 Job 的 Prompt 适配成 `user-role` 消息，再调用 LLM。传统 Cron 通常把到期事件映射到固定命令，而本章把到期事件映射到受 Tool 和权限约束的 Agent 决策。

重要边界：消息使用 `role: user` 不代表它来自此刻的真人输入；`[Scheduled]` 只是给模型看的来源标签，不承担身份、授权或优先级控制。

## 核心四层模型

```text
Scheduler
  每秒检查当前时间与 Cron 表达式
        ↓ 到期
Queue
  cron_queue 保存已触发、待交付的 CronJob
        ↓ Agent 空闲
Queue Processor
  非阻塞获取 agent_lock，并启动一轮 Agent Turn
        ↓
Consumer / Agent Loop
  消费队列 → 注入 [Scheduled] user message → 调用 LLM
```

### 1. Scheduler（调度器）

- 中文含义：按调度规则判断工作是否到期的确定性组件。
- 所在层次：Agent Runtime / Harness 的调度层。
- 当前实现：`cron_scheduler_loop()` 在 daemon 线程中每秒轮询。
- 边界：Scheduler 只执行“匹配、去重、入队”，不直接调用 LLM，也不执行 Job 描述的业务动作。

### 2. Queue（队列）

- 解决的问题：把“什么时候到期”和“什么时候能够运行 Agent”解耦。
- 当前实现：`cron_queue` 是由 `cron_lock` 保护的进程内 `list`。
- 边界：它不是具有持久化、确认、重投、优先级和背压能力的生产消息队列。

### 3. Queue Processor（队列处理器）

- 解决的问题：发现已到期工作，并在 Agent 空闲时启动一轮执行。
- 当前实现：`queue_processor_loop()` 每 0.2 秒检查队列，使用 `agent_lock.acquire(blocking=False)` 判断 Agent 是否空闲。
- 边界：这是非抢占式交付。Agent 忙时只等待，不取消正在运行的模型调用或 Tool。

### 4. Consumer / Agent Loop（消费者 / Agent 循环）

- 解决的问题：把运行时事件适配成模型可消费的上下文。
- 当前实现：消费全部 `cron_queue`，逐个追加 `{"role": "user", "content": "[Scheduled] ..."}`，随后调用模型。
- 边界：多个 Job 同时到期时可能在同一次模型调用前被批量注入，不保证每个 Job 独占一次 LLM Call。

## 关键调用链与状态变化

### 注册路径

```text
用户提出定时要求
  → LLM 生成 schedule_cron Tool Call
  → execute_tool() 路由到 run_schedule_cron()
  → schedule_job()
  → validate_cron()
  → scheduled_jobs[job.id] = job
  → durable=True 时重写 .scheduled_tasks.json
```

对话中的主要入口是模型调用 `schedule_cron`，但它不是唯一入口：代码可以直接调用 `schedule_job()`，进程启动时也会通过 `load_durable_jobs()` 恢复已有定义。

### 触发与交付路径

```text
cron_scheduler_loop()
  → cron_matches(job.cron, now)
  → 检查 _last_fired[job.id] != minute_marker
  → cron_queue.append(job)
  → queue_processor_loop() 等待 agent_lock
  → run_agent_turn_locked()
  → agent_loop()
  → consume_cron_queue()
  → messages.append([Scheduled] user message)
  → client.messages.create(...)
```

建议用以下状态理解，而不是只说“CronJob 已触发”：

```text
registered → due → enqueued → delivered → model_called
                                      → tool/action（可选）
                                      → result/verification（教学版未建模）
```

到期、入队、模型看到消息、模型采取动作和业务真正完成是不同事实。

## Cron 表达式与匹配

### 五字段表达式

```text
分钟  小时  月中日期  月份  星期
  0    9       *       *    1-5
```

当前教学实现支持 `*`、`*/N`、单值 `N`、范围 `N-M` 和列表 `N,M,...`。

### 字段级匹配

🔴 **已验证理解**：`_cron_field_matches(field, value)` 对分钟、小时、DOM、月份或 DOW 做原子化匹配。

它不知道当前字段属于哪一个时间位置；字段的合法范围由 `validate_cron()` 根据位置传入。

### 表达式拆分

🔴 **已验证理解**：`cron_expr.strip().split()` 将表达式拆成五个字段。

无参数 `split()` 按连续空白字符切割，会忽略首尾和重复空白，不是只识别一个普通空格。

### DOM / DOW 规则

DOM 是 Day of Month（月中日期），DOW 是 Day of Week（星期）。本实现要求分钟、小时和月份全部匹配；DOM 与 DOW 同时受到约束时采用 OR：两者匹配任意一个即可。

该结论只确认当前教学代码，不自动推广到所有 Cron 实现。

### 两层校验

🔴 **已验证理解**：`_validate_cron_field()` 校验单字段语法和值域，`validate_cron()` 校验五字段结构并按字段位置组合检查。

“通过校验”只表示当前解析器能够接受，不等于该表达式一定存在真实触发时间。例如日历日期组合是否存在并未被验证。

## Durable 的准确边界

> durable 指需要持久化，即重启后仍能恢复的任务。

🔴 **已验证理解**：`durable=True` 会把 CronJob 定义写入 `.scheduled_tasks.json`，启动时可以重新加载。

校准后的专业表述：

> Durable 在本教学实现中只表示“调度定义跨进程重启保留”，不表示执行过程耐久化，也不保证停机期间错过的触发会自动补跑。

因此：

- 进程停止时 daemon Scheduler 也停止；
- `.scheduled_tasks.json` 保留的是 Job 定义，不是执行状态或结果；
- 从 8:50 停机到 9:10 时，9:00 的触发不会因为定义仍在就自动补跑；
- 真正的 Durable Execution 还需要持久队列、Checkpoint、执行状态、重试与业务幂等。

## 取消任务的语义

🔴 **已验证理解**：`cancel_job()` 先从 `scheduled_jobs` 移除定义；如果 Job 是 durable，再把剩余 durable Jobs 整体重写到磁盘。

需要保留两个边界：

1. 它取消未来调度，不会撤回已经进入 `cron_queue` 的那次触发；
2. 删除内存状态时持有 `cron_lock`，但 `save_durable_jobs()` 在锁外读取完整字典，生产实现需要进一步处理并发一致性和原子写入。

## 消息注入与“插队”

### 我的原始理解

> Agent Loop 处理任务时，在某次 Tool Call / Tool Result 之后插入一个带标签的 user message，带入下一次 Loop；这是一种不中断 Loop 的消息插入。

确认正确的部分：

- 🔴 异步事件会在下一次模型调用前转成消息进入上下文；
- 🔴 当前 s14 不会修改正在进行的模型请求，也不会抢占正在执行的 Tool；
- 🔴 Tool 执行产生下一轮 `tool_result` 后，Cron 消息可能在下次 `while` 迭代开头被消费。

校准后的专业表述：

> 非抢占式消息注入是 Runtime 先缓存异步事件，等待当前模型调用或必要的 Tool 协议步骤结束，再在下一个安全模型调用边界把事件适配成消息并加入 Context。

不是所有注入都一定发生在 Tool Result 之后：如果上一轮 Agent Loop 已经结束，Queue Processor 会启动新的 Agent Turn，并在第一次模型调用前注入 Cron 消息。

标签与调度策略也必须分开：

- `[Scheduled]`、`<task_notification>`：给模型看的来源语义；
- Queue、Priority、Lock：Runtime 决定的交付顺序和时机；
- AuthN/AuthZ 与业务规则：决定消息允许驱动哪些真实动作。

“Message Injection（消息注入）”属于 Agent Harness、Runtime 与 Context Engineering 的交叉问题，不是 LLM 模型内部机制；也不同于安全领域的 Prompt Injection 攻击。

完整的生产级扩展已记录到 [`W-2026-015`](../specs/work-pool/W-2026-015-study-agent-message-injection-steering.md)，当前不在本章提前展开。

## 当前教学实现的关键简化

| 维度 | 当前实现 | 生产边界 / 待验证 |
| --- | --- | --- |
| 调度运行 | 进程内 daemon 线程 | 进程关闭即停止 |
| 时间 | `datetime.now()` 本地时间 | 时区、DST 和时钟跳变策略未建模 |
| 到期去重 | 进程内 `_last_fired` | 重启、多进程和分布式场景不能保证去重 |
| 队列 | 锁保护的内存 `list` | 无持久化、确认、重投、优先级和背压 |
| Job ID | 六位随机数 | 未证明跨进程唯一或冲突处理 |
| 持久化 | 重写 JSON 文件 | 无原子写、文件锁、版本或损坏恢复证据 |
| 加载错误 | `except Exception: pass` | 失败可能不可见，难以诊断 |
| 取消 | 删除调度定义 | 已入队事件不会被撤回 |
| 执行状态 | 只记录 Job 定义 | 无 running/succeeded/failed/unknown 与完成证据 |
| 消息来源 | 文本标签 | 无结构化来源、身份、信任和授权快照 |
| Agent 并发 | `agent_lock` 串行化 | 无公平性、超时、优先级和跨进程协调 |

这些是静态代码阅读得到的风险，不表示已经通过运行实验复现。

## 教学实现与真实源码映射的证据边界

README 折叠区说明真实 CC 还涉及三个 Cron Tool、持久化与会话任务、多 Session 锁、文件观察、抖动、自动过期、Job 上限、通知优先级和 Queue Processor。

本轮没有固定 CC 版本、Commit 或重新读取对应源码，因此：

- 可以把这些内容当成教程提供的进一步观察方向；
- 不能把它们写成当前版本已经重新确认的生产事实；
- 后续若据此做实现决策，需要使用当前官方资料和固定版本源码重新核验。

## 掌握情况

### 已基本掌握

- 为什么 s13 的后台执行仍不足以解决“按时间自动产生工作”；
- Scheduler、Queue、Queue Processor 和 Agent Loop 的职责分离；
- CronJob 到期后如何转成 `[Scheduled]` user message；
- 传统固定 Handler Cron 与 Agent Cron 的消费者差异；
- Cron 字段匹配、DOM/DOW OR 语义和两层校验；
- durable 只持久化调度定义，不等于 Durable Execution；
- 消息标签、Runtime 调度和业务授权属于不同层；
- 非抢占式消息注入发生在模型调用边界，而不是修改正在运行的 LLM 请求。

### 已纠正

- Cron 表达式不是正则表达式；
- `DURABLE_PATH` 是持久化文件路径，不是 Cron 表达式定义；
- Scheduler 不直接“给 Agent 线程发消息”，而是先写入队列；
- `cron_scheduler_loop()` 触发的是“到期入队”，不是业务工作已经执行；
- Agent Tool 不是 CronJob 的唯一创建来源，启动加载和程序直接注册也存在；
- Agent Loop 不会永远运行；无 Tool Use 时它会返回，之后由 Queue Processor 启动新 Turn；
- 文本标签不能实现优先级插队或授权。

### 尚待验收

- 独立写出完整注册、触发、交付和执行伪代码；
- 实际运行一个无危险副作用的短任务，观察注册、入队、注入和模型响应顺序；
- 验证 durable Job 写盘与重启加载；
- 验证 Agent 忙时 Cron 事件等待、多个 Job 同时到期和取消已入队 Job；
- 验证非法表达式、持久化文件损坏、进程退出和重复触发等失败场景；
- 重新核验 README 中真实 CC 映射的具体版本和源码位置。

## 本章验收结论

当前已经达到“能够解释核心机制、区分关键边界并映射当前代码”的静态学习目标，但还没有达到完整章节运行验收：伪代码需要由学习者独立复述，真实调度与失败场景尚未运行。

建议下一步只做一个最小验收：先不用真实 LLM，根据固定时间手工推演或测试 `cron_matches()`，再运行一个无副作用的一分钟任务，记录以下五个时刻：

```text
registered → fired → queued → injected → model response
```

## 相关 Work Pool

- [`W-2026-015`](../specs/work-pool/W-2026-015-study-agent-message-injection-steering.md)：消息注入、插队、安全边界、可靠交付与 Eval，`ready / medium`；本章学习过程中新增，尚未启动。
- [`W-2026-013`](../specs/work-pool/W-2026-013-study-task-completion-verification.md)：区分模型声称完成、状态完成与证据验证。
- [`W-2026-012`](../specs/work-pool/W-2026-012-study-production-reactive-context-compaction.md)：压缩和恢复时保持消息协议与 Tool 配对。
- [`W-2026-011`](../specs/work-pool/W-2026-011-study-system-prompt-production-context-governance.md)：每次模型调用的上下文来源、权限和版本治理。
- [`W-2026-007`](../specs/work-pool/W-2026-007-study-side-effect-tool-security.md)：定时或插队消息驱动副作用 Tool 时的权限、幂等和审批。
