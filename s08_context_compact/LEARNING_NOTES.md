# s08 Context Compact 学习笔记

> 学习进度：已建立四层上下文压缩的总体心智模型，重点理解了 L1 `snip_compact`、L2 `micro_compact`、消息与 Content Block 的结构、工具调用/结果配对，以及 Tool Result 压缩的生产边界；已完成两道 D2 场景题的核心判断。L3/L4 的逐行代码与完整运行实验尚待继续学习。

## 一、本章核心问题

Agent 在长任务中会不断把用户消息、模型回答、工具调用和工具结果追加到 `messages`。上下文窗口有限，历史持续增长后可能带来：

- 请求超过模型上下文上限；
- 每轮输入 Token、成本和延迟持续增加；
- 大量旧信息干扰当前推理；
- 粗暴删除历史后丢失任务目标、工具结果或执行状态。

本章核心不是单纯“缩短字符串”，而是在有限 Context 中管理信息：

> 上下文压缩是一种有损的信息管理。每种策略都要回答何时触发、删除什么、保留什么，以及丢失后如何恢复。

## 二、我的原始理解

我对上下文压缩方式的初步回顾：

1. 直接删除 `messages` 中间的大段消息；
2. 裁剪数据量很大的 Tool Result，用磁盘或其他外部数据形式代替；
3. 让 LLM 总结历史，进一步缩短 `messages`。

对消息与工具配对的理解：

- `message.content` 内部由一个个 Content Block 组成；
- `tool_use` 和 `tool_result` 需要保持配对；
- 当 `tail_start` 落在 `tool_result` 消息上时，检查它前面的 `tool_use` 消息，并扩大尾部保留区；
- `collect_tool_results()` 返回的 `block` 是 `messages` 内原字典对象的引用，修改 `block["content"]` 会同时修改原始消息。

对生产 Tool Result 压缩的初步理解：

- 短结果没有必要为了压缩而压缩；
- 是否压缩以及怎样压缩，需要结合具体 Tool 和业务风险；
- 只读工具与转账、发信、创建资源等有副作用的工具不能使用完全相同的恢复提示；
- 特殊工具可以使用专门的 `compress_result()`，或由统一元数据驱动压缩策略。

## 三、四层压缩的校准后总览

### 3.1 L1：`snip_compact`——消息级裁剪

🔴 **已验证理解**：当消息条数超过限制时，保留开头和最近消息，将中间一整段替换为一条占位消息。

```text
头部消息
  +
[snipped N messages]
  +
尾部消息
```

它删除的是完整 Message，不是 Message 内部的部分字符。

### 3.2 L2：`micro_compact`——旧工具结果正文占位

🔴 **校准后理解**：保留较旧工具调用的消息结构与配对关系，只把较长的 `tool_result.content` 替换为占位符。

```text
assistant：旧 tool_use
user：旧 tool_result，正文替换为占位符
```

当前教学代码保留最近 3 个 Tool Result Block 的完整内容；更旧且正文超过 120 字符的结果会变成：

```text
[Earlier tool result compacted. Re-run if needed.]
```

程序只是按时间顺序判断“旧”，并不真正理解某个结果是否仍然重要。

### 3.3 L3：`tool_result_budget`——大结果外置

🔴 **已验证理解**：当最新一批工具结果特别大时，把完整结果写入磁盘，活跃上下文只保留路径和短预览。

```text
完整 Tool Result
  ↓ 落盘
.task_outputs/tool-results/<tool_use_id>.txt

模型上下文中保留：
  result path + preview
```

L3 不是给 L2 的占位符建立索引。L2 通常直接丢掉旧结果正文；L3 则先持久化完整大结果，提供显式恢复路径。

当前只掌握 L3 的总体作用，具体阈值、排序和循环逻辑尚待逐行学习。

### 3.4 L4：`compact_history`——LLM 历史摘要

🔴 **已验证理解**：前三层仍不能满足预算时，额外调用一次 LLM，将长历史提炼为短摘要，并用摘要替换活跃消息历史。

在摘要前，代码先把完整历史写入 transcript。Transcript 是压缩前的会话流水，用于审计、调试和恢复；它落盘后不会自动重新进入模型上下文。

当前教学实现只把序列化历史的前 80000 字符交给摘要模型，因此“全量摘要”是设计意图，不保证所有原始字符都被模型处理。

### 3.5 `reactive_compact`——应急触发路径

`reactive_compact` 不是第五种新的内容表示，而是另一种触发时机：

```text
auto compact：调用 API 前，程序估算超限并主动压缩
reactive compact：API 实际返回 prompt_too_long 后，应急压缩并重试
```

当前 `estimate_size()` 估算的是字符串长度，不是真实 Token，因此需要 API 报错后的兜底路径。

## 四、消息与 Content Block

### 4.1 纯文本消息

请求历史中的纯文本可以使用字符串简写：

```python
{"role": "user", "content": "你好"}
{"role": "assistant", "content": "你好，有什么可以帮你？"}
```

但 SDK 返回的 `response.content` 是 Content Block 列表，所以本章保存的 assistant 消息通常是：

```python
{
    "role": "assistant",
    "content": [TextBlock(...)],
}
```

### 4.2 Tool Use / Tool Result 是 Block

🔴 **已验证理解**：`tool_use` 和 `tool_result` 是 `message.content` 中的 Block，不一定各自独占一条 Message。

一条 assistant 消息可以包含：

```text
TextBlock
ToolUseBlock1
ToolUseBlock2
```

工具结果通过 ID 与调用建立逻辑配对：

```text
ToolResultBlock.tool_use_id == ToolUseBlock.id
```

## 五、串行与同轮多工具调用

### 5.1 同一次模型响应请求两个工具

```text
user      content: string
assistant content: [ToolUseBlock1, ToolUseBlock2]
user      content: [ToolResultBlock1, ToolResultBlock2]
assistant content: [TextBlock]
```

这表示两个 Tool Use 在同一次模型响应中产生。Harness 可以并行或顺序执行它们；消息分组本身不强制并行。

### 5.2 模型根据前一个结果再决定调用下一个工具

```text
user      [普通问题]
assistant [ToolUseBlock1]
user      [ToolResultBlock1]
assistant [ToolUseBlock2]
user      [ToolResultBlock2]
assistant [TextBlock]
```

🔴 **已验证理解**：这是 Agent Loop 连续运行多轮。它包含三次 LLM 调用和两次工具执行。

## 六、L1 的切片与配对边界

`snip_compact()` 的三个区域是：

```python
messages[:head_end]            # 保留头部
messages[head_end:tail_start]  # 删除中间，左闭右开
messages[tail_start:]          # 保留尾部
```

头尾调整都在扩大保留区域：

| 边界 | 调整 | 作用 |
| --- | --- | --- |
| 头部结束于 `tool_use` | `head_end += 1` | 向右多保留紧随的结果消息 |
| 尾部开始于 `tool_result` | `tail_start -= 1` | 向左多保留前面的调用消息 |

🔴 **校准后理解**：尾部逻辑不是从 `tail_start` 开始不断向前搜索，而是只检查 `messages[tail_start - 1]` 这一条相邻消息。若当前消息包含任意 `tool_result`，且前一条包含任意 `tool_use`，便执行一次 `tail_start -= 1`。

例如：

```text
48 assistant [ToolUseBlock1, ToolUseBlock2]
49 user      [ToolResultBlock1, ToolResultBlock2]  ← 原 tail_start
50 assistant [TextBlock]

tail_start: 49 → 48
保留 messages[48:]
```

当前代码只检查消息类型，没有逐个比较 `tool_use.id` 与 `tool_result.tool_use_id`，因此它是简单的切口保护，不是完整的协议修复器。

## 七、L2 的 Python 对象引用

`collect_tool_results()` 收集：

```python
(message_index, block_index, block)
```

其中 `block` 与 `messages[message_index]["content"][block_index]` 指向同一个可变字典对象。后续执行：

```python
block["content"] = "[Earlier tool result compacted. Re-run if needed.]"
```

会原地修改 `messages` 中的 Tool Result。

需要区分：

```python
block["content"] = "..."  # 修改共享对象，messages 随之改变
block = {"content": "..."}  # 只重新绑定局部变量，不会替换 messages 中的对象
```

## 八、生产 Tool Result 压缩边界

### 8.1 短结果不必压缩

🔴 **已验证理解**：如果结果很短，并且已经包含后续推理所需事实，就没有必要为了形式执行压缩。

但“扣费成功”虽然短，从业务安全角度仍可能缺少操作 ID、金额、资源状态和幂等信息。是否需要压缩与结果契约是否完整，是两个不同问题。

### 8.2 不同工具需要不同恢复策略

```text
只读、可重跑工具
→ 可以保留占位符，必要时重新执行

写入、已成功工具
→ 保留操作凭证和资源 ID，禁止盲目重跑

超大但仍可能需要的结果
→ 完整结果外置，活跃上下文保留摘要和引用

失败或状态未知的工具
→ 保留错误分类、可重试性和是否可能已产生副作用
```

关键 Tool Result 的压缩摘要可以评估以下字段：

```json
{
  "tool": "create_ticket",
  "status": "succeeded",
  "operation_id": "op_123",
  "resource_id": "ticket_456",
  "idempotency_key": "req_789",
  "retry_policy": "do_not_retry",
  "result_ref": "tool-results/op_123.json"
}
```

进一步学习已记录到 [W-2026-006：Tool Result 压缩、恢复与副作用安全学习](../specs/work-pool/W-2026-006-study-tool-result-compaction-and-recovery.md)，当前只进入 Work Pool，不自动启动。

## 九、当前关键伪代码

### 9.1 L1 裁剪边界

```text
if 消息条数没有超限：
  原样返回

计算头部结束位置和尾部开始位置

if 头部最后一条包含 tool_use：
  向右扩大头部，保留紧随的 tool_result 消息

if 尾部第一条包含 tool_result
   and 它前一条包含 tool_use：
  tail_start 向左移动一条

删除 [head_end, tail_start) 中间区域
插入一条 snipped 占位消息
```

### 9.2 L2 旧结果占位

```text
收集所有 tool_result block 的原对象引用
保留最近 3 个结果

for 每个更旧的结果：
  if 正文长度超过 120：
    原地替换 content 为占位符
```

## 十、当前掌握状态与待验收问题

- 已掌握：Message 与 Content Block 的基本结构；
- 已掌握：同轮多 Tool Use 与串行多轮 Tool Use 的消息序列；
- 已掌握：L1 删除中间 Message 的总体机制；
- 已掌握：头尾边界调整都是扩大保留区域；
- 已掌握：L2 通过共享字典引用原地替换旧结果正文；
- 已校准：尾部边界只检查相邻前一条消息，不会向前搜索完整调用链；
- 已校准：L2 占位与 L3 大结果落盘不是同一机制；
- 已建立：L3、L4 和 reactive compact 的初步心智模型；
- 待学习：L3 的总预算、单结果阈值、排序和落盘代码；
- 待学习：L4 transcript、摘要替换和最近消息保留的具体代码；
- 待验收：不看代码写出四层压缩的完整伪代码；
- 待验收：设计不会重复执行副作用工具的压缩与恢复方案；
- 待验证：运行构造历史，观察 L1/L2/L3/L4 分别怎样改变 `messages`。

## 十一、D2 场景题回答与校准

### 11.1 被外部修改的 300KB 配置文件

题目要求在文件后来发生变化时，仍能引用“当时读取的版本”。

我的回答：

> 选择 L3。配置对改动敏感，记录历史版本和历史修改有利于回滚；记录原内容和 Diff 内容。

🔴 **已验证理解**：应选择 L3，把当时读取的完整配置作为快照持久化，而不是使用 L2 后重新读取已经变化的当前文件。

需要补充：

- L3 保存原内容，但当前教学代码不会自动计算 Diff；
- 建议同时保存来源路径、读取时间、版本/Commit、内容 Hash 和 `result_ref`；
- Diff 需要明确比较基线，例如“保存快照 vs 当前文件”或“修改前 vs 修改后”；
- 保存快照有利于比较与审计，但“能够回滚”还需要恢复命令、权限、写入校验和失败处理；
- 配置可能包含密钥或敏感数据，外置存储需要权限与保留策略。

校准后的结果结构示例：

```json
{
  "status": "captured",
  "source_path": "config/app.yaml",
  "captured_at": "<timestamp>",
  "version": "<commit-or-version>",
  "content_hash": "<sha256>",
  "result_ref": "tool-results/<tool_use_id>.txt"
}
```

### 11.2 已成功创建、但返回 100KB 的工单

我的回答：

> 把创建工单的完整结果存入外部存储，原内容替换成文件名；不能使用 `Re-run if needed`，因为创建工单是危险的 POST 操作，不能直接重复执行；后续需要时用 `read_file` 读取保存路径。

已确认正确的部分：

- 🔴 **已验证理解**：100KB 完整结果适合外置，Context 中保留短结果和恢复引用；
- 🔴 **已验证理解**：已经成功创建工单后，不能用通用的 `Re-run if needed` 引导 Agent 再次创建；
- 🔴 **已验证理解**：若完整结果存为文件且 Agent 有权限，可以使用 `read_file` 按 `result_ref` 恢复历史详情。

需要校准的部分：

1. 风险来自“创建工单具有副作用且可能非幂等”，不是因为 HTTP 方法叫 POST；POST 也可以通过服务端幂等键实现安全去重。
2. Context 中不能只留下文件名，还应直接保留继续执行所需的最小操作凭证。
3. 磁盘文件是创建当时的历史快照；如果需要工单当前状态，应使用 `ticket_id` 查询工单系统这一权威来源。

校准后的最小内容：

```json
{
  "tool": "create_ticket",
  "status": "succeeded",
  "ticket_id": "ticket_456",
  "operation_id": "op_123",
  "idempotency_key": "req_789",
  "retry_policy": "do_not_retry_create; query_by_ticket_id",
  "result_ref": "tool-results/op_123.json"
}
```

恢复路径分为：

```text
需要创建当时的完整响应
→ read_file(result_ref)

需要工单当前状态
→ get_ticket(ticket_id)

不确定创建请求是否成功
→ 使用 operation_id / idempotency_key 查询状态，不直接重复创建
```

### 11.3 本轮验收结论

- 已通过：能够根据“历史快照是否可重现”选择 L2 或 L3；
- 已通过：知道有副作用工具不能使用通用重跑提示；
- 已通过：能够提出完整结果外置和按引用恢复；
- 已校准：保存历史快照不自动等于具备回滚能力；
- 已校准：副作用与幂等性是工具语义，不能只根据 HTTP POST 判断；
- 已校准：历史文件与业务系统当前状态是两个不同的数据来源；
- 尚待：L3/L4 逐行代码与一次真实运行验证。
