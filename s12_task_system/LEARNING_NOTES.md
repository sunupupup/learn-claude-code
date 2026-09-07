# s12 Task System 学习笔记

> 学习状态：基础验收完成；核心机制已理解；生产级并发、验证和异步协同留待后续专题。

## 一、本章核心结论

s12 在 Agent Loop 上增加了一个持久化任务系统。任务不再只是当前对话里的计划文本，而是存储在 `.tasks/` 下的独立 JSON 记录，可以被后续模型轮次或其他执行者读取。

任务系统的核心不是让程序自动完成所有工作，而是把任务的创建、依赖检查、认领和状态迁移变成 Harness 可以检查的显式状态：

```text
pending --claim--> in_progress --complete--> completed
```

`blockedBy` 表示当前任务依赖的上游任务 ID。只有所有依赖都存在且为 `completed`，`claim_task` 才允许认领。

## 二、我的原始理解

1. `Task` 是任务的数据结构，`.tasks` 会把任务状态持久化，所以 Agent 可能跨进程继续查看任务。
2. `write_text` 可能是追加写入，也可能是全量重写。
3. `blockedBy` 看起来像是 LLM 生成的，但不理解为什么它是 ID，而不是自然语言。
4. `create_task` 一次只创建一个任务；多个任务应该通过多次 Tool Call 创建。
5. `create_task` 返回的任务 ID 会通过 message/Tool Result 回到 LLM，后续任务可以引用这个 ID。
6. 当前没有通用 `update_task`，可能由 `claim_task` 和 `complete_task` 分别承担状态更新。
7. `list_tasks` 适合发现任务，`get_task` 适合读取指定任务的完整信息。
8. 主 Agent 可以把任务交给 Subagent，继续自己的工作，再通过任务工具查看 Subagent 的状态。

## 三、已验证的理解

### 3.1 数据结构与持久化

🔴 **已验证理解**：`dataclass` 定义字段形状；`asdict` 和 JSON 序列化把对象转换成可保存内容；`Path.write_text()` 才是实际写入磁盘的动作。

`write_text()` 默认是覆盖写：文件不存在就创建，存在就先截断再写入完整 JSON。当前实现没有原子写入和文件锁，所以它适合教学，不足以处理生产并发和崩溃恢复。

持久化只保存任务记录，不保存 Python 调用栈、正在运行的 Bash 进程或模型隐式状态。新进程需要主动调用 `list_tasks` 发现已有任务。

### 3.2 `blockedBy` 与 Tool Result

🔴 **已验证理解**：`blockedBy` 最终可以由 LLM 放入 `create_task` 的结构化 Tool Call，但它的值必须是任务 ID 字符串数组。

```text
LLM: create_task(A)
程序: 创建 A，并返回 task_A
Tool Result: Created task_A: A
LLM: create_task(B, blockedBy=["task_A"])
```

Harness 不会把自然语言“依赖 A”自动转换成 ID。模型必须使用此前 Tool Result 中的 ID；不存在的 ID 会让任务保持 blocked。

### 3.3 一个任务调用与多个任务调用

🔴 **已验证理解**：一次 `create_task` 只创建一个 `Task` 和一个 JSON 文件；多个任务通过多次调用创建，`blockedBy` 只是 ID 数组，不是嵌套的 Task 对象数组。

依赖任务通常需要跨模型轮次创建，因为模型只有在上一轮 Tool Result 返回后，才能看到新生成的 ID：

```text
Turn 1: create_task(A)
Turn 1 Tool Result: A.id
Turn 2: create_task(B, blockedBy=[A.id])
```

`get_task` 不是为了重新获取刚创建任务的 ID；如果“get A id”指的是从 Tool Result 读取 A.id，那么它和上述流程完全是同一个意思。

### 3.4 状态迁移与工具职责

🔴 **已验证理解**：当前教学版没有通用 `update_task`，但任务仍可通过专用动作更新：

```text
claim_task: pending → in_progress，并设置 owner
complete_task: in_progress → completed，并报告部分下游任务已解锁
```

Task 工具不只是防御性代码：`create_task` 负责创建，`list_tasks/get_task` 负责查询，`claim/complete` 负责状态迁移，`can_start` 负责依赖约束。

### 3.5 `list_tasks`、`get_task` 与 Agent 协同

🔴 **已验证理解**：模型可以在任意一个新的决策点主动调用 `list_tasks` 查看当前任务快照，再根据 Tool Result 决定下一步。

但 s12 没有自动 watcher 或推送通知。它不会在另一个 Agent 修改任务后主动唤醒模型；轮询、文件监听或通知队列属于后续 Runtime/后台协同能力。

`get_task` 适合在已知 ID 时读取完整 description、依赖、owner 和状态。它可以作为主 Agent 查询 Subagent 任务详情的接口，但 s12 本身没有启动异步 Subagent 的能力。

## 四、完整调用链

```text
用户提出多步骤目标
  ↓
LLM 调用 create_task(A)
  ↓
Handler 生成 ID，写入 .tasks/{A}.json
  ↓
Tool Result 把 A.id 返回 messages
  ↓
LLM 调用 create_task(B, blockedBy=[A.id])
  ↓
LLM 调用 claim_task(A)
  ↓
LLM 执行 bash / read_file / write_file
  ↓
LLM 调用 complete_task(A)
  ↓
LLM 调用 claim_task(B)
  ↓
执行 B 并 complete_task(B)
  ↓
模型不再请求工具，返回普通文本
```

这里的 `done` 不是 Task Tool。当前 Run 在模型返回非 `tool_use` 的响应，并且没有其他继续条件时结束。

## 五、任务作用域与协同边界

单个 `.tasks/` 目录适合教学，但如果多个对话、项目或 Agent 共用工作目录，应该增加任务集合的作用域：

```text
.tasks/{task_list_id}/{task_id}.json
```

`task_list_id` 应表示一组跨轮次的长期目标；不要把一次 LLM 请求的 `turn_id` 当成任务目录，因为任务本身需要跨多个 turn 延续。目录隔离也不能代替原子写入、锁、租约、幂等和恢复。

主 Agent 与 Subagent 的协同还需要额外的启动、通知、结果 Artifact、身份和验收机制。相关生产专题记录在 [`W-2026-004`](../specs/work-pool/W-2026-004-study-production-subagent-runtime.md)。

## 六、代码中仍需记住的边界

- 当前任务 ID 是秒级时间戳加四位随机数字，存在碰撞风险；
- 当前只有 `blockedBy`，没有反向 `blocks` 字段，解锁报告需要扫描全部任务；
- 教学版没有依赖环检测、自引用检查和任务输入的完整运行时校验；
- `claim_task` 没有文件锁，两个进程可能同时读到 pending 后竞争写入；
- `owner` 在 `run_claim_task` 中固定为 `agent`，不能准确区分不同执行者；
- `complete_task` 只检查状态，不验证测试、产物或 Bash 是否成功；
- `list_tasks` 返回所有任务的摘要，不是自动筛选出的可执行任务列表；
- `update_context` 不会自动把 `.tasks` 内容注入 System Prompt，恢复时仍需主动查询。

## 七、待验收问题

1. 如果任务 B 的 `blockedBy` 依赖任务 A，而模型刚刚创建 A 后还没有收到 Tool Result，为什么不能可靠地在同一个模型响应里创建 B？请写出两轮消息与 Tool Result 的顺序。
2. 如果任务 A 已经 `completed`，但它实际执行的 Bash 命令失败了，当前 `complete_task` 为什么仍可能把它标记为完成？生产系统应增加哪一个确定性验收点？

## 八、小测回答与校准

### 8.1 依赖任务的两轮创建

我的回答：

> task id 是依赖于业务代码层面来生成的。`create_task(A)` → Tool Result A.id → `create_task(B, blockedBy=[A.id])`。

🔴 **已验证理解**：当前实现由 `create_task()` 在程序层生成任务 ID；模型只有在收到第一个 Tool Result 后，才能把准确的 A.id 填入 B 的 `blockedBy`。

完整消息顺序是：

```text
messages: user 请求
Turn 1 assistant: tool_use create_task(A)
Harness: 写入 A，并追加 user/tool_result，其中包含 A.id
Turn 2 assistant: tool_use create_task(B, blockedBy=[A.id])
```

不能可靠地在同一个模型响应中完成，是因为模型会先一次性生成整条响应中的所有 `tool_use`；执行第一个 Tool Call 的结果不会在生成第二个 Tool Call 之前回到模型。除非工具预先分配 ID，或工具支持带内部引用的批量事务创建，否则模型只能猜测 B 的依赖 ID。

### 8.2 完成状态与实际验证

我的回答：

> A 的状态没有需要依赖其他的强校验，能直接更新。执行 Bash 肯定是在 claim A 之后、complete A 之前；可能需要 `verify_task`，在完成前验证能否标记成完成。

第一句需要校准。🔴 **已验证理解**：当前 `complete_task()` 只要求任务状态是 `in_progress`，然后直接写入 `completed`；它不检查 Bash、测试、文件、数据库或其他真实产物是否成功。

`blockedBy` 只在 `claim_task()` 阶段检查“上游依赖是否完成”，不负责证明当前任务已经完成。即使 A 有上游依赖，只要 A 已经成功 claim，`complete_task(A)` 仍然不会检查 A 的工作结果。

“先 claim，再执行 Bash，最后 complete”是合理的协作约定，但当前代码没有把 Bash 与任务绑定：Bash 工具没有 `task_id`，模型也可能跳过 Bash 或在 Bash 失败后仍调用 complete。

`verify_task` 是可行方向，但不能只是一个模型可选的额外工具。更可靠的做法是让 `complete_task` 内部强制执行确定性验证，或要求它携带由 Harness 生成并验证的证据：

```text
claim_task(A)
  ↓
执行任务工具
  ↓
Harness 自动运行 task-specific verifier
  ├─ 失败：保持 in_progress 或转为 failed，返回证据
  └─ 成功：写入 completed，并保存测试结果 / 文件 Hash / 资源状态
```

验证器应按任务类型选择确定性 Oracle，例如代码任务检查测试退出码，文件任务检查路径和内容 Hash，数据库任务查询真实 Schema；不能只让另一个 LLM 判断“看起来完成了”。

## 九、后续学习

- `s13_background_tasks`：慢操作、异步执行和完成通知；
- `s15_agent_teams` / `s16_team_protocols`：持久队友、消息总线、请求响应和关机握手；
- [`W-2026-004`](../specs/work-pool/W-2026-004-study-production-subagent-runtime.md)：生产级 Subagent 与多 Agent 协同；
- [`W-2026-013`](../specs/work-pool/W-2026-013-study-task-completion-verification.md)：任务完成验证、验收证据与完成门。
