# s11 Error Recovery 学习笔记

> 学习主题：Harness 如何在 LLM 调用失败或输出不完整时，判断重试、恢复、降级或终止。
>
> 当前状态：基础验收完成。已经掌握三条恢复路径、错误分类和主要代码位置；lambda 默认参数捕获属于 Python 语法细节，当前有意暂缓，不阻塞本章完成。生产级重试预算、幂等恢复和协议安全压缩留待后续专题。

## 一、本章核心结论

错误恢复不是无条件“再试一次”，而是先识别结果类型，再选择与原因匹配且有上限的动作：

```text
正常完整响应            → 返回或继续 Tool 循环
max_tokens 停止原因     → 提高输出预算；仍截断时提示续写
prompt_too_long 异常    → 改变上下文后重试一次
429 / 529 瞬时异常      → 指数退避 + 随机抖动；必要时切换模型
未分类异常              → 教学版停止并记录错误
```

恢复动作必须有次数、时间、Token 和成本边界。否则错误恢复本身可能变成无限循环或成本放大器。

## 二、我的原始理解与已确认部分

### 1. 本章目的

我的理解：LLM 调用失败或输出不完整时，Harness 需要判断“重试、恢复、降级还是终止”，使 Agent 遇到常见故障时仍能受控运行。

🔴 **已验证理解**：错误恢复的核心不是捕获所有异常，而是把失败分类，并为每一类配置有边界的状态转移。

### 2. max_tokens

我的理解：`max_tokens` 对 LLM 来说不是异常，而是一次正常响应的结束原因；如果业务能够接受截断结果，也可以不重试。

🔴 **已验证理解**：`max_tokens` 是 `stop_reason`，API 调用本身成功，但应用需要决定输出是否完成。

当前教学代码把截断视为未完成：第一次不保存截断内容，把输出预算从 8K 提高到 64K 后重新生成；64K 仍截断时，才保存已有输出并追加续写提示，最多三次。

`escalate` 在这里表示提高输出额度。重新生成仍具有模型非确定性，并不保证前后内容完全一致；64K 也必须受具体模型能力和总上下文预算约束。

### 3. prompt_too_long 与 reactive compact

我的初始理解：reactive compact 可能是一次全量总结式压缩，只剩一条 user message。

校准后：

🔴 **已验证理解**：当前教学实现没有生成摘要，而是在一条恢复提示后保留原消息的最后五条；真实实现通常需要生成或加载结构化摘要，并保留继续任务所需的状态。

我的进一步发现：直接取最后五条可能破坏 `assistant.tool_use` 与 `user.tool_result` 的消息配对。

🔴 **已验证理解**：上下文压缩必须选择协议安全的切点，保留 Tool 调用和结果之间的 ID 与因果关系，不能只按消息数量机械截断。

整个上下文的生产级紧急压缩已记录在 [`W-2026-012`](../specs/work-pool/W-2026-012-study-production-reactive-context-compaction.md)；单独的 Tool Result 压缩与副作用恢复由 [`W-2026-006`](../specs/work-pool/W-2026-006-study-tool-result-compaction-and-recovery.md) 负责。当前章节不展开完整实现。

### 4. 429、529 与退避

我的理解：429/529 属于等待后可能恢复的供应商错误，延迟之后进入下一次尝试；延迟按指数增长，并加入随机抖动。

🔴 **已验证理解**：指数退避逐步降低请求频率，jitter 将并发客户端的重试时刻打散，避免再次同时冲击服务端。

需要区分：429 是请求触发速率或配额限制；529 表示供应商服务暂时过载，不等同于 429 限流。

当前公式为：

```text
base = min(0.5 × 2^attempt, 32) 秒
delay = base + random(0, base × 25%)
```

`MAX_RETRIES = 10` 在当前 `for` 循环中表示最多十次调用尝试。函数虽然声明支持 `Retry-After`，但调用方尚未从异常响应读取并传入该值。

### 5. wrapper 与 RecoveryState

我的理解：`with_retry()` 在模型调用外包了一层错误处理，和 LangChain wrap-style hook 的思路相似；`RecoveryState` 集中保存恢复过程中的状态。

🔴 **已验证理解**：二者都采用 wrapper 思路，在真正调用前后加入统一控制逻辑。

当前 `with_retry()` 是普通 Python 高阶函数，不是 LangChain middleware。`RecoveryState` 只保存一次 `agent_loop()` 中需要跨模型轮次共享的主要状态；`max_tokens`、单次 `attempt`、累计耗时和完整重试历史仍存放在其他位置或尚未实现。

## 三、当前代码中发现的边界

1. `lambda mt=max_tokens, mdl=state.current_model` 会提前捕获模型名称。`with_retry()` 修改 `state.current_model` 后，当前这批重试仍可能继续使用旧模型，因此 fallback 状态变化不等于真实请求已经切换。
2. 切换 fallback 前没有判断当前是否已经位于 fallback，后续 529 可能重复执行并记录同一次切换。
3. 429 分支没有清零 `consecutive_529`，所以当前计数不一定是严格连续的 529。
4. Anthropic Python SDK 自身也有默认重试；应用层再包十次重试会形成叠加，需要统一最大次数、累计等待和截止时间。
5. `is_prompt_too_long_error()` 通过异常名称和字符串匹配分类，教学上直观，但生产实现应优先使用 SDK 的异常类型、HTTP 状态和结构化错误码。
6. 当前 Tool 执行没有进入统一恢复策略。有副作用 Tool 如果“执行成功但响应丢失”，不能直接再次执行，必须通过幂等键或业务状态查询恢复。

## 四、恢复控制流伪代码

```text
初始化一次 Run 的恢复状态

while Run 未结束:
    尝试调用模型:
        如果是 429/529:
            在总次数和总时间预算内退避
            必要时选择备用模型
            重新调用

    如果是 prompt_too_long:
        如果尚未紧急压缩:
            在协议安全切点压缩上下文
            回到循环开头
        否则终止

    如果是其他未分类异常:
        记录并终止

    如果 stop_reason 是 max_tokens:
        如果尚未提高输出预算:
            提高额度并重新生成
        否则在续写次数预算内保存截断内容并续写

    如果 stop_reason 是 tool_use:
        校验并执行 Tool，保存配对结果，继续循环
    否则返回完整结果
```

## 五、代码映射

| 责任 | 当前实现 |
| --- | --- |
| 跨轮次恢复状态 | `RecoveryState` |
| 退避时间 | `retry_delay()` |
| 429/529 重试 | `with_retry()` |
| 上下文超限识别 | `is_prompt_too_long_error()` |
| 教学版紧急裁剪 | `reactive_compact()` |
| 三条路径的总编排 | `agent_loop()` |

## 六、掌握状态

### 已形成基础

- 能区分 API 异常与正常响应中的 `stop_reason`；
- 能解释三条恢复路径为何需要不同动作；
- 能解释指数退避和随机抖动的目的；
- 能沿 `continue` 追踪恢复后的控制流；
- 能发现 Tool 消息配对和 fallback 状态的代码问题；
- 能区分普通 wrapper 与框架 middleware。

### 基础验收结论

- 已能从错误性质判断“原样重试、改变请求后重试或终止”；
- 已能区分 `max_tokens` 停止原因与 `context_length_exceeded` 异常；
- 已能说明两条恢复路径对 messages 的不同影响；
- fallback 调用中的 lambda 默认参数捕获暂缓学习，不作为本章核心验收项；
- 副作用 Tool 的幂等恢复属于后续生产级专题。

## 七、小测结果与纠偏

### 小测 1：max_tokens 与 context_length_exceeded

我的回答：`max_tokens` 是正常响应，恢复时调整 LLM 入参 `max_tokens`；`context_length_exceeded` 是异常，需要紧急压缩。当前 case 中，第一次处理 `max_tokens` 不影响已有 messages，而 context 超限恢复会压缩 messages，造成信息损失。

🔴 **已验证理解**：两类结果的性质与第一次恢复动作判断正确。`max_tokens` 首次升级时没有把截断响应追加到 messages，因此 messages 不变；`context_length_exceeded` 会通过切片赋值原地替换 messages。

边界补充：第一次提高输出预算后如果仍然 `max_tokens`，代码会把截断输出和续写提示追加到 messages，此时 messages 会变化。当前教学版 reactive compact 会直接丢弃较早消息；生产方案虽然也通常是有损压缩，但应保存任务状态、关键事实、Tool 配对和副作用凭证，将不可控损失降到可验证范围。

### 小测 2：fallback 状态与真实调用

我的原始回答：第三次 529 后 `state.current_model` 变成默认模型，第四次实际使用 fallback。

该回答混淆了“状态中保存的模型”和“lambda 已经捕获的模型参数”。

🔴 **已验证理解**：第三次 529 后，`state.current_model` 被赋值为 `FALLBACK_MODEL`；但当前 lambda 在创建时已经把当时的主模型保存到默认参数 `mdl`，第四次调用仍然使用主模型。

```text
创建 lambda 时：mdl = PRIMARY_MODEL
第三次 529 后：state.current_model = FALLBACK_MODEL
第四次 fn()：model = mdl = PRIMARY_MODEL
```

状态变化不会自动传播到已经复制或捕获的变量。只有每次调用时重新读取 `state.current_model`，真实请求才会跟随状态切换。

学习决策：这一问题主要验证 Python 默认参数捕获语义，而不是错误恢复的核心心智模型。当前选择暂缓，不要求继续复述，也不影响 `s11` 基础章节完成；以后实际修改 fallback 代码时再结合最小 Python 示例学习。

### 用户故事：fallback 模型也失败

已确认的基础成功链路：

```text
A 529 → A 529 → A 529 → 切换 B → B 200 → 返回结果
```

如果 fallback B 也失败，Harness 仍然按照错误类型和剩余恢复预算处理，而不是无限切换模型：

```text
B 529 → 退避后重试 B → 在剩余预算内成功，或预算耗尽后终止
B 429 → 按 Retry-After/退避等待 → 重试 B，或预算耗尽后终止
B prompt_too_long → 紧急压缩一次 → 重试 B，仍超限则终止
B max_tokens → 提高输出预算或续写 → 超过续写上限后终止
B 401/403/参数错误 → 等待不会自愈，直接终止并报告配置或权限问题
B 200 但结果不符合任务契约 → 进入结果校验、降级回答或人工接管，不能把 HTTP 成功当作任务成功
```

当前教学实现没有第三个模型 C。A 切换到 B 后，如果 B 的瞬时错误一直持续，最终会耗尽同一次 `with_retry()` 的总尝试预算，由外层记录错误并结束当前 `agent_loop()`。

我的最终理解：B 已经是最后的兜底，不能无限重试；系统必须允许最终失败，因为任何代码和外部服务都不可能保证所有请求必然成功。

🔴 **已验证理解**：可靠性设计不是保证永不失败，而是让成功、重试、降级和最终失败都有明确边界；预算耗尽后应停止自动恢复，保留可诊断信息并向用户提供清晰的失败或后续处理方式。

## 八、暂缓的生产级主题

- 生产级 reactive compact 的触发、协议安全切点、摘要状态契约与真实项目对比，见 [`W-2026-012`](../specs/work-pool/W-2026-012-study-production-reactive-context-compaction.md)；
- SDK 与应用层重试策略叠加后的总预算；
- 流式响应中断和部分内容恢复；
- fallback 模型的能力、Tool Schema 和输出兼容性；
- Tool 幂等键、操作状态核对与响应丢失恢复；
- 协议安全的摘要、Checkpoint 和恢复重放；
- Retry Trace、错误分类指标、告警和成本治理。
