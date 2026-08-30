# s06 Subagent 学习笔记

> 学习进度：核心机制已理解。已完成 Tool 接口与子 Agent Loop、上下文隔离、共享文件副作用、摘要回传与父 Agent 验证责任的边界校准；尚待完成一次运行实验和本章最终伪代码验收。

## 一、本章核心结论

s06 在主 Agent 的工具集合中新增 `task`。从主 Agent 视角看，`task` 仍是普通 Tool；它的特殊之处在于对应 Handler `spawn_subagent()` 内部会启动另一套 Agent Loop。

子 Agent 使用独立的 `messages[]`、独立的 System Prompt 和受限工具集合。它完成子任务后，只把最终文本作为 `task` 的 Tool Result 返回给主 Agent，中间消息和工具轨迹不进入主 Agent 上下文。

当前教学实现只提供**上下文隔离**，不提供完整运行环境隔离：父子 Agent 共享 `WORKDIR`，子 Agent 的文件修改会真实保留；子 Agent 的工具调用仍经过同一套 Hook 和权限检查。

## 二、我的原始理解

1. 主 Agent 添加了一个“创建子 Agent”的 Tool；这个 Tool 比较特殊，因为它里面运行的也是一个 Agent。
2. 子 Agent 有新的上下文、自己的 Tools，并可以处理需要多轮探索和工具调用的子任务。
3. 父子 Agent 的工具可能大量重叠，具体能力由业务代码和 Harness 对两者职责的定义决定。
4. 子 Agent 最终把一段 concise summary 返回给主 Agent。
5. 如果子 Agent 只说“任务完成”，父 Agent 可以结合自己发出的 `task` 输入理解原任务，但是否需要二次验证取决于父 Agent 的能力和控制规则。

## 三、已经理解正确的部分

### 3.1 Tool 接口与子 Agent 执行单元

🔴 **已验证理解**：主 Agent 调用的是 `task` Tool；`task` 对应的 Handler `spawn_subagent()` 内部运行一个具有独立消息列表、System Prompt、工具集合和模型循环的子 Agent。

```text
task：暴露给父模型的工具接口
spawn_subagent：task 对应的 Handler
Subagent：Handler 内部运行的独立 Agent Loop
```

因此，“一个工具里面运行了一个 Subagent”是可保留的直观理解，但 Tool 与 Agent 不是同一个对象层级。

### 3.2 子 Agent 的能力来源

🔴 **已验证理解**：子 Agent 的具体职责和可用工具由业务代码与 Harness 配置、限制和控制。

还要保留模型与 Harness 的边界：

- 模型能力决定它能够理解、推理和生成到什么程度；
- System Prompt 描述角色、目标和行为偏好；
- Tool 与权限决定它可以对环境执行哪些动作；
- 步数、时间、Token 和成本预算限制一次执行能走多远；
- Runtime 与 Harness 决定调用、状态、失败和副作用如何被管理。

Harness 可以组织和约束模型能力，但不能凭空创造底层模型没有的能力。

### 3.3 上下文隔离与文件副作用共享

🔴 **已验证理解**：子 Agent 使用全新的 `messages[]`，主 Agent 不会接收它的完整对话和工具轨迹。

🔴 **校准后表述**：上下文隔离不等于文件系统隔离。当前父子 Agent 共享 `WORKDIR`；子 Agent 调用 `write_file` 或 `edit_file` 后，真实文件已经发生变化，只是修改过程没有进入父 Agent 的上下文。

### 3.4 父 Agent 能看见的任务边界

主 Agent 发出 `task` Tool Call 后，该 Tool Call 和输入已经保存在主 `messages` 中。子 Agent 完成后，主上下文大致包含：

```text
父 Agent 原有 messages
  ↓
assistant: task({ description: "修改 a.py ..." })
  ↓
user: tool_result("任务完成")
```

🔴 **已验证理解**：如果 `task.description` 提到了 `a.py`，父 Agent 下一轮可以结合自己之前发出的 Tool Call 和子 Agent 返回的摘要，知道原任务涉及 `a.py`。

如果任务输入没有文件名，摘要也没有说明修改对象，父 Agent 只能主动读取工作区状态，例如执行 `git status`、`git diff --name-only` 或 `git diff`，才能发现真实改动。

## 四、需要校准的边界

### 4.1 子 Agent 不会天然“做复杂事情”

子 Agent 适合承接边界清晰、可能需要多轮探索和工具调用的子任务，但它是否复杂、能否完成，仍取决于模型、任务描述、工具、权限、预算和环境。

使用 Subagent 的主要收益不是让模型自动变聪明，而是：

- 给子任务更干净、更聚焦的上下文；
- 把大量中间探索留在子 Agent 内部；
- 让主 Agent 只接收对后续决策有用的结果。

同时会付出额外模型调用、延迟、成本、协调和信息损失。

### 4.2 Summary 是有损边界，不是完成证据

`SUB_SYSTEM` 要求子 Agent 返回 concise summary，但 `extract_text()` 只负责提取文本，并不校验：

- 子任务是否真的完成；
- 摘要是否准确、完整；
- 文件是否只修改了允许范围；
- 测试是否运行并通过；
- 是否发生未报告的副作用。

所以 `"任务完成"` 只是一段模型输出，不能直接等同于可验证的完成状态。

### 4.3 “能够验证”“要求验证”“强制验证”是三层

父 Agent 验证子任务结果，需要同时具备相关工具和控制规则：

| 层次 | 当前含义 | 确定性 |
| --- | --- | --- |
| 拥有能力 | 父 Agent 有 `read_file`、`bash` 等工具 | 只能说明可以检查 |
| Prompt 要求 | System Prompt 要求检查 diff、运行测试 | 提高执行概率，不保证遵守 |
| Harness 强制 | 程序自动收集证据、执行校验或设置验收状态 | 才能形成确定性控制 |

当前教学代码让父 Agent **可以验证**，但 `SYSTEM` 没有要求它在每次 `task` 返回后验证，Harness 也没有自动执行验收，因此不保证真的发生二次验证。

代码修改任务的建议验证链是：

```text
收到 task summary
  ↓
检查 git status / git diff
  ↓
读取关键文件
  ↓
运行相关测试、Lint 或类型检查
  ↓
根据真实证据确认、继续修复或交给用户
```

生产实现可以进一步要求子 Agent 返回结构化的 `status`、`files_changed`、`commands_run`、`tests` 和 `artifacts`，但这些声明仍应和确定性证据交叉验证。

### 4.4 `text` 内容块不是结束标志

`extract_text()` 只检查内容块是否为 `type == "text"`。这表示内容块携带文本，不表示 Agent 已经完成：同一条 assistant response 可以同时包含 `text` 和 `tool_use`。

当前循环是否继续由 `response.stop_reason` 决定：

```python
if response.stop_reason != "tool_use":
    break
```

如果第 30 轮仍然是 `tool_use`，程序执行工具后会追加一条 `tool_result`，随后 `for range(30)` 自然耗尽；最后一条消息不是 assistant 最终回答，因此通常提取不到文本。

但“提取不到文本”不能严格证明达到了步数上限。更可靠的实现应显式记录正常退出、步数耗尽、取消、超时和错误等终止原因。

### 4.5 Subagent 不等于 Agent Team

s06 的 Subagent 是同步、临时、结果返回后销毁的执行单元。它不具备持续身份、异步收件箱、长期协作和任务认领机制；这些属于后续 s13、s15-s18 的学习范围。

## 五、当前代码的对象与职责

| 对象 | 当前职责 | 不负责什么 |
| --- | --- | --- |
| `SYSTEM` | 引导主模型为复杂子问题调用 `task` | 不强制委派，也不强制验收子任务 |
| `task` Tool Schema | 描述父模型发起委派时的输入契约 | 不执行子 Agent，不保证描述完整 |
| `TOOL_HANDLERS["task"]` | 把 `task` 名称映射到 `spawn_subagent()` | 不定义子 Agent 的工具与权限 |
| `spawn_subagent()` | 创建 fresh `messages[]` 并运行最多 30 轮子循环 | 不提供进程、文件系统或租户隔离 |
| `SUB_SYSTEM` | 要求子 Agent 完成指定任务、简洁总结且不再委派 | 不能程序化保证完成或总结质量 |
| `SUB_TOOLS` / `SUB_HANDLERS` | 定义子 Agent 能看到和执行的工具 | 不自动继承父 Agent 的全部工具 |
| `trigger_hooks()` | 在子 Agent 工具调用前后继续执行权限与日志 Hook | 不等同于完整服务端授权或沙箱 |
| `extract_text()` | 从内容块中提取文本作为 Tool Result | 不判断任务成功，也不可靠判断终止原因 |
| 父 `agent_loop()` | 保存自己的 Tool Call 与 Tool Result，再决定下一步 | 不自动验证子 Agent 的文件改动和完成声明 |

## 六、关键流程伪代码

```text
父 Agent 判断某个子问题适合委派
  ↓
父模型生成 task(description) Tool Call
  ↓
父 Harness 调用 spawn_subagent(description)
  ↓
创建子 Agent：
  messages = [description]
  system = SUB_SYSTEM
  tools = SUB_TOOLS
  ↓
最多循环 30 轮：
  调用模型
  保存 assistant response
  if stop_reason 不是 tool_use:
      结束子循环
  对每个 Tool Call：
      执行 PreToolUse Hook
      校验权限并调用 SUB_HANDLER
      执行 PostToolUse Hook
      收集 Tool Result
  把 Tool Results 追加到子 messages
  ↓
提取子 Agent 最终文本
  ↓
丢弃子 messages，把文本作为 task Tool Result 返回
  ↓
父 Agent 在下一轮同时看到原 task 输入和返回文本
  ↓
父 Agent 可选择检查文件、diff 和测试，但当前 Harness 不强制
```

## 七、待完成的本章验收

1. 运行一个只读子任务，观察父 `messages` 与子 `messages` 的边界。
2. 运行一个写文件子任务，验证子 Agent 对共享工作目录造成的真实副作用。
3. 在父 Agent 收到不完整 summary 后，观察它是否主动执行 `read_file`、`git diff` 或测试；区分“模型主动验证”与“程序强制验证”。
4. 独立写出能够区分 `completed`、`step_limit`、`timeout`、`cancelled` 和 `error` 的终止状态伪代码。
5. 能解释为什么 `text` 内容块不是完成标志，以及为什么 summary 不是完成证据。

## 八、当前掌握状态

- 已掌握：`task` Tool、Handler 与子 Agent Loop 的对象层级。
- 已掌握：fresh `messages[]`、摘要回传和主上下文降噪的目的。
- 已校准：上下文隔离不等于文件系统或安全隔离。
- 已校准：业务/Harness 能力配置与底层模型能力的边界。
- 已校准：父 Agent 能验证不等于 Prompt 要求验证，更不等于 Harness 强制验证。
- 待验证：真实运行轨迹、文件副作用、父 Agent 验收行为和显式终止状态。

## 九、后续学习

真实项目与生产级 Subagent Runtime 的系统调研已记录到 [`W-2026-004：生产级 Subagent 机制与真实项目调研`](../specs/work-pool/W-2026-004-study-production-subagent-runtime.md)。

该任务当前只进入 Work Pool，不立即启动。建议先继续完成：

- s08 Context Compact：比较隔离与压缩如何共同管理上下文；
- s11 Error Recovery：补齐超时、重试、恢复和终止状态；
- s13 Background Tasks：理解同步与异步子任务；
- s15 Agent Teams：区分一次性 Subagent 与持久队友；
- s18 Worktree Isolation：理解共享目录与隔离工作区的工程取舍。
