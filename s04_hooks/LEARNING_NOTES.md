# s04 Hooks 学习笔记

> 学习进度：已完成（D1 核心理论与代码阅读验收通过）。LangChain 最小实验和生产项目调研属于后续巩固，不阻塞本章结业。

## 一、本章当前核心结论

s03 把权限判断直接写在 Agent Loop 中；s04 保留原有工具执行流程，但把权限、日志、输出告警等横切逻辑注册为 Hook，并在主流程的生命周期扩展点统一触发。

Hook 的核心价值不是增加新的执行能力，而是：

- 把权限、日志、审计、上下文补充等逻辑从核心循环中拆出；
- 允许新增扩展行为时少改或不改 Agent Loop；
- 让扩展逻辑围绕明确的生命周期注册和执行；
- 通过 Hook 返回值契约决定是否允许扩展逻辑影响主流程。

## 二、我的原始理解

1. s04 与上一章很像，主要是在各个环节增加额外的中间处理流程。
2. Hook 在程序开始运行 Agent Loop 前注册，用于整个 LLM 对话生命周期。
3. Hook 常对应生命周期过程，例如 LLM 调用前后、Tool Call 前后、追加 Message 前后。
4. Pre Hook 常用于保护、权限和预处理；Post Hook 常用于修饰、补充和记录。
5. Hook 注册方式偏声明式：声明某个生命周期应该执行哪些回调。
6. 插件式产品通常提供固定生命周期和固定参数接口；业务开发者只注册插件，不需要手动书写触发时机。
7. 在代码中显式触发 Hook 的定制能力更强；固定插件接口牺牲一部分自由度，换取稳定和兼容。
8. LangChain 的 Middleware 与 Hook 很像，都是夹在核心执行流程中的扩展流水线。

## 三、已经理解正确的部分

### 3.1 Hook 用于拆分横切逻辑

🔴 **已验证理解**：s04 把 s03 中硬编码的权限判断迁移成 `PreToolUse` Hook，使 Agent Loop 更精炼，并用相同机制承载日志、输出告警等扩展行为。

### 3.2 Pre 与 Post 的常见职责

🔴 **已验证理解**：Pre Hook 通常负责“执行前是否允许、需要怎样准备”，例如权限、参数校验、输入标准化、脱敏和上下文补充。

🔴 **已验证理解**：Post Hook 通常负责“执行后怎样处理、记录和补充”，例如日志、指标、审计、输出截断和状态更新。

这只是常见职责划分，不是强制规则。Post Hook 是否可以替换结果、要求重试或停止流程，取决于主流程是否消费它的返回值。

### 3.3 插件式生命周期与显式触发

🔴 **已验证理解**：成熟插件产品通常让业务开发者只声明或注册 Hook；框架或 Runtime 在内部生命周期点负责分发事件。

🔴 **已验证理解**：自定义显式 Hook 可以自由决定事件粒度、参数和返回语义；固定插件接口则主动限制自由度，以换取类型约束、兼容性、可测试性和第三方生态。

需要注意：自定义 Hook 一旦被多个模块或团队依赖，也会成为需要维护兼容性的公共接口。

## 四、需要校准的边界

### 4.1 Hook 不是独立 Workflow

原始理解中的“各个环节增加额外的中间 workflow”方向正确，但 Hook 通常不拥有完整主流程。

🔴 **校准后表述**：Hook 是挂载在既有 Workflow 生命周期扩展点上的回调，用来执行横切逻辑；主 Workflow 仍由 Agent Loop 控制。

### 4.2 Hook 不会自动感知所有生命周期

Hook 只有在程序显式调用 `trigger_hooks()` 的地方才会触发。当前教学代码实现了：

```text
用户输入
  ↓ UserPromptSubmit
调用 LLM
  ↓
产生 tool_use
  ↓ PreToolUse
执行 Tool
  ↓ PostToolUse
再次调用 LLM
  ↓
不再调用 Tool
  ↓ Stop
```

当前代码没有 `PostLLMResponse`，也没有在每次 `messages.append()` 前执行的通用 Hook。`Stop` 只在模型不再请求工具、Agent Loop 准备结束时触发，不能等同于每次 LLM 响应后的 Hook。

### 4.3 “非空返回”不等于“发生错误”

我的回答：

> `permission_hook` 返回 `"Permission denied"` 后，`log_hook` 不会执行。当前 Hook 只有返回空值时才继续；任何失败的 Hook 都代表这个生命周期有错误，继续执行意义不大。

其中第一句正确，原因是 `trigger_hooks()` 遇到第一个非 `None` 返回值就立即 `return`，后面的 Hook 不会执行。

需要校准的是：非 `None` 不一定代表“错误”，它也可能是阻止、替换、重试、等待审批等控制信号。是否继续执行后续 Hook 也是契约选择。例如被拒绝的 Tool Call 仍然可能需要审计日志，因此“后续 Hook 没有意义”不能作为通用规则。

🔴 **校准后表述**：当前教学实现把任意非 `None` 返回值解释为阻断信号，并采用 first-result-wins 的短路策略；因此 `permission_hook` 阻断后，随后注册的 `log_hook` 不会执行。这是本项目的简化契约，不是所有 Hook 系统的通用规则。

### 4.4 Post Hook 当前不能修改 Tool Result

`PreToolUse` 的返回值由 Agent Loop 保存为 `blocked` 并参与控制流，因此可以阻止工具执行。

`PostToolUse` 的返回值没有被 Agent Loop 接收，最终追加到 `tool_result` 的仍是原始 `output`。因此当前 `large_output_hook` 只能打印警告，不能真正截断或替换返回给 LLM 的内容。

## 五、当前代码的对象与职责

| 对象 | 当前职责 |
| --- | --- |
| `HOOKS` | 保存事件名到回调列表的映射 |
| `register_hook()` | 按注册顺序把回调加入指定事件 |
| `trigger_hooks()` | 在主流程到达生命周期点时依次执行回调，并在首个非 `None` 结果处短路 |
| `permission_hook()` | `PreToolUse` 权限检查和人工确认 |
| `log_hook()` | `PreToolUse` 工具调用日志 |
| `large_output_hook()` | `PostToolUse` 大输出告警 |
| `context_inject_hook()` | `UserPromptSubmit` 阶段输出当前工作目录信息 |
| `summary_hook()` | `Stop` 阶段统计工具结果数量 |

注册、触发和执行是三件不同的事：

1. `register_hook()` 建立事件与回调的关系；
2. `trigger_hooks()` 表示主流程抵达生命周期扩展点；
3. 具体 Hook callback 执行权限、日志或告警逻辑。

## 六、Hook、Callback 与 Middleware

### 6.1 通用区别

- **Callback**：偏向收到事件通知，常用于日志、Trace、Token 统计等观测行为。
- **Hook**：强调生命周期扩展点；是否能改变流程取决于 Hook 契约。
- **Middleware**：强调可组合的处理链，通常可以通过 `handler` 或 `next` 决定是否继续、重试或替换结果。

🔴 **校准后表述**：Middleware 和 Hook 功能相似，但不是同义词。Middleware 可以提供多个生命周期 Hook；其中能够包裹下一层调用的 Wrap-style Hook，比普通事件回调拥有更明确的流程控制权。

### 6.2 LangChain 当前对应关系

截至 2026-08-27，LangChain Agent Middleware 提供：

- Node-style Hooks：`before_agent`、`before_model`、`after_model`、`after_agent`；
- Wrap-style Hooks：`wrap_model_call`、`wrap_tool_call`。

Node-style Hook 更接近当前教学代码的生命周期通知；Wrap-style Hook 接收下一层 `handler`，可以修改请求、重试、拦截或替换结果，更接近典型中间件。

LangChain 还保留独立 Callback 系统，主要用于模型、工具和链路的观测事件。学习时不应把 Callback、Hook、Middleware 三者完全画等号。

参考资料：

- [LangChain Agent Middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [LangChain Models 与 Callback](https://docs.langchain.com/oss/python/langchain/models)

更完整的框架扩展笔记见：[LangChain 的 Hook 类型学习](./LangChain%20的%20Hook%20类型学习.md)。

## 七、后续巩固的工程边界

1. 多个 Hook 的注册顺序、短路策略和结果合并策略；
2. Hook 抛出异常时采用 fail-open 还是 fail-closed；
3. Hook 的超时、同步/异步执行和取消；
4. Hook 是否允许修改输入对象，以及修改如何传给下一阶段；
5. Post Hook 如何安全地转换输出或停止后续执行；
6. Stop Hook 如何避免反复阻止结束而形成无限循环；
7. 权限 Hook 与服务端授权、工作区限制、操作系统权限和沙箱的边界。

以上内容属于后续工程化深化，不再作为本章基础结业的前置条件。

## 八、本章验收结论

- 已掌握：为什么引入 Hook、Pre/Post 常见用途、注册与触发分层、显式 Hook 与插件接口的取舍。
- 已掌握：Hook、Callback、Middleware 的关系，以及 LangChain Node-style / Wrap-style Hook 的区别。
- 已完成校准：非 `None` 不天然等于错误、短路不是通用策略、`can_jump_to` 只是能力声明、Node-style Hook 是节点而不是连线。
- 已能映射真实调用链：`UserPromptSubmit`、`PreToolUse`、`PostToolUse`、`Stop` 的触发位置和职责。
- 后续可选实验：验证 Post Hook 输出修改、异常与短路策略，以及 LangChain Middleware 的最小运行示例。
- 最终结论：第四章 D1 核心学习已完成，可以进入第五章；生产级 Hook 调研已进入 Work Pool，待基础章节结束后再启动。
