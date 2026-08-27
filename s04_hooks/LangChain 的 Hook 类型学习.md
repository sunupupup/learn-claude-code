# LangChain 的 Hook 类型学习

> 学习日期：2026-08-27
> 定位：作为 `s04_hooks` 的框架扩展阅读，重点建立 Hook / Middleware 的心智模型，不要求记忆 LangChain API。

## 一、先给出结论

LangChain 把 Agent 生命周期扩展机制统一称为 **Middleware**。一个 Middleware 可以提供多个 Hook；这些 Hook 又分成两类：

- **Node-style Hook**：在 Agent 图中的固定生命周期点插入一个执行节点；
- **Wrap-style Hook**：包裹已有的 Model 或 Tool 调用，通过 `handler` 控制下一层是否、何时、以什么参数执行。

🔴 **已验证理解**：Node-style 仍是一个插入的执行节点；Wrap-style 则包裹已有的 Model / Tool 节点。

需要再精确一点：Node-style 不是“两点之间的连线”。在图模型中，Hook 本身是节点，连线是节点之间的路由关系；当 Hook 返回 `jump_to` 时，才是在改变下一步走哪条路径。

## 二、Hook、Callback 与 Middleware

| 概念 | 主要关注点 | 对控制流的典型影响 |
| --- | --- | --- |
| Callback | 事件通知与观测 | 通常不改变主流程，用于日志、Trace、Token 统计 |
| Hook | 固定生命周期扩展点 | 取决于契约，可以只观测，也可以修改状态或阻断 |
| Middleware | 可组合的中间处理层 | 通常可以修改请求、调用下一层、重试、拦截或替换结果 |

它们不是互斥概念：LangChain 的 Middleware 通过 Hook 暴露扩展点，而其中某些 Hook 也可以只承担 Callback 式的观测职责。

🔴 **已验证理解**：把 LangChain Middleware 理解成 Agent 调用流水线中的“中间件”是合理的。它与 Hook 功能相近，但 Middleware 更强调组合和控制下一层调用，Hook 更强调生命周期扩展点。

## 三、Node-style Hook

LangChain 当前提供四个主要 Node-style 生命周期：

| Hook | 调用范围 | 常见用途 |
| --- | --- | --- |
| `before_agent` | 一次 Agent Run 开始前 | 初始化状态、注入整次运行都需要的上下文 |
| `before_model` | 每次 Model Call 前 | 修改状态、调用次数限制、模型前校验和日志 |
| `after_model` | 每次 Model Response 后 | 记录响应、更新计数、检查模型输出 |
| `after_agent` | 一次 Agent Run 完成前 | 汇总、清理、记录最终运行结果 |

### 3.1 `before_agent` 和 `before_model` 为什么不合并

它们看起来都发生在“模型之前”，但作用域和调用次数不同：

```text
一次 Agent Run
  before_agent                 只执行一次
  ├─ before_model → model      可能执行多次
  ├─ tools
  ├─ before_model → model
  └─ after_agent               只执行一次
```

- `before_agent` 面向整个 Run；
- `before_model` 面向一次具体的 Model Call。

如果把两者合并，初始化逻辑可能在 Agent 循环中重复执行，模型级校验也无法清楚表达“每次调用都要检查”。因此拆细不是形式主义，而是在区分 Session / Run / Model Call 等不同作用域。

这四个名称是 LangChain 的框架设计，不是所有 Agent 生态必须遵守的“四个标准节点”。不同系统还可能暴露 Session、Turn、Tool、Memory、Human-in-the-loop、Checkpoint 等生命周期。

### 3.2 `state` 与 `runtime`

典型签名如下：

```python
@before_model
def log_before_model(
    state: AgentState,
    runtime: Runtime,
) -> dict[str, Any] | None:
    print(len(state["messages"]))
    return None
```

- `state`：当前 Agent 图的持久状态快照，至少常见 `messages`，也可以通过自定义 State Schema 增加调用次数、用户 ID 等字段；
- `runtime`：本次运行的运行时环境，可承载调用上下文、依赖、Store 等不适合直接混入消息状态的信息；
- 返回 `dict`：表示状态更新，框架通过图的 reducer 合并；
- 返回 `None`：表示这次 Hook 不更新状态，也不改变路由。

框架约束的是参数位置、类型和返回契约，而不是变量必须叫 `state`、`runtime`。改变量名通常不影响 Python 调用，但保留官方命名更易读，类型也更容易检查。

Hook 在注册到 Agent 后是全局配置的一部分，但“全局”只表示该 Agent 实例后续每次运行都会使用它，不表示多个 Agent 实例或整个进程自动共享同一份 `state`。

### 3.3 `can_jump_to` 会不会中断

```python
@before_model(can_jump_to=["end"])
def check_message_limit(state: AgentState, runtime: Runtime):
    if len(state["messages"]) >= 50:
        return {
            "messages": [AIMessage("Conversation limit reached.")],
            "jump_to": "end",
        }
    return None
```

`can_jump_to=["end"]` 本身不会中断。它是 Hook 的**能力声明**：告诉框架这个节点允许返回哪些跳转目标。

真正改变控制流的是运行时返回：

```python
{"jump_to": "end"}
```

当前文档列出的目标包括：

- `end`：提前走向 Agent 结束阶段；
- `model`：跳到 Model 节点或第一段 `before_model` 链；
- `tools`：跳到 Tools 节点。

因此更准确的说法是：

```text
can_jump_to = 静态声明“允许跳到哪里”
jump_to     = 本次运行实际要求“下一步跳到哪里”
```

跳转是一种改道或提前结束，不等于抛异常；是否算“中断”要看目标。跳到 `end` 属于提前结束当前 Agent 主循环，但仍可能继续执行 `after_agent` 等收尾阶段。

## 四、Wrap-style Hook

典型模型包装器：

```python
@wrap_model_call
def retry_model(request: ModelRequest, handler):
    for attempt in range(3):
        try:
            return handler(request)
        except Exception:
            if attempt == 2:
                raise
```

这里：

- `request` 是原本准备传给下一层 Model 节点的结构化请求，不是 HTTP 原始请求；
- `handler` 是“继续执行下一层”的函数；
- 直接调用一次 `handler(request)`，表示正常放行；
- 修改 request 后调用，表示改写请求；
- 不调用 handler 而直接返回，表示拦截或替换；
- 多次调用 handler，常用于重试，但必须考虑费用、时延和副作用。

这就是高阶函数和洋葱模型：外层 Middleware 在调用前后都拥有控制权。

LangChain 当前最主要的两个 Wrap-style Hook 是：

- `wrap_model_call`：修改模型请求、动态选择模型或工具、重试、缓存、替换响应；
- `wrap_tool_call`：权限和参数检查、工具错误转换、重试、替换工具结果。

🔴 **已验证理解**：Wrap-style 面向 Workflow 中已有的 Model / Tool 关键节点进行包装。理论上任何有明确输入、输出和调用边界的函数都可以使用这种模式；但要接入 LangChain 的 Middleware 装饰器，必须是框架已暴露的扩展点。任意业务函数需要自己写 wrapper，或把它建模成自定义 LangGraph 节点。

Human-in-the-loop、Memory、Checkpoint 等也是 Agent 的关键步骤或能力，但不代表它们必然都有同名 `wrap_*` Hook；应以框架实际公开的生命周期和扩展 API 为准。

## 五、Hook 链真正依赖的是契约

Hook 的行为不能只靠 `canBeParallel`、`shouldBeBlocked` 两个布尔值表达。一个可生产使用的 Hook 系统通常需要四组契约共同决定行为：

| 契约 | 需要回答的问题 |
| --- | --- |
| 调度契约 | 串行还是并行？顺序如何？是否有优先级和依赖？ |
| 决策契约 | `allow`、`deny`、`modify`、`retry`、`jump`、`defer` 如何表达？ |
| 合并契约 | 多个 Hook 的状态更新、输出和冲突怎样合并？谁覆盖谁？ |
| 失败契约 | 超时或异常时 fail-open 还是 fail-closed？是否隔离、降级或重试？ |

常见策略是：

| Hook 类型 | 常见执行策略 |
| --- | --- |
| 权限、保护型 | `deny-overrides`；任意拒绝都可以阻止危险操作，同时审计 Hook 仍应有独立保障 |
| 输入/输出转换型 | 串行管道；前一个输出成为后一个输入，冲突顺序必须稳定 |
| 日志、指标、审计型 | 尽量全部执行或安全并行；单个观测 Hook 失败不应轻易拖垮业务 |

短路只是策略之一：

- 权限检查适合遇到拒绝后停止业务执行；
- 转换链可能需要继续执行全部转换器；
- 审计和日志通常不应该因为前一个 Hook 返回结果就被跳过；
- 一个系统还可能“停止同类 Hook，但始终执行 finally / audit Hook”。

所以 `s04_hooks` 的“首个非 `None` 结果立即返回”只是教学版的 `first-result-wins` 契约，不能直接推广为生产标准。

## 六、映射回本章代码

| 本章事件 | 当前职责 | LangChain 中较接近的位置 |
| --- | --- | --- |
| `UserPromptSubmit` | 追加上下文 | `before_agent` 或模型前的状态 / Prompt 处理，取决于作用域 |
| `PreToolUse` | 权限、参数检查、日志 | `wrap_tool_call` 的执行前半段 |
| `PostToolUse` | 输出告警、日志、指标 | `wrap_tool_call` 的执行后半段 |
| `Stop` | 汇总一次运行 | `after_agent` |

这里是语义上的近似映射，不是一一对应的 API 翻译。本章 `Stop` 只在模型不再请求工具、循环准备结束时触发；它常用于：

- 汇总本次 Run 的工具调用、Token、费用和耗时；
- 写入审计、Trace 或会话摘要；
- 刷新缓存、释放 Run 级资源；
- 在框架允许时补充最终状态。

不建议在 Stop 阶段随意重新启动 Agent 或反复阻止结束，否则容易产生循环和重复副作用。

## 七、学习结论

🔴 **已验证理解**：本章的目的就是把上一章写在主循环中的安全、权限和日志等横切逻辑抽成生命周期 Hook，学习 Hook 的注册、触发、输入输出契约，以及 Pre / Post 的常见使用场景。

到这里需要掌握的不是 LangChain 装饰器名称，而是以下判断方法：

1. 这个 Hook 属于哪个作用域：Run、Model Call 还是 Tool Call？
2. 它只是观察，还是允许修改状态和控制流？
3. 多个 Hook 怎样排序、合并和失败隔离？
4. 权限 Hook 是否只是体验层，真正授权是否仍由服务端和沙箱兜底？
5. 重试、替换和 Post 处理是否会造成费用、重复副作用或审计缺口？

下一步不需要系统学习整个 LangChain。做一个最小 Middleware 实验，再到真实的小型 Agent 项目中追踪注册点、触发点和返回值如何影响控制流，收益更高。对应任务已放入 [Work Pool](../specs/work-pool/W-2026-001-study-agent-hook-production-practices.md)。

## 参考资料

- [LangChain：Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [LangChain：Models 与 Callback](https://docs.langchain.com/oss/python/langchain/models)
