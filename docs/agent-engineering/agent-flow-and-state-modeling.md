# Agent 流程与状态建模方法

这是一条跨章节、跨项目的 Agent 工程方法：

> 先画角色和调用链，再把关键节点落成状态、事件、数据和失败出口。

它适用于：

- 设计 Agent Loop；
- 设计 Tool、MCP、Subagent、审批和后台任务流程；
- 排查“调用了但没有生效”“状态丢失”“重试重复执行”等问题；
- 面试中用精简、专业的方式说明一个 Agent 系统如何工作。

## 一、先区分三种图

### 1. 调用链 / 时序图

回答“谁在什么顺序调用谁”：

~~~text
模型 -> Host -> MCP Client -> MCP Server -> 下游系统
~~~

它适合说明组件边界、请求方向和成功路径。

### 2. 状态机

回答“系统当前处于什么状态，什么事件会让它迁移”：

~~~text
DISCONNECTED
  --connect--> CONNECTING
  --handshake_ok--> READY
  --tool_call--> EXECUTING
  --success--> READY
  --timeout--> DEGRADED
~~~

它必须包含状态、触发事件、前置条件、动作、下一状态和失败出口。

### 3. 数据流

回答“数据从哪里来，经过哪些处理，保存到哪里”：

~~~text
Tool definition
  -> MCP Client registry
  -> Host tool pool
  -> model request.tools
  -> model tool_use
  -> handler adapter
  -> MCP request
  -> tool_result
  -> next model context
~~~

实际设计时，三种图经常一起使用，但不能把它们当成同一种东西。

## 二、最小描述模板

面对一个新的 Agent 功能，先用下面六步写出主流程：

1. **触发**：用户、模型、定时器、后台任务还是外部事件触发？
2. **角色**：User、Model、Host、Tool、MCP Client、Server、下游系统分别负责什么？
3. **前置检查**：身份、权限、配置、依赖、幂等键和资源是否满足？
4. **执行**：哪个组件执行动作，哪个组件只转发或记录？
5. **状态和证据**：状态何时持久化，结果如何关联，什么能证明操作真的完成？
6. **失败出口**：超时、拒绝、断连、重试、取消、部分成功和未知结果如何处理？

可以先写成一行：

~~~text
触发 -> 前置检查 -> 状态持久化 -> 执行 -> 结果验证 -> 完成或恢复
~~~

这行是提纲，不是完整状态机。复杂流程必须继续展开分支和恢复路径。

## 三、Agent Loop 的通用状态模型

一个最小的 Agent 回合可以这样表示：

~~~text
IDLE
  -> MODEL_REQUEST
  -> MODEL_RESPONSE
      ├─ no tool_use -> DONE
      └─ tool_use
          -> PRE_TOOL_CHECK
          -> WAITING_APPROVAL（需要人工时）
          -> TOOL_EXECUTING
          -> TOOL_RESULT_PERSISTED
          -> MODEL_REQUEST
~~~

这里要区分：

- 模型输出了工具调用，不等于工具已经执行；
- Tool handler 返回结果，不等于下游业务已经完成；
- Agent 结束回答，不等于外部异步任务已经完成；
- 收到成功 HTTP 响应，不等于写操作的最终状态已被核对。

如果存在异步任务、审批或外部系统，通常还需要：

~~~text
PENDING
  -> APPROVED
  -> EXECUTING
  -> COMPLETED
  -> FAILED / CANCELED / TIMED_OUT / UNKNOWN
~~~

具体状态名可以变化，但每个状态都应有定义、进入条件、离开事件和恢复策略。

## 四、把 MCP 放进 Agent 流程

MCP 流程是 Agent Loop 内部的一段子流程，不等于完整 Agent 状态机。

对于 2025-11-25 生命周期，成功路径可以写成：

~~~text
模型提出 connect_mcp("docs")
  -> Host 找到已配置的 Server
  -> MCP Client 建立连接
  -> initialize
  -> notifications/initialized
  -> tools/list
  -> Host 保存并筛选 Tool definitions
  -> 下一轮 model request.tools 包含 MCP tools
  -> 模型提出 mcp__docs__search
  -> Host handler adapter
  -> MCP Client 发送 tools/call
  -> MCP Server 执行
  -> tool_result 回到 Agent Loop
~~~

这条链中至少有三个不同层次：

1. connect_mcp 是 Host 为模型提供的入口，不是 MCP 标准 method；
2. initialize、tools/list、tools/call 是 MCP 协议消息；
3. mcp__docs__search 是 Host 为避免名称冲突生成的本地工具名。

协议版本必须固定。2025-11-25 及更早生命周期使用 initialize/initialized 握手；更新版本可能采用不同的无状态流程，不能把某个版本的调用链写成永远不变的标准。

参考：

- [s19 MCP 学习笔记](../../s19_mcp_plugin/LEARNING_NOTES.md)
- [MCP 2025-11-25 Lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
- [MCP Architecture](https://modelcontextprotocol.io/specification/2025-06-18/architecture)

## 五、设计时必须补出的失败路径

成功路径精简，但生产设计必须同时列出失败出口：

~~~text
连接失败
  -> 配置错误 / 认证失败 / TLS 失败 / Server 不可达

initialize 失败
  -> 版本不兼容 / 能力不足 / 超时

tools/list 失败
  -> 重试 / 降级 / 不向模型暴露旧列表

tools/call 超时
  -> 不直接判断为业务失败
  -> 查询执行状态或进入 UNKNOWN

写操作响应丢失
  -> 使用幂等键查询或对账
  -> 禁止无条件盲重试
~~~

还要明确：

- 谁可以发起动作；
- 谁审批；
- 谁真正执行；
- 哪个状态是持久化事实；
- 哪个结果只是模型观察到的文本；
- 如何关联日志、Trace、请求 ID 和下游业务 ID。

## 六、面试中的精简表达

面试时可以用下面的顺序回答一个 Agent 设计题：

### 先说角色

> 模型负责决策，Host 负责编排、上下文和权限，Tool 或 MCP Client 负责执行适配，业务系统负责最终状态。

### 再说成功调用链

~~~text
用户请求
  -> Host 组装上下文和可用工具
  -> 模型选择动作
  -> Host 做权限和参数校验
  -> 执行工具或 MCP 调用
  -> 持久化结果并验证下游状态
  -> 把结果放回下一轮模型上下文
~~~

### 再说状态

> 我会把流程拆成 pending、approved、executing、completed、failed、unknown 等状态，并为每个状态定义进入条件、持久化字段和恢复路径。

### 最后说生产边界

> 对写操作补充幂等、超时、取消、重试、审计和对账；对异步任务补充查询、恢复和最终状态验证；对外部工具补充认证、授权、隔离和版本兼容。

这比只说“模型调用工具，工具返回结果”更专业，因为它同时说明了控制边界和失败后的行为。

## 七、证据和表达纪律

描述流程时，把结论分成三层：

| 层次 | 写法 |
| --- | --- |
| 已验证 | “在当前代码/运行记录中，A 调用 B，结果是 C” |
| 通用原理 | “通常可以把这类系统建模为……” |
| 待核验 | “该 SDK/厂商的真实行为需要固定版本后检查源码或运行证据” |

不要把以下内容混为一谈：

- 教学 Mock 的本地函数；
- MCP 协议规定的 method；
- 某个 Host 的命名和权限策略；
- 某个厂商 SDK 的生命周期封装；
- 模型提出的意图；
- 下游系统已经确认的业务事实。

## 八、什么时候这种方法最有价值

- 新功能设计：先发现缺少哪些状态和失败出口；
- 代码评审：检查实现是否遗漏状态持久化或权限边界；
- 故障排查：定位请求卡在哪个组件、哪个状态；
- 生产验收：为每条边和每个状态设计可观测证据；
- 面试表达：用一张简图和几个状态名快速说明系统，而不是堆砌框架名。

这是一种通用的工程表达方式，不是某个 Agent 框架专属的 API 或固定状态名称。
