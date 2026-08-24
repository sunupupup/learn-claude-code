# s02 学习手册：Tool Use

> 学习状态：进行中  
> 本章目标：理解工具声明、分发、校验、执行和结果回传的完整链路，并能区分 Client Tool、Server Tool、MCP Tool 与协议错误。

| 项目 | 路径 |
|---|---|
| 章节教程 | [`README.md`](README.md) |
| 章节代码 | [`code.py`](code.py) |
| 前置章节 | [`../s01_agent_loop/LEARNING_NOTES.md`](../s01_agent_loop/LEARNING_NOTES.md) |

## 一、本章核心结论

s01 已经建立最小 Agent Loop；s02 没有改变模型与工具之间的基本闭环，而是把单一 `bash` 扩展成多个专用工具，并用注册表完成分发。

```text
TOOLS 告诉模型“可以请求哪些工具”
        ↓
模型返回 tool_use(name, input, id)
        ↓
Harness 校验 name 和 input
        ↓
TOOL_HANDLERS 找到并执行本地函数
        ↓
Harness 构造 tool_result(tool_use_id, content, is_error)
        ↓
把 tool_result 放进 messages，再次调用模型
```

最重要的职责边界：

```text
模型只提出工具调用请求，不执行 Python 函数。
Harness 才负责校验、授权、执行、记录和回传结果。
```

## 二、我的原始理解

读完本章代码后，我的理解是：

1. `TOOLS` 会传给 LLM，告诉模型当前有哪些方法，以及每个方法的名称、描述、参数类型和参数描述等 metadata。
2. `TOOL_HANDLERS` 负责处理模型响应中的 `tool_call`/`tool_use`，读取工具名和参数，再通过 `TOOL_HANDLERS[tool_name](**args)` 调用真正的工具。

这条主线是正确的，已经抓住 s02 相对 s01 的核心变化。

## 三、理解校准

### 3.1 `TOOLS` 是模型可见的契约

`TOOLS` 不是函数实现，也不会让模型获得执行 Python 的能力。它只是告诉模型：

- 有哪些工具；
- 什么时候适合使用；
- 输入对象应包含哪些字段；
- 字段类型和必填项是什么。

```python
TOOLS = [
    {
        "name": "glob",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    }
]
```

模型根据这份契约生成：

```json
{
  "type": "tool_use",
  "id": "toolu_123",
  "name": "glob",
  "input": {"pattern": "**/*.py"}
}
```

### 3.2 `TOOL_HANDLERS` 是 Harness 的本地执行注册表

```python
TOOL_HANDLERS = {
    "glob": run_glob,
    "read_file": run_read,
}
```

它解决的是：收到模型请求后，本地程序应该调用哪个函数。

```python
handler = TOOL_HANDLERS.get(block.name)
output = handler(**block.input)
```

实际代码使用 `.get()`，而不是直接用 `TOOL_HANDLERS[block.name]`，这样可以显式处理未知工具名，而不是直接抛出 `KeyError`。

### 3.3 `tool_result` 是闭环中不能遗漏的一步

执行函数后，Harness 必须把结果送回模型：

```python
messages.append(
    {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            }
        ],
    }
)
```

否则模型只知道自己请求了工具，不知道工具是否成功以及返回了什么。

## 四、工具调用错误流程

### 4.1 当前代码演示的两类错误

#### 未知工具名

```text
block.name 不在 TOOL_HANDLERS
→ 不执行任何函数
→ 返回可用工具列表
→ is_error = true
```

模型通常只会从 `TOOLS` 中选择工具，但未知名称仍可能来自模型偏差、旧消息重放、工具列表动态变化，或者 `TOOLS` 与 `TOOL_HANDLERS` 维护不同步。

#### `glob` 参数错误

教学代码只为 `glob` 注册了校验器：

```text
{"pattern": "*.py"}  → 合法
{"pattern": 123}     → 类型错误
{}                     → 缺少必填参数
```

校验必须发生在 handler 之前。对于有副作用的工具，如果先执行再校验，拒绝已经没有意义。

### 4.2 `is_error` 如何回传给模型

`execute_tool()` 返回：

```python
(output, is_error)
```

发生错误时，Harness 构造：

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_123",
  "content": "Error: Invalid input for tool 'glob': 'pattern' must be a string",
  "is_error": true
}
```

然后把所有结果作为下一条 `role: "user"` 消息加入 `messages`。下一次调用 `client.messages.create()` 时，模型会看到错误内容，并决定修改参数、换工具、换方案或向用户说明失败。

要准确记住：

```text
is_error 不会让 API 自动重试。
它只是明确告诉模型“这个工具结果代表失败”。
```

### 4.3 `tool_use_id` 不能丢

一次响应可能包含多个工具调用，所以必须通过 ID 配对：

```text
tool_use.id == tool_result.tool_use_id
```

如果缺少某个结果、ID 不匹配或消息顺序错误，API 可能直接拒绝下一次请求。

## 五、完整错误分类

| 错误层 | 例子 | 谁处理 | 模型如何看到 |
|---|---|---|---|
| 调用/参数错误 | 未知工具、缺参数、类型错误 | 本地 Harness | Client `tool_result(is_error=true)` |
| Client Tool 执行错误 | 函数异常、文件不存在、业务 API 500 | 本地 Harness | Client `tool_result(is_error=true)` |
| Anthropic Server Tool 错误 | Web Search、Web Fetch、Code Execution 失败 | Anthropic/API | 对应的 server tool result block |
| Remote MCP Tool 错误 | 远程 MCP 服务调用失败 | MCP Server 与 Anthropic MCP Connector | `mcp_tool_result(is_error=true)` |
| 协议错误 | 漏结果、ID 错、消息顺序错 | 应用程序 | API 4xx；模型通常看不到 |
| 网络/API 错误 | 超时、429、鉴权失败、服务不可用 | SDK/应用程序 | 请求异常；应用决定是否重试或告知模型 |

### 5.1 Client Tool

Client Tool 由本地 Harness 执行。当前项目的 `bash`、`read_file`、`write_file`、`edit_file` 和 `glob` 都属于这一类。

```text
assistant: tool_use
user:      tool_result
```

### 5.2 Anthropic Server Tool

Web Search、Web Fetch 等 Server Tool 由 Anthropic 执行，通常在 assistant 响应中出现：

```text
server_tool_use
server-specific tool result
```

本地程序通常不需要为它们手写 `role=user + tool_result`。

### 5.3 Remote MCP Tool

使用 Anthropic MCP Connector 时，块类型是：

```text
mcp_tool_use
mcp_tool_result
```

远程 MCP 是服务端执行体系的一种，但不能把所有 Server Tool 都等同于 MCP Tool。如果本地自己运行 MCP Client，再把工具包装成 Client Tool，错误处理责任又会回到本地 Harness。

### 5.4 协议错误不是 `is_error`

以下问题通常在模型看到结果之前就会导致 API 请求失败：

- `tool_result` 没有紧跟对应的 assistant `tool_use`；
- 一次有多个 `tool_use`，但只返回部分结果；
- `tool_use_id` 不匹配；
- 在 `tool_result` 前放普通文本；
- 没有把完整 assistant 响应加入历史。

所以要区分：

```text
工具错误 → 作为 is_error 交给模型，模型可能自愈。
协议错误 → API 请求失败，由程序修复，模型通常看不到。
```

## 六、参数校验方案

模型看过 `input_schema`，仍不能完全代替本地运行时校验。模型输出、历史消息和外部输入都应该按不可信输入处理。

| 方式 | 适合场景 | 取舍 |
|---|---|---|
| 手写校验 | 教学、小工具、少量业务规则 | 流程直观；工具多时容易漏字段 |
| JSON Schema 校验 | `TOOLS.input_schema` 是权威契约、跨语言系统 | 可复用同一份 schema；Python 类型体验一般 |
| Pydantic | Python 服务、复杂嵌套参数、需要结构化错误 | 类型与错误信息好；应避免再手写第二份 schema |

### 6.1 当前章节为什么使用手写校验

本章目标是看清：

```text
声明 → 分发 → 校验 → 执行 → 回传
```

只为 `glob` 增加手写校验，不引入新依赖，可以避免 Pydantic 把核心 Agent Loop 隐藏在额外抽象下面。

### 6.2 生产环境一定需要 Pydantic 吗

不一定，但必须有可靠的运行时校验，并尽量保持单一事实来源：

- Python 项目可以让 Pydantic 模型成为权威定义，通过 `model_json_schema()` 生成模型使用的 JSON Schema；
- 跨语言系统可以把 JSON Schema 作为权威定义，各语言使用自己的运行时校验器；
- 不建议分别手写 Pydantic 模型和 `TOOLS.input_schema`，否则两份定义容易漂移。

Pydantic 只解决结构和值校验，不解决授权、危险副作用、幂等、超时和审计。

## 七、当前教学实现的边界

当前 `execute_tool()` 已处理：

- handler 不存在；
- `glob` 参数缺失或类型错误；
- `handler(**tool_input)` 抛出的未捕获异常；
- 错误结果的 `is_error: true` 标记。

仍有意省略或简化：

- 其他工具没有完整的 schema 运行时校验；
- 某些 `run_*` 函数在内部把异常转换成 `Error:` 字符串，外层无法可靠判断它是不是错误；
- 没有最大 Agent 轮数或单工具重试上限；
- 没有错误码、错误分类和结构化日志；
- 没有测试完整的多工具消息配对；
- 没有权限审批、幂等键或回滚机制。

生产实现不要依赖 `output.startswith("Error:")` 判断失败。更稳妥的方式是让 handler 抛出分类异常，或统一返回结构化的 `ToolExecutionResult`。

## 八、生产级扩展点

### 8.1 循环与重试预算

至少考虑：

```text
max_iterations
max_tool_retries
per_tool_timeout
token/cost budget
```

否则模型可能反复生成同一个错误调用并持续消耗 token。

### 8.2 错误分级

- 参数错误：通常让模型修正一次；
- 权限错误：请求用户批准或终止；
- 临时系统错误：按退避策略有限重试；
- 永久业务错误：换方案或向用户解释；
- 协议错误：记录并修复 Harness，不能假装是工具失败。

### 8.3 错误信息与日志分离

给模型的错误应可操作但不能泄密：

```text
给模型：错误类型、失败原因、允许的修正方向。
写日志：完整异常栈、耗时、工具名、tool_use_id、重试次数和版本。
```

不要把密钥、访问令牌、内部路径或完整异常栈塞进 `tool_result`。

### 8.4 Tool Result 也是不可信输入

网页、邮件、用户文件和第三方 API 返回值可能包含 Prompt Injection。应该把外部数据留在 `tool_result` 中，不要把它拼进 system prompt，也不要把工具结果里的文字自动当成高优先级指令。

### 8.5 多工具调用

一次响应中的每个 `tool_use` 都必须得到一个匹配结果。即使因为前一个步骤失败而决定不执行后续调用，也应该返回对应的错误结果：

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_456",
  "is_error": true,
  "content": "Not executed because the preceding operation failed."
}
```

### 8.6 注册一致性

生产程序可以在启动时检查：

```text
TOOLS 中的工具名
TOOL_HANDLERS 中的工具名
TOOL_VALIDATORS 中的工具名
```

这样能在启动阶段发现配置漂移，而不是等模型调用时才暴露未知工具。

### 8.7 Strict Tool Use 与 Tool Runner

当前 Claude 文档提供 `strict: true` 来减少工具名和输入 schema 错误，也提供 Beta Tool Runner 自动处理 Agent Loop、类型校验、异常包装与 `tool_result`。

本项目当前保留手写循环，因为它更适合学习协议和控制边界。等手写流程掌握后，可以再用 Tool Runner 重写一次，比较它隐藏了哪些细节。启用这些当前能力前还要核对 SDK 版本、模型支持和兼容网关能力。

## 九、建议实验

1. 直接调用 `execute_tool("missing_tool", {})`，观察未知工具错误。
2. 调用 `execute_tool("glob", {})`，观察缺少参数。
3. 调用 `execute_tool("glob", {"pattern": 123})`，观察类型错误。
4. 调用合法 `glob`，确认 `is_error` 为假。
5. 模拟同一响应里两个 `tool_use`，确认生成两个匹配的 `tool_result`。
6. 故意漏掉一个 `tool_result`，观察 API 的协议错误；不要在真实有副作用的工具上实验。
7. 为循环加入很小的 `max_iterations`，模拟模型持续犯错时如何退出。

## 十、待验收问题

1. `TOOLS`、`TOOL_HANDLERS` 和 `TOOL_VALIDATORS` 分别给谁使用？
2. 为什么模型看过 JSON Schema 后，本地仍要校验？
3. 为什么校验必须发生在 handler 执行之前？
4. `tool_use.id` 与 `tool_result.tool_use_id` 是什么关系？
5. `is_error: true` 会不会触发 API 自动重试？
6. Client Tool、Server Tool 和 Remote MCP Tool 分别由谁执行？
7. 工具执行错误与消息协议错误的处理方式有什么不同？
8. 为什么不能把完整异常栈直接返回给模型？
9. 为什么工具结果可能成为 Prompt Injection 的载体？
10. 如果模型连续三次生成同一个错误参数，Agent 应该怎样终止或升级处理？

## 十一、延伸阅读

> 官方文档核对日期：2026-08-24。API、Beta 功能和 MCP 版本可能变化，使用前应重新核对。

- [Claude：Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)
- [Claude：Parallel tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use)
- [Claude：Tool Runner (SDK)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)
- [Claude：Server tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)
- [Claude：MCP Connector](https://platform.claude.com/docs/en/agents-and-tools/mcp-connector)
- [Claude：Troubleshooting tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use)
- [Pydantic：Strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/)
- [Pydantic：JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/)

## 十二、本章记忆句

```text
TOOLS 让模型知道能调用什么；
TOOL_HANDLERS 让 Harness 知道实际执行什么；
TOOL_VALIDATORS 在副作用发生前拒绝非法输入；
tool_result 让模型知道执行结果；
tool_use_id 负责配对；
is_error 负责表达失败，但不会自动重试。
```

