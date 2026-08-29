# s05 TodoWrite 学习笔记

> 学习进度：核心机制已理解。已完成 TodoWrite、Plan-and-Execute、Run 生命周期、Reminder、Tool Input Schema 与产品级 Plan mode 的边界校准；尚待完成一次运行实验和本章最终伪代码验收。

## 一、本章核心结论

s05 在原有 Agent Loop 上新增一个 `todo_write` 工具，把模型原本只存在于上下文中的计划，外化为 Harness 能保存和展示的显式状态。

`todo_write` 不增加读取文件、修改代码或运行命令等执行能力。它增加的是规划和进度跟踪能力：模型可以先列出步骤，再通过后续 Tool Call 提交新的完整 TODO 列表，更新每一步的状态。

当前实现属于 **Plan-and-Execute（规划后执行）风格的最小教学实现**，但不是完整的规划状态机，也不能直接等同于产品级 Plan mode。

## 二、我的原始理解

1. 这是一个 planning Agent 的最小示例：先计划要做几件事，再循环执行并更新计划状态。
2. Plan-and-Execute 是当前 Agent 系统中常见的一类设计模式。
3. 每个任务都由 LLM 决定是否发出 Tool Call；Harness 执行后把结果返回给 LLM，LLM 再决定是否更新 TODO 状态。
4. 连续三轮没有更新 TODO 的限制不是退出上限，而是提醒 LLM 更新计划。
5. 一次 Agent Run 中，只要模型不再 Tool Call，本次运行就结束。
6. `todos` 是一个对象数组：数组中的每一项都是包含 `content` 和 `status` 的 TODO 对象。
7. Codex Plan mode 的核心可能是“先不要修改代码，先写计划文件”。

## 三、已经理解正确的部分

### 3.1 规划状态由模型主动维护

🔴 **已验证理解**：LLM 负责判断当前应该调用哪个工具；Harness 负责校验、执行 Tool Call 并返回 Tool Result。LLM 看见结果后，可以再次调用 `todo_write`，传入更新后的完整 TODO 列表。

模型并不直接调用 Python 函数，真实边界是：

```text
LLM 生成结构化 Tool Call
  ↓
Harness 校验并分发给 TOOL_HANDLERS
  ↓
工具执行并返回 Tool Result
  ↓
Harness 把结果追加到 messages
  ↓
LLM 根据新上下文决定下一步
```

### 3.2 Plan-and-Execute 的直观机制

🔴 **已验证理解**：Plan-and-Execute 的核心是先形成计划，再逐步执行，并在环境结果发生变化时更新或重新规划。

s05 已具备最小的“计划—执行—更新”形态，但 Planner 和 Executor 没有拆成两个独立对象，仍由同一个模型在同一个 Agent Loop 中决定。

### 3.3 Tool Input Schema 的嵌套结构

🔴 **已验证理解**：完整工具输入是一个 object；其中 `todos` 属性是 array；每个 array item 又是一个 object，包含必填的 `content` 和 `status`。

```text
tool input: object
└── todos: array
    └── item: object
        ├── content: string
        └── status: enum(pending, in_progress, completed)
```

Schema 描述模型应该生成的参数形状；`_normalize_todos()` 是工具执行前的 Runtime 校验。不能因为向模型提供了 Schema，就假设所有输入在程序端天然可信。

### 3.4 Reminder 不是退出条件

🔴 **已验证理解**：`nag` 在这里表示反复提醒或催促。连续三个产生 `tool_use` 的模型轮次没有调用 `todo_write` 时，Harness 会在下一次模型调用前追加一条 `<reminder>` 用户消息。

`rounds_since_todo` 统计的是产生 Tool Call 的模型轮次，不是工具总调用次数；同一响应中即使包含多个工具，也只在进入该轮结果处理前增加一次。

### 3.5 一次 Run 的结束条件

🔴 **已验证理解**：当前 `agent_loop()` 中，只要模型返回的 `stop_reason` 不再是 `tool_use`，并且 `Stop` Hook 没有要求继续，本次 Run 就会结束。

这不等于整个 Python 进程结束：外层 REPL 仍会等待下一次用户输入，并使用保留下来的会话历史启动新的 Run。

## 四、需要校准的边界

### 4.1 当前实现没有轮次上限

当前代码中的 `max_tokens=8000` 是单次模型响应的输出 Token 上限，不是 Agent Loop 的最大轮次。

`rounds_since_todo >= 3` 只负责注入 Reminder，也不是退出条件。如果模型持续调用任意工具，当前循环理论上可能一直运行。

生产实现仍需要由 Harness 强制提供：

- 最大步骤数；
- 总时间与单工具超时；
- Token 和费用预算；
- 取消与人工接管；
- 重复调用或无进展检测。

### 4.2 程序不会根据 TODO 自动推进或退出

`run_todo_write()` 中的 `for` 循环只读取 `status` 并渲染图标。真正的状态更新发生在：

```python
CURRENT_TODOS = todos
```

这是用模型本次提交的完整列表整体替换旧列表，而不是程序自动把某一项从 `in_progress` 改为 `completed`。

程序也不会检查：

- 是否只有一个任务处于 `in_progress`；
- 是否严格按列表顺序执行；
- 是否遗漏或偷偷删除了任务；
- 是否所有任务都已经 `completed`；
- TODO 全部完成后是否应该退出。

### 4.3 不更新 TODO 不一定造成无限循环

如果模型不更新 TODO，但停止调用工具，本次 Run 仍会结束。真正的无限循环风险是模型持续产生 Tool Call，而 Harness 没有最大步数、预算或无进展检测。

另一方面，即使 TODO 仍有 `pending` 项，模型只要不再调用工具，当前教学实现也会结束。

### 4.4 s05 不等于完整 Plan-and-Execute

完整的 Plan-and-Execute 实现通常还需要明确：

- 谁生成计划，谁执行计划；
- 是否强制先规划；
- 如何选择当前步骤；
- 如何判断步骤完成；
- 何时重新规划；
- 计划修改是否需要用户批准；
- 如何处理失败、回滚和部分完成。

s05 只提供了一个规划工具、进程内 TODO 状态、提示词引导和 Reminder，没有用程序强制上述规则。

### 4.5 Plan mode 不等于 plan 文件

🔴 **校准后表述**：产品级 Plan mode 的核心是把调研、澄清和规划阶段与实际修改阶段分开；计划是否写入 `plan.md`，只是可选的持久化方式，不是 Plan mode 的定义。

计划可以存在于对话、UI、任务状态或文件中。若产品需要强约束，还应在规划阶段限制写工具或要求人工批准，而不能只依靠一句“先不要改代码”的 Prompt。

## 五、当前代码的对象与职责

| 对象 | 当前职责 | 不负责什么 |
| --- | --- | --- |
| `SYSTEM` | 引导模型在多步骤任务前使用 `todo_write` | 不强制模型一定先规划 |
| `TOOLS` 中的 Schema | 描述 `todo_write` 的工具输入形状 | 不替代 Runtime 校验和业务约束 |
| `_normalize_todos()` | 校验数组、对象、必填字段和状态枚举 | 不校验任务顺序、唯一进行中项或完成真实性 |
| `run_todo_write()` | 整体替换内存 TODO，并渲染当前状态 | 不执行任务、不自动推进状态 |
| `CURRENT_TODOS` | 保存当前进程内的 TODO 列表 | 不持久化，进程退出后丢失 |
| `rounds_since_todo` | 记录距离上次 `todo_write` 的 Tool Call 轮次 | 不是最大轮次或完成判定 |
| Reminder | 把“更新 TODO”的提示重新放回模型上下文 | 不能强制服从，也不能阻止无限循环 |
| `agent_loop()` | 执行模型—工具—结果循环 | 不把 TODO 列表变成确定性工作流 |

## 六、关键流程伪代码

```text
收到用户输入
触发 UserPromptSubmit Hook

while True:
    if 连续 3 个 Tool Call 轮次没有调用 todo_write:
        向 messages 追加 Reminder
        清零提醒计数器

    response = 调用 LLM(messages, tools)
    保存 assistant response

    if response 不再请求工具:
        触发 Stop Hook
        if Stop Hook 要求继续:
            把要求追加到 messages
            continue
        结束本次 Run

    Tool Call 轮次计数 +1

    for 每个 Tool Call:
        触发 PreToolUse Hook
        if 被阻止:
            返回拒绝结果
            continue

        校验参数并执行对应 Tool Handler
        触发 PostToolUse Hook

        if 工具是 todo_write:
            用模型提交的完整列表替换 CURRENT_TODOS
            清零提醒计数器

        收集 Tool Result

    把全部 Tool Result 追加到 messages
```

## 七、仍需完成的验收

1. 运行一个至少包含三个步骤的真实任务，观察首次 Tool Call 是否为 `todo_write`。
2. 记录一次 TODO 从 `pending` 到 `in_progress` 再到 `completed` 的完整 Tool Call 参数。
3. 构造连续三轮不调用 `todo_write` 的场景，确认 Reminder 注入时机。
4. 解释为什么 Schema 合法不等于任务语义正确。
5. 独立写出带最大步骤数和“全部完成”检查的改进版伪代码，但暂不修改教程代码。

## 八、当前掌握状态

- 已掌握：TodoWrite 的目的、Plan-and-Execute 直观机制、嵌套 Tool Schema、模型与 Harness 的职责边界。
- 已掌握：Reminder 与退出条件、一次 Run 与整个交互进程的区别。
- 已校准：当前实现不会自动更新状态、不会检查全部完成、没有最大循环轮次。
- 待验证：真实运行轨迹、无进展场景以及带程序强制边界的改进伪代码。
- 后续专题：严格 JSON 输出、约束解码与后训练对照实验，见 [`W-2026-003`](../specs/work-pool/W-2026-003-study-strict-json-output-post-training.md)。

## 九、后续学习建议：严格 JSON 输出与后训练

### 9.1 当前操作建议

🔴 **已验证理解**：选择一个足够小的开放权重模型，亲自完成一次后训练，是理解 Base、Instruct、SFT、LoRA 和结构化输出边界的有效实践。

不建议把“古早、最基础的小模型”作为主实验。老模型可能同时带来旧 Tokenizer、弱指令跟随、训练配方落后和当前库兼容问题；实验失败后，很难判断问题来自数据、训练方法、模型容量还是工具链年代。

推荐按以下顺序学习和操作：

1. 先补齐 Token、Causal Language Model、Base Model、Instruct Model、SFT、LoRA 和 Constrained Decoding 的最小理论。
2. 选择当前仍受训练工具链支持、许可证清晰、规模足够小，并且同一家族同时提供 Base 与 Instruct 版本的开放权重模型。
3. 优先用小型 Instruct 模型建立 Prompt-only 基线，确认任务和 Eval 管线本身可以运行。
4. 在同一模型上使用 LoRA + SFT 训练窄任务 JSON 输出行为，不覆盖原始模型权重。
5. 加入约束解码，对比“模型更愿意遵循”与“生成过程被强制遵循”的区别。
6. 最后再使用同家族 Base 模型做 instruction tuning 对照，观察 Post-training 如何让 Base 获得指令跟随能力。
7. 始终保留程序端 JSON 解析、JSON Schema 校验、业务规则校验和授权；不能让模型权重代替确定性边界。

具体模型、精度、量化方式和训练参数暂不锁定。正式开始前，应先检查本机 GPU 型号、显存、内存、磁盘和可接受训练时间，再按当时的官方文档选择。

### 9.2 严格 JSON 的四层心智模型

```text
Prompt / Examples
    提高模型理解任务和格式的概率

Post-training（例如 SFT + LoRA）
    调整模型分布，提高原生格式遵循与任务能力

Constrained Decoding（约束解码）
    在生成阶段屏蔽不符合语法或 Schema 的 Token

Runtime Validation（运行时校验）
    对最终对象执行 JSON、Schema、业务规则和权限检查
```

需要始终区分三个质量层次：

1. **JSON 语法合法**：输出能够被 JSON Parser 解析；
2. **Schema 合法**：字段、类型、必填项和枚举满足约束；
3. **语义正确**：字段值真实表达了用户意图，并且业务操作安全。

SFT/LoRA 提高遵循概率，但不能单独提供严格保证；约束解码可以在其支持范围内限制结构，但不能保证字段语义正确；Runtime 和业务系统仍需采用 fail-closed 校验。

### 9.3 推荐的最小对照实验

在相同 Prompt、Schema、采样参数和冻结测试集上比较四组结果：

| 组别 | 模型权重 | 解码方式 | 主要目的 |
| --- | --- | --- | --- |
| B1 | 原始小型 Instruct | 普通生成 | 测量 Prompt-only 原生遵循率 |
| B2 | 原始小型 Instruct | 约束解码 | 测量不修改权重时的结构约束收益 |
| B3 | LoRA/SFT 后模型 | 普通生成 | 测量后训练带来的原生遵循和语义收益 |
| B4 | LoRA/SFT 后模型 | 约束解码 | 测量训练与结构约束组合后的结果 |

至少记录以下确定性指标：

- JSON parse rate；
- JSON Schema validation rate；
- required、enum 和 type 的分项通过率；
- 字段级语义准确率或 exact match；
- 正确拒绝率与 unsafe acceptance；
- 输出截断率；
- 延迟、Token、显存和训练成本。

详细数据设计、实验边界、启动条件和验收标准只在 [`W-2026-003：严格 JSON 输出与后训练对照实验`](../specs/work-pool/W-2026-003-study-strict-json-output-post-training.md) 中维护。启动该任务时，应先把 Work Pool 文件转换成 `specs/changes/C-*.md`，再安装依赖或下载模型。

### 9.4 后续阅读资料

以下资料已于 2026-08-29 核对；真正启动实验时仍需复查最新稳定版本：

- [Hugging Face TRL：SFT Trainer](https://huggingface.co/docs/trl/sft_trainer)：学习 prompt-completion 数据、completion-only loss、Assistant-only loss、PEFT/LoRA 和 Tool Calling 训练格式。
- [Hugging Face TRL：PEFT Integration](https://huggingface.co/docs/trl/peft_integration)：学习如何用 Adapter 做参数高效微调并保留原始模型。
- [Qwen3-0.6B 模型卡](https://huggingface.co/Qwen/Qwen3-0.6B)：一个小型开放权重候选及其 Base/Post-trained 关系；这里只作为候选，不提前锁定。
- [Generating Structured Outputs from Language Models / JSONSchemaBench](https://arxiv.org/abs/2501.10868)：理解约束解码在 Schema 覆盖、效率和生成质量上的评测方法。
- [JSONSchemaBench 官方仓库](https://github.com/guidance-ai/jsonschemabench)：查看 JSON Schema 测试集和约束解码框架对照方式。
- [When JSON Is Not Enough](https://arxiv.org/abs/2607.18261)：理解为什么 Schema 合法仍可能产生语义错误或不安全操作。
