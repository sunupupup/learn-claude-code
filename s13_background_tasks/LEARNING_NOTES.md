# s13 Background Tasks 学习笔记

## 学习状态

- 当前状态：**核心机制验收通过；运行时失败场景仍待实验**。
- 已确认范围：本章教学代码、当前 `README.md`、本次代码注释与讨论。
- 证据边界：本次没有实际运行 `code.py` 做并发实验；README 中关于真实 Claude Code（CC）源码的内容只作为本章给出的源码映射记录，没有重新核验当前版本。

## 章节衔接

s12 已经能用 Task System 表达任务状态和依赖关系，但耗时 Tool 仍会阻塞 Agent Loop。s13 在 Harness 层加入后台执行与完成通知，使慢操作执行期间 Agent 还能处理其他工作。

s13 解决的是“慢操作不阻塞”，还没有解决“按时间触发任务”，因此下一章 s14 引出 Cron Scheduler。

## 核心心智模型

```text
模型产生 tool_use
  ↓
Harness 执行后台路由策略
  ├─ 模型传入 run_in_background=true
  └─ 否则使用慢命令关键词启发式兜底
  ↓
注册 bg_id 和 running 状态
  ↓
daemon worker 在线程中同步执行 Tool
  ↓                         ↓
主循环立即返回占位           worker 写入结果并标记 completed
tool_result                  ↓
  ↓                     后续循环边界收集结果
Agent 继续工作               ↓
                        注入 task_notification
```

这里的“异步”是系统效果：主 Agent Loop 不等待慢 Tool 完成。教学代码的具体实现仍是 worker 在线程里同步调用 `execute_tool()`，并不是把 Tool Handler 全部改写成 `async/await`。

## 关键术语与系统层次

### Background Task（后台任务）

- 中文含义：把耗时操作交给独立执行单元，调用方先继续运行。
- 所在层次：Agent Runtime / Harness 的执行与生命周期管理层。
- 本章实现：Python `threading.Thread` 加进程内字典。
- 边界：后台任务不是 Subagent。它只是异步执行一个 Tool，没有独立模型、独立上下文或自主规划能力。

### Dispatch Policy（分派策略 / 路由策略）

- 解决的问题：决定一次 Tool Call 是前台同步执行还是后台执行。
- 本章实现：模型提供的 `run_in_background` 参数与 Harness 的关键词启发式规则共同决定。
- 专业表述：**模型显式请求后台执行，Harness 使用确定性启发式规则兜底。**

### Placeholder Tool Result（占位 Tool Result）

- 原始 `tool_use` 必须先得到一个配对的 `tool_result`。
- 后台分派成功后，Harness 立即返回包含 `bg_id` 的占位结果，表示“已接收并开始执行”，不表示命令已经完成。
- 真正完成时不再复用原始 `tool_use_id` 发送第二个 Tool Result，而是注入独立的 `<task_notification>` 文本事件。

### Shared-state Synchronization（共享状态同步）

- 解决的问题：多个执行线程访问共享任务状态时，保持一次状态转换涉及的数据一致。
- 本章共享状态：`background_tasks`、`background_results` 以及它们之间的对应关系。
- 边界：锁保护的是共享状态及其不变量，不是单独“锁住某个变量”或“锁住某个 ID”。但是否需要某个具体临界区，仍取决于真实并发访问方式。

## 我的原始理解与校准

### 1. `run_in_background` 是模型决策与 Harness 规则的结合

我的原始理解：

> 这个方法，agent 判断 + 某些硬编码判断，结合了。

🔴 **已验证理解**：后台分派不是纯模型决策，也不是纯硬编码；模型生成 Tool 参数，Harness 再执行确定性的分派策略。

专业准确表述：

> `should_run_background()` 实现了两层后台路由：`run_in_background=true` 时采用模型的显式请求，否则由 Harness 的慢命令关键词启发式规则兜底。

需要继续注意：当前实现用 `tool_input.get("run_in_background")`，所以“字段缺失”和“显式传入 `false`”都会继续进入启发式判断。它并没有实现“模型显式要求前台时强制前台”。

### 2. 当前后台路径主要面向 Bash

我的原始理解：

> 这一章节的后台任务其实都是针对于 bash 这个工具的。

🔴 **已验证理解**：当前 Tool Schema 只有 `bash` 暴露 `run_in_background`，启发式函数也只把 Bash 命令识别为慢操作，因此正常协议路径主要面向 Bash。

边界：`should_run_background()` 的显式参数分支没有先检查 `tool_name == "bash"`。在当前 Schema 下通常不会出问题，但如果将来其他 Tool 也带有同名字段，Harness 应明确按工具能力校验，而不是只依赖模型遵守 Schema。

### 3. `bg_id` 是后台生命周期关联 ID

我的原始理解：

> 后续任务完成的时候，会依赖这个 bg_id 进行结果关联。

🔴 **已验证理解**：占位结果和完成通知都携带同一个 `bg_id`，用它关联后台任务的“已分派”和“已完成”两个时刻。

`f"bg_{_bg_counter:04d}"` 中的 `04d` 会把数字至少补齐为 4 位，便于日志阅读和一定范围内的字典序排序。它不是生产级全局唯一 ID：进程重启会重新从 1 开始，多调用线程下 `_bg_counter += 1` 也需要同步或换用更稳定的 ID 生成方式。

### 4. 锁与唯一 `bg_id` 的关系

我的原始理解：

> 主线程会读取，worker 线程会修改这个对象，所以需要锁；但每个任务的 key 都是唯一 `bg_id`，似乎不会发生重复操作。

🔴 **已验证理解**：主线程与 worker 确实共享后台任务容器；唯一 `bg_id` 能避免不同任务互相覆盖。

校准后表述：

> 唯一 key 解决的是任务身份冲突，锁解决的是跨线程状态转换的一致性。例如 worker 必须让 `status=completed` 与对应 `result` 作为一致状态被收集器观察，收集器也应一致地移除任务元数据和结果。

当前教学实现的具体边界：

- `_bg_counter += 1` 没有加锁，但当前只有主 Agent Loop 调用 `start_background_task()`，所以这个调用模型下不会发生计数器竞争；以后若允许多个提交线程，就需要同步。
- 初始任务记录在 `thread.start()` 之前写入，因此仅为了“worker 能看见已初始化记录”，这个临界区并不是当前时序下唯一可行的保证。
- `collect_background_results()` 先锁内扫描、再逐项重新加锁删除。当前只有一个收集者且 worker 完成后不再修改该任务，所以可以工作；如果扩展为多个收集者，这两段并不是一个完整原子操作，仍可能重复观察同一个 `bg_id`。
- 更成熟的实现通常会把完整状态转换放进一个临界区，或使用线程安全队列、`Future`、持久任务表等更明确的并发原语。

### 5. `results` 与通知注入

我的原始理解：

> `results` 搜集这一轮 Tool Call 的所有结果，然后包装成 user message 的 content。

🔴 **已验证理解**：同一次 assistant 响应可能包含多个 `tool_use`，Harness 逐个执行或分派，并把每个对应的 `tool_result` 收集进 `results`，最后组成下一条 user message。

后台任务完成通知也是下一条 user message 的 content，但它是 `text` block，不是 `tool_result`。当前代码先放本轮 `tool_result`，再追加后台通知。

### 6. 收集器不是“时刻监听”

我的原始理解：

> 每轮 loop 的结尾查一遍后台任务状态，及时注入成功任务结果。

确认正确的部分：收集动作确实位于一次 Tool 执行批次之后，并把已完成任务注入后续消息。

校准后表述：

> 教学实现采用轮询式收集（polling）：只有 Agent Loop 继续产生 Tool Use 并走到收集点时，才调用 `collect_background_results()`；它不是持续监听，也不会在后台任务完成的一刻主动唤醒已经返回的循环。

因此，如果模型本轮没有继续调用 Tool、循环直接返回，后台任务即使稍后完成，也要等用户再次触发后续循环才可能被观察；真实 Runtime 通常需要事件队列、唤醒机制或独立任务订阅。

### 7. `output[:200]` 是截断，不是智能摘要

我的原始理解：

> 市面上做上下文或 Bash 结果压缩的工具，很多其实是在处理这个 summary。

🔴 **已验证理解**：它们面对的是同一类工程压力——Tool Result 过大会增加模型上下文、Token 成本和噪声，因此需要缩短模型实际看到的结果。

专业准确表述：

> `output[:200]` 是固定长度的前缀截断（prefix truncation），不是语义摘要，也没有保留完整结果的恢复引用；生产级 Tool Result 压缩通常还会结合命令感知过滤、结构化字段投影、head-tail 截断、LLM 摘要和 Artifact 外置。

重要边界：

- 前 200 个字符可能丢掉输出尾部真正的报错、退出状态和诊断证据。
- README 中的 CC `pendingToolUseSummary` 是用较小模型生成短进度标签的 side-query，主要服务进度展示；本章 `<task_notification><summary>` 承载后台完成信息。二者都在减少信息体积，但消费者、时机和数据流不同，不能视为同一个机制。
- 生产级 Bash 结果压缩、恢复引用与副作用安全已经记录在 [`W-2026-006`](../specs/work-pool/W-2026-006-study-tool-result-compaction-and-recovery.md)，当前仍为 `ready`，本章不提前启动。

## 教学实现与真实 Runtime 的边界

| 维度 | 本章教学实现 | 生产级需要继续考虑 |
| --- | --- | --- |
| 执行模型 | Python daemon thread 中执行同步 Tool | 子进程、任务队列、事件循环或隔离 Runtime |
| 状态 | 进程内字典 | 持久状态、Checkpoint、重启恢复 |
| 完成通知 | Agent Loop 边界轮询 | 事件队列、主动唤醒、订阅或消息系统 |
| 错误 | worker 缺少统一异常状态转换 | failed/cancelled/timed_out、错误分类与重试策略 |
| 生命周期 | running → completed | 取消、超时、部分成功、重试、清理和审计 |
| 并发 | 无后台并发上限或背压 | 配额、队列、背压、资源隔离和公平性 |
| 结果 | 内存保存，通知只留前 200 字符 | 完整结果持久化、稳定引用、权限和保留策略 |
| 退出 | daemon 线程随主进程退出 | 优雅关闭、任务接管或耐久执行 |

README 给出的真实 CC 映射说明：其后台 Shell 更接近“启动独立进程后不在主路径等待”，完成事件进入通知队列；不是照搬本章 Python 线程模型。该部分属于版本相关源码事实，后续若据此做实现决策，需要按具体 CC 版本重新核验。

## 关键流程伪代码

```python
for tool_call in assistant_response.tool_calls:
    if should_run_background(tool_call):
        bg_id = register_running_task(tool_call)
        start_worker(tool_call, bg_id)
        results.append(placeholder_tool_result(tool_call.id, bg_id))
    else:
        output = execute_tool(tool_call)
        results.append(tool_result(tool_call.id, output))

notifications = collect_completed_background_tasks()
messages.append(user_message(results + notifications))
```

其中必须保持两类关联：

1. 消息协议关联：`tool_use_id → tool_result`；
2. 后台生命周期关联：`bg_id → running/completed/result/notification`。

## 掌握情况

### 已基本掌握

- 为什么 s13 要把慢 Tool 从主 Agent Loop 中分离；
- 模型参数与 Harness 启发式共同构成后台分派策略；
- `bg_id`、占位 Tool Result 和完成通知之间的关系；
- 后台任务完成与模型得知完成是两个不同的时刻；
- 唯一任务 ID 与共享状态同步解决的是不同问题；
- `output[:200]` 只是不可恢复的前缀截断，不能等同于生产级上下文压缩。

### 已通过本章问答验收

- 能准确判断 `run_in_background=false` 不会直接强制前台，命中 `test` 关键词后仍会被 Harness 启发式规则分派到后台；
- 能解释占位 `tool_result` 用于完成原始 `tool_use` 的消息协议配对，而独立 `task_notification` 使用 `bg_id` 报告后台任务后续的生命周期事件；
- 已校准专业表述：这里是 Harness 的兜底路由策略，不是安全“防护”；`bg_id` 属于 Harness / Runtime 层，不是业务层 ID。

### 仍待运行实验

- 尚未运行真实示例观察占位结果、主循环继续执行和完成通知的先后顺序；
- 尚未实验 worker 异常、主循环提前返回、进程退出和多个后台任务并发等失败场景。

## 本章验收结果

1. **后台路由题：通过。** `false` 会继续进入 `is_slow_operation()`；`npm test` 命中慢命令关键词，因此最终后台执行。
2. **消息协议题：通过。** 一个 `tool_use_id` 只与一个 `tool_result` 配对；占位结果表示已经分派，完成事件通过独立 `task_notification` 和 `bg_id` 关联，不重复发送同 ID 的 Tool Result。
