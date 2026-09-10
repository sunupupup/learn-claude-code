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

## 第 1 道验收题与我的 Demo

### 题目

> 每个工作日上午 9 点，让 Agent 检查当前任务并总结阻塞项；重启后仍保留这个计划。请写出从用户提出要求，到 LLM 收到定时消息的完整伪代码。至少覆盖注册、校验、持久化、时间匹配、分钟级去重、入队、等待 Agent 空闲、消息注入和模型调用；同时标出哪些步骤由确定性代码完成，哪些步骤由 LLM 完成，并解释 `durable` 的边界以及它与传统 Cron 的主要区别。

### 我的核心思路

🔴 **已验证理解**：我已经抓住了生产者—消费者主干：

```text
scheduled_jobs（调度定义）
  → Scheduler 每秒检查一次
  → 到期且本分钟尚未触发时生成执行事件
  → job_queue（待交付事件）
  → Queue Processor 等待 Agent 空闲
  → Agent Loop 注入 user message
  → 下一次 LLM Call
```

每秒检查并不表示同一个 Job 每秒执行一次。Scheduler 会记录该 Job 上一次触发的分钟；同一分钟再次匹配时忽略，进入新分钟且再次满足表达式时才产生新的执行事件。

在题目场景中，第一次模型调用会把自然语言转换为类似下面的 Tool Call：

```text
LLM → create_job(
  cron = "0 9 * * 1-5",
  durable = true,
  recurring = true,
  prompt = "检查当前任务并总结阻塞项"
)
```

### 润色后的完整伪代码

下面保留我的 Demo 结构，只修正基础语法和几个会改变行为的状态边界：

```text
# ==================== Tool 定义：提供给 LLM ====================

TOOLS = {
  "create_job": {
    "input_schema": {
      "cron": {
        "type": "string",
        "description": "五字段 Cron 表达式"
      },
      "durable": {
        "type": "boolean",
        "description": "是否持久化调度定义，使进程重启后可以恢复"
      },
      "prompt": {
        "type": "string",
        "description": "任务到期后注入给 Agent 的消息"
      },
      "recurring": {
        "type": "boolean",
        "description": "是否为重复任务"
      }
    }
  },
  "delete_job": { ... },
  "list_jobs": { ... }
}


# ==================== Runtime 状态 ====================

scheduled_jobs = {}   # 调度定义：等待未来某个时间点匹配
job_queue = Queue()   # 执行事件：已经到期，等待交付给 Agent
last_fired = {}       # job_id -> 上次触发的分钟标记
agent_lock = Lock()   # 保证同一时刻只有一个 Agent Turn 运行


# ==================== Tool Handler：确定性代码 ====================

function create_job(cron, durable, prompt, recurring = true):
  validation_error = validate_cron(cron)
  if validation_error exists:
    return ToolError(validation_error)

  job = Job(
    id = generate_job_id(),
    cron = cron,
    durable = durable,
    prompt = prompt,
    recurring = recurring
  )

  # 新建的是“调度定义”，还没有到执行时间，不能直接放进 job_queue。
  scheduled_jobs[job.id] = job

  if durable:
    persist_durable_jobs(scheduled_jobs)

  return ToolResult(job)


function delete_job(job_id):
  job = scheduled_jobs.remove(job_id)
  if job exists and job.durable:
    persist_durable_jobs(scheduled_jobs)
  return ToolResult(job exists)


function list_jobs():
  return ToolResult(scheduled_jobs.values())


TOOLS_HANDLER = {
  "create_job": create_job,
  "delete_job": delete_job,
  "list_jobs": list_jobs
}


# ==================== 启动恢复：确定性代码 ====================

# 只恢复 durable 的调度定义，不恢复未持久化的队列事件或执行现场。
scheduled_jobs.update(load_durable_jobs())


# ==================== Job 生产者：确定性代码 ====================

function produce_jobs():
  while process_is_running:
    sleep(1 second)
    now = current_local_time()
    minute_marker = format(now, "YYYY-MM-DD HH:mm")

    for job in snapshot(scheduled_jobs.values()):
      if cron_matches(job.cron, now):
        # Scheduler 每秒轮询，但同一个 Job 在同一分钟只允许入队一次。
        if last_fired[job.id] == minute_marker:
          continue

        job_queue.push(FiredJob(job_id = job.id, prompt = job.prompt))
        last_fired[job.id] = minute_marker

        # 重复任务保留定义；一次性任务在成功入队后移除定义。
        if not job.recurring:
          scheduled_jobs.remove(job.id)
          if job.durable:
            persist_durable_jobs(scheduled_jobs)


# ==================== Agent 空闲唤醒器：确定性代码 ====================

function queue_processor_loop():
  while process_is_running:
    sleep(200 milliseconds)

    if job_queue.is_empty():
      continue

    # Agent 忙时不抢占当前 LLM Call 或 Tool，只等待下一个安全边界。
    if agent_lock.try_acquire():
      try:
        agent_loop(messages = conversation_history)
      finally:
        agent_lock.release()


# ==================== Agent Loop：Runtime + LLM ====================

function agent_loop(messages):
  while true:
    # 确定性代码：在下一次模型调用前消费已经到期的事件。
    for fired_job in job_queue.consume_all():
      messages.append({
        "role": "user",
        "content": "[Scheduled] " + fired_job.prompt
      })

    # LLM：理解普通用户消息或定时消息，并决定回复或调用 Tool。
    response = LLM(messages = messages, tools = TOOLS)
    messages.append({ "role": "assistant", "content": response.content })

    if response.stop_reason != "tool_use":
      return

    # 确定性代码：执行 LLM 选择的 Tool，并按协议回填 Tool Result。
    tool_results = []
    for tool_call in response.tool_calls:
      handler = TOOLS_HANDLER[tool_call.name]
      result = handler(**tool_call.input)
      tool_results.append({
        "type": "tool_result",
        "tool_use_id": tool_call.id,
        "content": result
      })

    messages.append({ "role": "user", "content": tool_results })


# ==================== 进程启动 ====================

start_daemon_thread(produce_jobs)
start_daemon_thread(queue_processor_loop)
```

这份 Demo 中，LLM 负责两类语义判断：第一次理解“每个工作日上午 9 点……”并决定调用 `create_job`；任务到期后理解 `[Scheduled]` 消息并决定如何回复或调用其他 Tool。注册、校验、持久化、匹配、去重、入队、加锁和消息封装都由确定性 Runtime 代码完成。

### 本次校准的关键点

- `create_job()` 应写入 `scheduled_jobs`，不能直接写入 `job_queue`，否则任务会在注册后立刻执行；
- 每秒轮询需要配合 `last_fired` 做分钟级去重；
- `recurring=True` 表示保留调度定义，只有 `not recurring` 时才在入队后删除；
- Agent Loop 不是永久不退出，因此需要 Queue Processor 在队列非空且 Agent 空闲时启动新的 Agent Turn；
- `durable=True` 只保证调度定义可在重启后恢复，不保证停机期间补跑，也不保证排队事件和执行现场恢复；
- 传统 Cron 到期后通常直接调用固定 Handler；这里到期后先注入消息，再由 LLM 根据上下文决定后续动作。

## 第 2 道验收题：取消、队列与重启

### 题目

```yaml
09:00:00  一个 recurring + durable Job 到期并进入 cron_queue
09:00:00  Agent 正在执行其他任务，持有 agent_lock
09:00:10  用户调用 cancel_job(job_id)
09:00:25  Agent 释放 agent_lock
09:00:30  Queue Processor 再次检查队列
09:01:00  进程重启
```

需要回答：

1. `cancel_job()` 后，`scheduled_jobs`、`cron_queue` 和 `.scheduled_tasks.json` 分别是什么状态？
2. 09:00 已经入队的这次任务还会不会进入 Agent Loop？说明代码依据。
3. 重启后会恢复调度定义、已入队事件，还是执行状态？
4. 设计一个无副作用实验验证判断，并列出需要观察的日志或状态证据。

### 我的回答与校准

#### 1. 取消后的三份状态

我的判断：

> `scheduled_jobs` 和 `.scheduled_tasks.json` 空了，`cron_queue` 里还有一个等待消费的 Job。

🔴 **已验证理解**：对于题目中的目标 Job，取消后会从 `scheduled_jobs` 和持久化文件中消失，但已经进入 `cron_queue` 的这次触发仍然保留。

边界：只有当它是系统中唯一的 durable Job 时，`.scheduled_tasks.json` 才会整体为空；如果还有其他 durable Jobs，文件会保留其他定义。

#### 2. 已入队事件是否还会进入 Agent Loop

我的判断：

> 会进入。`consume_cron_queue()` 会直接取得整个队列，不会额外检查 Job 是否刚刚从 `scheduled_jobs` 删除。

🔴 **已验证理解**：这个判断正确。`cancel_job()` 只取消未来调度，不撤销已经产生的队列事件。09:00:30 Queue Processor 获得 `agent_lock` 后，会启动 Agent Turn；Agent Loop 调用 `consume_cron_queue()`，把这个 Job 转成 `[Scheduled]` user message。

对应调用链：

```text
cancel_job()
  → 只从 scheduled_jobs 删除定义并重写 durable 文件
  → cron_queue 中的 Fired Job 保持不变

queue_processor_loop()
  → 获得 agent_lock
  → run_agent_turn_locked()
  → agent_loop()
  → consume_cron_queue()
  → 注入 [Scheduled] user message
```

#### 3. 重启后恢复什么

我的直观回答：

> 重启后，这个 Job 的东西就都没了。

🔴 **已验证理解**：针对这个已经被取消的 Job，重启后不会恢复其调度定义、已入队事件或执行状态。

更准确的边界是：

- 只有重启时仍存在于 `.scheduled_tasks.json` 的 durable 调度定义会被恢复；
- `cron_queue` 是内存队列，未持久化，重启后不会恢复；
- 当前实现没有持久化执行状态，因此 running、succeeded 或 failed 等现场不会恢复；
- 按题目时间线，09:00:30 到 09:01:00 之间，这次事件可能已经进入 Agent Loop；重启不会撤销重启前已经发生的模型调用。

可以把本题结论压缩成一句话：

> 🔴 取消只阻止未来触发，不撤回已入队事件；重启只恢复文件中仍存在的 durable 调度定义，不恢复内存队列和执行现场。

### 无副作用验证实验

不需要真的等待上午 9 点，也不需要赌 LLM 恰好在运行。测试应该主动控制时间、锁和模型调用：

```text
# 测试缝：把无限循环中的单次工作提取出来
scheduler_tick(now)       # 使用测试传入的时间检查一次调度
queue_processor_tick()    # 检查一次队列并尝试交付

# 1. 准备并加载 recurring + durable Job
write_json(job(cron = "0 9 * * *", recurring = true, durable = true))
load_durable_jobs()

assert job_id in scheduled_jobs
assert job_id in read_json(.scheduled_tasks.json)

# 2. 手动持锁，确定性地模拟 Agent 正忙
agent_lock.acquire()

# 3. 使用 Fake Clock 直接制造 09:00，不等待真实时间
scheduler_tick(now = "2026-09-09 09:00:00")

assert job_id in scheduled_jobs
assert job_id in cron_queue
assert job_id in read_json(.scheduled_tasks.json)
assert logs contain "[cron fire]"

# 4. 取消未来调度
cancel_job(job_id)

assert job_id not in scheduled_jobs
assert job_id in cron_queue
assert job_id not in read_json(.scheduled_tasks.json)
assert logs contain "[cron cancel]"

# 5. Agent 仍忙时，Queue Processor 不能消费
queue_processor_tick()

assert job_id in cron_queue
assert no "[inject cron]" log exists

# 6. 释放锁，使用 Fake LLM 记录消息但不执行任何真实 Tool
agent_lock.release()
queue_processor_tick(fake_llm)

assert job_id not in cron_queue
assert fake_llm.last_messages contains {
  role: "user",
  content: "[Scheduled] ..."
}
assert logs contain "[queue processor] delivering scheduled work"
assert logs contain "[inject cron]"

# 7. 清空内存并重新加载，模拟进程重启
scheduled_jobs.clear()
cron_queue.clear()
last_fired.clear()
load_durable_jobs()

assert job_id not in scheduled_jobs
assert cron_queue is empty
assert no execution state was restored
```

这个实验走完整的 Runtime Workflow：

```text
Scheduler → Queue → Queue Processor → Agent Loop → Messages
```

但不调用真实 LLM。Fake LLM 只记录输入消息，因此不会产生模型 Tool 副作用。当前 Demo 虽然有 Scheduler 和 Queue Processor 后台线程，但 Agent Turn 受 `agent_lock` 串行化；测试可以通过手动持有和释放这把锁，确定性地模拟“Agent 忙”和“Agent 空闲”，不需要制造两个真实 Agent 并发。

本题得到的测试经验：

> 测试时间与并发逻辑时，不要努力制造时间巧合；应通过 Fake Clock、显式的单步 Tick、可控锁和 Fake LLM，把不确定的外部条件变成可重复的状态推进。

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
- 已独立写出 Scheduler、Queue 和 Agent Loop 的完整伪代码主干，并完成关键状态边界校准。
- 能区分取消调度定义、撤回已入队事件和进程重启恢复这三种不同语义。
- 能用 Fake Clock、可控锁和 Fake LLM 设计无副作用的调度测试。

### 已纠正

- Cron 表达式不是正则表达式；
- `DURABLE_PATH` 是持久化文件路径，不是 Cron 表达式定义；
- Scheduler 不直接“给 Agent 线程发消息”，而是先写入队列；
- `cron_scheduler_loop()` 触发的是“到期入队”，不是业务工作已经执行；
- Agent Tool 不是 CronJob 的唯一创建来源，启动加载和程序直接注册也存在；
- Agent Loop 不会永远运行；无 Tool Use 时它会返回，之后由 Queue Processor 启动新 Turn；
- 文本标签不能实现优先级插队或授权。
- `create_job()` 注册的是未来调度定义，应写入 `scheduled_jobs`，而不是直接写入待执行的 `job_queue`；
- 重复任务到期后应保留定义；被移除的是成功入队的一次性任务。

### 尚待验收

- 实际运行一个无危险副作用的短任务，观察注册、入队、注入和模型响应顺序；
- 验证 durable Job 写盘与重启加载；
- 验证 Agent 忙时 Cron 事件等待、多个 Job 同时到期和取消已入队 Job；
- 验证非法表达式、持久化文件损坏、进程退出和重复触发等失败场景；
- 重新核验 README 中真实 CC 映射的具体版本和源码位置。

## 本章验收结论

当前已经达到“能够解释核心机制、区分关键边界、映射当前代码，并独立写出完整伪代码主干”的静态学习目标。第 1 道伪代码验收已经通过校准；第 2 道取消与重启场景的静态判断和无副作用实验设计也已完成，但还没有实际运行该实验，因此尚未达到完整章节运行验收。

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
