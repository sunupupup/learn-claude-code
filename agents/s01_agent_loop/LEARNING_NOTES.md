# s01 学习手册：Agent Loop

> 学习状态：进行中
> 本章目标：理解带工具调用的最小 Agent Loop，能够独立写出前置、核心和后置伪代码，并能解释 Tool Call 的消息协议。

## 一、本章核心结论

第一章讲的是：当模型具备工具调用能力时，Harness 如何把下面几个环节连接成一个完整闭环：

```text
用户提出目标
    ↓
模型判断下一步
    ↓
模型请求调用工具
    ↓
Harness 执行工具
    ↓
Harness 把工具结果放回消息历史
    ↓
模型根据结果继续判断
    ↓
需要工具：继续循环
不需要工具：输出最终答案并结束
```

最核心的循环可以概括为：

```text
模型请求工具 → 执行工具 → 返回结果 → 再次调用模型
```

它是一个**最小完整 Agent Loop**，但还不是生产级 Agent。权限、错误恢复、上下文压缩、子 Agent、后台任务等机制会在后续章节逐步增加。

### 各角色的职责

| 角色 | 职责 |
|---|---|
| 用户 | 提供最终目标 |
| 模型（LLM） | 判断下一步做什么、是否调用工具、什么时候停止 |
| Harness | 调用模型、执行工具、维护消息历史、把结果送回模型 |
| 工具 | 真正读取或改变外部环境，例如执行命令、读取文件 |

模型本身不会直接执行命令。模型只生成结构化的工具调用请求，真正执行工具的是 Harness。

## 二、我的原始伪代码

```text
一个基本的有无 tool call 的 agent loop 代码

def cmd_tool(cmd)
   return cmd.exec().result()

def tool_define_map tool 的基本定义 tool 的名字、schema、描述信息

messages = []
def loop(user_message) {
   messages.append({ role:user, message: user_message})
   while True:
       res = llm.invoke(messages)
       if res.stop_reason !== "tool_call"
           messages.append({assistant, res.content})
           break;

       // 执行 tool_call
       tool_result = tool_define_map[res.tool_call.command]
       message.append({tool_use, tool_result})
}

loop(user_message)
```

## 三、已经理解正确的部分

原始伪代码已经正确理解了以下核心思想：

1. 需要一个 `messages` 保存对话历史。
2. 用户输入要先加入消息历史。
3. Agent 的核心是一个持续运行的循环。
4. 每一轮都要调用 LLM，让模型判断下一步。
5. 需要通过 `stop_reason` 判断模型是否要求调用工具。
6. 模型调用工具时，Harness 要执行对应工具。
7. 模型不再调用工具时，当前任务结束。

目前的理解不是方向错误，而是消息协议和工具分发的细节还需要补全。

## 四、问题与原因逐条记录

### 问题 1：工具定义和工具执行映射混在了一起

原始写法：

```text
tool_define_map
```

实际上需要区分两个结构：

```text
TOOLS：给模型看的工具说明
TOOL_HANDLERS：给 Harness 使用的执行函数映射
```

示例：

```text
TOOLS = [
    {
        name: "bash",
        description: "执行一条命令",
        input_schema: {...}
    }
]

TOOL_HANDLERS = {
    "bash": run_bash
}
```

`TOOLS` 解决“模型怎么知道有哪些工具”的问题；`TOOL_HANDLERS` 解决“Harness 怎么找到真正的执行函数”的问题。

### 问题 2：调用 LLM 时没有传入工具定义

原始写法：

```text
res = llm.invoke(messages)
```

应当把工具定义一起传入：

```text
res = llm.invoke(
    messages = messages,
    tools = TOOLS
)
```

如果没有传入 `TOOLS`，模型就不知道当前环境提供了哪些工具、工具需要什么参数。

### 问题 3：只有不调用工具时才保存模型响应

原始代码只在结束分支保存了模型响应：

```text
if res.stop_reason !== "tool_call":
    messages.append({assistant, res.content})
```

无论模型有没有调用工具，都必须先保存完整的 assistant 响应：

```text
messages.append({
    role: "assistant",
    content: response.content
})
```

如果不保存包含 `tool_use` 的 assistant 消息，下一轮模型只能看到工具结果，却看不到这个结果对应的工具请求，对话链条就断了。

### 问题 4：使用了命令参数查找工具，而不是使用工具名称

原始思路：

```text
tool_define_map[res.tool_call.command]
```

例如模型返回：

```json
{
  "name": "bash",
  "input": {
    "command": "python main.py"
  }
}
```

应该使用 `name` 找处理器，使用 `input` 作为参数：

```text
handler = TOOL_HANDLERS[tool_call.name]
result = handler(**tool_call.input)
```

对应关系是：

```text
"bash" → run_bash
```

而不是：

```text
"python main.py" → run_bash
```

### 问题 5：`tool_use` 和 `tool_result` 混淆

- `tool_use`：模型发出的工具调用请求。
- `tool_result`：Harness 执行工具后返回给模型的结果。

Harness 应该追加 `tool_result`，而不是再次追加 `tool_use`。

```text
messages.append({
    role: "user",
    content: [{
        type: "tool_result",
        tool_use_id: tool_call.id,
        content: result
    }]
})
```

### 问题 6：缺少 `tool_use_id`

每次工具调用都有唯一 ID：

```text
tool_use.id
    ↓ 对应
tool_result.tool_use_id
```

模型可能一次调用多个工具。`tool_use_id` 用来说明每个执行结果分别对应哪一次工具调用。

### 问题 7：只考虑了单个工具调用

模型的 `response.content` 是一个内容块数组，一次响应里可能同时包含文本和一个或多个 `tool_use`：

```text
for block in response.content:
    if block.type == "tool_use":
        执行这个工具调用
```

因此最小实现也应当遍历工具调用，而不是只读取单个 `res.tool_call`。

### 问题 8：变量名不一致

原始代码初始化的是：

```text
messages = []
```

后面却写成：

```text
message.append(...)
```

这里应统一为 `messages.append(...)`。

### 问题 9：Anthropic 的停止原因是 `tool_use`

在抽象伪代码中写 `tool_call` 可以表达意思，但本项目使用 Anthropic Messages API，实际值是：

```text
response.stop_reason == "tool_use"
```

`tool_call`、`function_call`、`tool_use` 等命名会因不同模型厂商的协议而不同。

### 问题 10：缺少错误结果和最终输出

工具执行可能失败。即使失败，也应把错误作为工具结果返回给模型，让模型决定重试、换方案或向用户解释。

模型不再调用工具时，还需要输出或返回最终文本，而不仅仅是 `break`。

## 五、Tool Call JSON Schema

需要区分三个阶段的 JSON。

### 5.1 发给模型的工具定义

本章定义的 bash 工具：

```json
{
  "name": "bash",
  "description": "Run a shell command.",
  "input_schema": {
    "type": "object",
    "properties": {
      "command": {
        "type": "string"
      }
    },
    "required": ["command"]
  }
}
```

这里的 `command` 是本项目自己定义的参数名，不是 LLM API 固定要求的名字。

如果工具定义改成：

```json
{
  "input_schema": {
    "type": "object",
    "properties": {
      "cmd": {
        "type": "string"
      }
    },
    "required": ["cmd"]
  }
}
```

模型就应该返回 `input.cmd`，执行代码也要相应改为：

```python
output = run_bash(block.input["cmd"])
```

### 5.2 模型返回的 `tool_use`

模型的完整响应大致如下：

```json
{
  "id": "msg_01ABC",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "我先查看一下当前目录。"
    },
    {
      "type": "tool_use",
      "id": "toolu_01XYZ",
      "name": "bash",
      "input": {
        "command": "dir"
      }
    }
  ],
  "stop_reason": "tool_use"
}
```

工具调用块的通用形状是：

```json
{
  "type": "tool_use",
  "id": "本次工具调用的唯一ID",
  "name": "工具名称",
  "input": {
    "由input_schema定义的参数": "参数值"
  }
}
```

所以真实代码中的：

```python
output = run_bash(block.input["command"])
```

意思是：从模型返回的 `tool_use` 内容块中取得 `input.command`，然后把它交给 `run_bash` 执行。

### 5.3 Harness 返回的 `tool_result`

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_01XYZ",
      "content": "main.py\nREADME.md",
      "is_error": false
    }
  ]
}
```

其中：

- `tool_use_id` 必须对应原来 `tool_use` 的 `id`。
- `content` 是工具的执行结果。
- `is_error` 是可选字段，工具失败时可以设置为 `true`。
- Anthropic 协议使用下一条 `user` 消息承载客户端工具结果。

完整对应关系：

```text
工具定义：
    name = bash
    input_schema.properties.command

模型返回：
    type = tool_use
    id = toolu_01XYZ
    name = bash
    input.command = dir

Harness 执行：
    run_bash("dir")

Harness 返回：
    type = tool_result
    tool_use_id = toolu_01XYZ
    content = 命令执行结果
```

## 六、修正后的完整伪代码

```text
函数 run_bash(command):
    return 执行命令(command).结果


// 给模型看的工具定义
TOOLS = [
    {
        name: "bash",
        description: "执行一条 Shell 命令并返回结果",
        input_schema: {
            type: "object",
            properties: {
                command: {
                    type: "string"
                }
            },
            required: ["command"]
        }
    }
]


// Harness 使用的工具执行映射
TOOL_HANDLERS = {
    "bash": run_bash
}


messages = []


函数 agent_loop(user_message):

    messages.append({
        role: "user",
        content: user_message
    })

    while True:

        response = llm.invoke(
            messages = messages,
            tools = TOOLS
        )

        // 无论是否调用工具，都先保存完整模型响应
        messages.append({
            role: "assistant",
            content: response.content
        })

        // 模型不再调用工具，本轮任务完成
        if response.stop_reason != "tool_use":
            输出 response.content 中的最终文本
            break

        tool_results = []

        // 一次响应可能包含多个工具调用
        for block in response.content:

            if block.type != "tool_use":
                continue

            tool_name = block.name
            tool_args = block.input
            handler = TOOL_HANDLERS[tool_name]

            try:
                result = handler(**tool_args)
                is_error = false
            catch error:
                result = "工具执行失败：" + error
                is_error = true

            tool_results.append({
                type: "tool_result",
                tool_use_id: block.id,
                content: result,
                is_error: is_error
            })

        // 将工具结果作为下一条消息送回模型
        messages.append({
            role: "user",
            content: tool_results
        })

        // 回到 while 开头，模型读取工具结果并继续判断
```

## 七、前置、核心与后置代码

### 前置处理

```text
初始化 LLM 客户端
定义工具的 name、description 和 input_schema
实现真正的工具函数
建立工具名称到执行函数的映射
初始化 messages
接收并保存用户输入
```

### 核心处理

```text
调用模型
保存完整模型响应
判断 stop_reason
查找并执行模型请求的工具
收集 tool_result
把结果送回模型
继续循环
```

### 后置处理

```text
模型不再请求工具
提取并输出最终文本
退出当前任务循环
保留或清理消息历史
等待下一次用户输入
```

## 八、待验收问题与掌握状态

### 当前掌握状态

| 知识点 | 状态 | 备注 |
|---|---|---|
| Agent Loop 的整体目的 | 已理解 | 能说明“调用—执行—反馈—继续”的闭环 |
| `messages` 的作用 | 基本理解 | 需要继续强化严格的消息顺序 |
| 工具定义与 Handler 的区别 | 已纠正 | 后续需要独立复述 |
| `tool_use` 与 `tool_result` | 已纠正 | 需要记住二者方向相反 |
| `tool_use_id` 的作用 | 已学习 | 用于匹配调用与结果 |
| `input_schema` 与 `block.input` | 已学习 | 参数字段由工具定义决定 |
| 多工具调用 | 已学习 | 需要遍历 `response.content` |
| 独立写完整伪代码 | 待再次验收 | 建议脱离本手册再写一次 |

### 待验收问题

1. 如果模型第一次响应就没有调用工具，循环应该继续还是结束？为什么？
2. 为什么模型发出的 `tool_use` 必须先加入 `messages`？
3. `TOOLS` 和 `TOOL_HANDLERS` 分别给谁使用？
4. 为什么不能使用 `command` 的值查找工具处理器？
5. `tool_use.id` 和 `tool_result.tool_use_id` 有什么关系？
6. `block.input["command"]` 中的 `command` 是谁规定的？
7. 模型一次返回三个工具调用时，Harness 应该如何处理？
8. 工具执行失败后，为什么仍然应该把错误结果返回给模型？
9. 请不看修正版，独立写出完整 Agent Loop 伪代码。

### 本章通过标准

满足以下条件后，可以认为 s01 通过：

- 能用自己的话解释 Agent Loop 为什么存在。
- 能准确说出模型、Harness 和工具的职责边界。
- 能写出正确的消息顺序。
- 能解释 Tool Call 的 `id`、`name`、`input`。
- 能独立写出包含前置、核心、后置处理的伪代码。
- 面对异常、多工具调用等追问时，不只是背诵主流程。

## 九、补充问题：是否只需要检查最后一个 content block

### 新发现的遗漏

`response.content` 是一个数组，里面可能同时存在：

```text
text block
tool_use block
tool_use block
```

因此需要遍历整个数组，不能只处理一个 `tool_call`，也不能只执行最后一个内容块。

### `stop_reason` 和 content block 分别表示什么

```text
stop_reason：模型这一轮为什么停止生成
content block：模型这一轮具体生成了什么内容或动作
```

对于 Anthropic 客户端工具调用，正常的完整响应通常满足：

```text
response.stop_reason == "tool_use"
并且
response.content 中存在一个或多个 type == "tool_use" 的块
```

但是不要把条件写成：

```text
stop_reason == "tool_use"
并且
response.content[-1].type == "tool_use"
```

原因如下：

1. `content` 中可能有多个工具调用，只检查最后一个会漏掉前面的调用。
2. 官方协议保证工具调用响应包含一个或多个 `tool_use` 块，但不应把“最后一个块一定是 tool_use”当成业务代码依赖的协议不变量。
3. 流式响应中，`tool_use` 内容块和最终 `stop_reason` 不是同时到达的。
4. 未来增加新的内容块类型、SDK 转换或中间层处理时，依赖最后一个块会变得脆弱。

### 教学版的处理方式

本章教学代码先使用 `stop_reason` 判断这一轮是否进入工具处理流程，然后遍历整个数组：

```text
if response.stop_reason != "tool_use":
    结束循环

for block in response.content:
    if block.type == "tool_use":
        执行这个工具调用
```

### 更稳健的处理方式

生产实现可以先扫描具体内容，再校验它与 `stop_reason` 是否一致：

```text
tool_calls = []

for block in response.content:
    if block.type == "tool_use":
        tool_calls.append(block)


if response.stop_reason == "tool_use" and tool_calls 不为空:
    执行全部 tool_calls

else if response.stop_reason == "tool_use" and tool_calls 为空:
    这是协议异常或响应不完整
    记录错误并重试，不能空转

else if response.stop_reason == "max_tokens" and tool_calls 不为空:
    工具调用可能被截断
    不要直接执行，增加 token 限制后重试

else if tool_calls 不为空:
    stop_reason 与内容不一致
    按协议异常处理，并验证工具参数

else:
    没有工具调用，处理最终文本或其他停止原因
```

### 会不会出现 `stop_reason == tool_use`，但最后一个块不是 tool_use

在当前常见的非流式 Anthropic 客户端工具响应中，`tool_use` 通常位于文本块之后，最后一个块往往也是 `tool_use`。但是官方推荐的处理代码仍然遍历整个 `response.content`，而不是只依赖 `response.content[-1]`。

所以工程上的结论是：

```text
不能假设这种组合绝对不会出现。
也没有必要依赖“最后一个块”的位置来判断。
```

更应该关注的是：

```text
stop_reason == "tool_use"
response.content 中至少存在一个 tool_use
所有 tool_use 都被逐个处理
```

### 一个更容易真实遇到的相反情况

更值得注意的是：

```text
stop_reason == "max_tokens"
最后一个 content block 是 tool_use
```

这表示模型可能在生成工具参数时触达 token 上限，工具调用可能不完整。此时不应该直接执行，应提高 `max_tokens` 后重新请求。

### 流式响应的特殊性

流式调用时，事件到达顺序可能是：

```text
先收到 text/tool_use 内容块
    ↓
继续接收 input JSON 增量
    ↓
最后在 message_delta 中收到 stop_reason
```

因此在流式处理中，不能在内容还没接收完整时就只靠当前的 `stop_reason` 判断。应等待工具调用参数组装完成，或者像生产实现一样，在流式事件中记录“是否出现过完整 tool_use”。

### 本问题的最终记忆句

```text
stop_reason 是整轮生成的停止信号；
content blocks 才是这一轮需要处理的具体内容。

判断是否进入工具流程要看 stop_reason；
执行哪些工具必须遍历全部 content blocks；
生产代码还要校验两者是否一致。
```

## 十、补充问题：`invoke`、`stream` 和其他调用方式

### `invoke` 一般表示什么

`invoke` 不是所有模型厂商统一规定的 HTTP API 名称，它通常是上层框架提供的统一调用接口，含义是：

```text
给当前对象一个输入
等待它处理完成
返回一个完整输出
```

例如 LangChain 的 `Runnable` 把单输入、完整输出的同步调用统一命名为：

```text
result = runnable.invoke(input)
```

但需要观察 `invoke` 前面的对象是谁：

```text
llm.invoke(messages)
    通常只进行一轮模型调用

chain.invoke(input)
    可能依次执行提示词、模型、解析器等整条 Chain

agent.invoke(input)
    可能在框架内部运行多轮模型调用和工具执行，直到 Agent 结束
```

所以不能只看到方法名 `invoke` 就判断它只调用了一次 LLM；真正的执行边界由被调用对象决定。

### 本项目实际没有使用 `invoke`

本章 Anthropic SDK 的真实代码是：

```python
response = client.messages.create(
    model=MODEL,
    system=SYSTEM,
    messages=messages,
    tools=TOOLS,
    max_tokens=8000,
)
```

这里的 `messages.create(...)` 在概念上相当于：

```text
llm.invoke(messages)
```

也就是发起一轮非流式模型请求，等待整轮响应完成后取得完整 `response`。

### 常见调用方式

| 方式 | 常见命名 | 含义 |
|---|---|---|
| 同步、完整响应 | `invoke`、`create` | 阻塞等待，最后一次性返回完整结果 |
| 异步、完整响应 | `ainvoke`、`await create` | 等待期间不阻塞整个事件循环 |
| 同步流式响应 | `stream` | 持续迭代接收文本块或事件 |
| 异步流式响应 | `astream` | 异步迭代接收文本块或事件 |
| 批量调用 | `batch` | 一次提交或并发处理多个独立输入 |
| 异步批量调用 | `abatch` | 异步处理多个独立输入 |
| 事件流 | `stream_events`、`astream_events` | 接收开始、增量、工具调用、结束等更细粒度事件 |

前缀 `a` 通常表示 asynchronous（异步）：

```text
invoke  → 同步调用
ainvoke → 异步调用

stream  → 同步流
astream → 异步流

batch   → 同步批量
abatch  → 异步批量
```

具体方法名称仍取决于 SDK 或框架，不能认为所有厂商都使用同一套命名。

### 非流式调用

```text
response = llm.invoke(messages)
```

过程是：

```text
发送请求
    ↓
等待模型生成完整响应
    ↓
一次性得到完整 content 和 stop_reason
```

优点：

- 代码简单。
- 得到的 `content` 和 `stop_reason` 已经完整。
- 适合学习 Agent Loop 和后端批处理。

缺点：

- 模型生成较慢时，用户长时间看不到输出。
- 不能提前展示文本或观察工具参数生成过程。

### 流式调用

```text
for chunk/event in llm.stream(messages):
    处理当前增量
```

过程是：

```text
发送请求
    ↓
收到一小段 text
    ↓
收到下一段 text 或 tool_use 增量
    ↓
逐步组装完整响应
    ↓
最后收到停止原因
```

流式返回的通常不是多个独立回答，而是**同一轮回答的多个增量片段**。

### 流式 Tool Call 的特殊点

流式响应中，工具参数 JSON 可能被拆成多个增量：

```text
第一个增量：{"command": "py
第二个增量：thon main
第三个增量：.py"}
```

概念上需要先组装：

```text
input_json = ""

for event in stream:
    if event 是工具参数增量:
        input_json += event.partial_json

等待该 tool_use block 完成
tool_input = parse_json(input_json)
执行工具
```

不能收到第一段参数就马上执行工具，否则 JSON 可能不完整。

同时，流式过程中 `stop_reason` 可能还没有到达；通常要到最终事件才能知道这一轮为什么停止。

### Stream 和 Agent Loop 是两层循环

它们不是二选一关系：

```text
外层循环：Agent Loop
    控制模型调用 → 工具执行 → 结果回填 → 再次调用模型

内层循环：Stream Loop
    控制一轮模型调用中的增量接收和响应组装
```

组合后的伪代码：

```text
while Agent 还没有结束:

    完整响应 = 初始化响应构建器

    for event in llm.stream(messages, tools):
        展示文本增量
        组装 content blocks
        组装 tool input JSON
        记录最终 stop_reason

    messages.append(完整 assistant 响应)

    tool_calls = 从完整响应中提取所有 tool_use

    if 没有工具调用:
        结束 Agent Loop

    执行所有工具调用
    messages.append(tool_results)
```

因此：

```text
invoke/stream 决定“一轮模型响应怎么拿回来”；
Agent Loop 决定“拿到一轮响应后，要不要执行工具并继续下一轮”。
```

### Batch 与 Agent Loop 的区别

`batch` 通常用于多个互相独立的输入：

```text
batch([
    "总结文件 A",
    "总结文件 B",
    "总结文件 C"
])
```

它不是 Agent 的多轮循环，也不是一次响应中的多个工具调用。需要区分：

```text
batch：多个独立模型请求
parallel tool calls：同一轮模型响应要求执行多个工具
Agent Loop：同一任务的多轮模型调用
```

### 本问题的最终记忆句

```text
invoke：等待一次调用得到完整输出。
stream：一边生成，一边接收同一次调用的增量。
ainvoke/astream：对应的异步版本。
batch/abatch：处理多个独立输入。

Stream 是单轮内部的接收方式，Agent Loop 是多轮之间的控制流程。
```

## 十一、补充问题：Message Role 与 Content Block

> 核对范围：Anthropic Python SDK / Messages API，核对日期 2026-08-19。

### 11.1 Message 的基本结构

一条消息可以先理解成：

```text
Message = 谁发的（role）+ 发了什么（content）
```

```json
{
  "role": "user",
  "content": "你好"
}
```

或者使用内容块数组：

```json
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "你好"
    }
  ]
}
```

在 Anthropic Messages API 中，这两种写法等价。字符串是单个 `text` block 的简写。

### 11.2 通用聊天系统中常见的 role

不同厂商和框架的 role 不完全一致。常见概念包括：

| role | 一般含义 |
|---|---|
| `system` | 平台或应用给模型的最高层行为说明 |
| `developer` | 开发者指令；部分厂商提供，Anthropic Messages 不使用这个消息 role |
| `user` | 用户或外部环境提供给模型的信息 |
| `assistant` | 模型生成的消息 |
| `tool` | 工具执行结果；部分厂商使用独立 role，Anthropic 不这样表示 |

这些是跨厂商的通用概念，不代表每个 API 都支持所有 role。

### 11.3 Anthropic Messages API 实际使用的 role

Anthropic 的 `messages` 数组中使用：

```text
user
assistant
```

系统提示词不放在 `messages` 里，而是使用请求的顶层 `system` 参数：

```python
client.messages.create(
    system="You are a coding agent.",
    messages=[
        {"role": "user", "content": "查看当前目录"}
    ],
)
```

模型生成的响应，其 `role` 固定是：

```text
assistant
```

Anthropic 没有单独的 `tool` role。客户端工具执行结果使用一个 `tool_result` 内容块，放进下一条 `user` 消息：

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_123",
      "content": "命令执行成功"
    }
  ]
}
```

这里的 `user` 不表示结果是人类亲手输入的。它表示这是从模型外部环境送回给模型的新输入。

### 11.4 `content` 是字符串或内容块数组

消息级别的 `content` 可以是：

```text
字符串
或
ContentBlock 数组
```

简单文本可以写成：

```json
{
  "role": "user",
  "content": "读取 README.md"
}
```

复杂内容使用数组：

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "分析这张图片"},
    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}
  ]
}
```

数组的意义是：一条消息可以同时携带多种、多个有顺序的内容块。

### 11.5 `type` 是内容块的判别字段

`type` 可以理解为：

```text
这个 block 到底是什么类型，以及应该按照哪套字段解释它
```

程序通常这样分发：

```text
for block in message.content:
    if block.type == "text":
        使用 block.text
    else if block.type == "tool_use":
        使用 block.id、block.name、block.input
    else if block.type == "tool_result":
        使用 block.tool_use_id、block.content、block.is_error
```

这是一种 discriminated union（带判别字段的联合类型）：同一个数组可以装不同结构，而 `type` 决定当前结构。

### 11.6 第一章最重要的 Content Block

#### Text Block

```json
{
  "type": "text",
  "text": "任务已经完成"
}
```

关键字段：

```text
type = text
text = 文本内容
```

注意这里的正文属性叫 `text`，不是 `content`。

#### Tool Use Block

由模型生成，表示模型请求客户端执行工具：

```json
{
  "type": "tool_use",
  "id": "toolu_123",
  "name": "bash",
  "input": {
    "command": "python main.py"
  }
}
```

关键字段：

| 字段 | 作用 |
|---|---|
| `type` | 固定为 `tool_use` |
| `id` | 本次调用的唯一 ID |
| `name` | 工具名称，用于查找 Handler |
| `input` | 工具参数，形状由工具 `input_schema` 决定 |

#### Tool Result Block

由 Harness 生成，表示客户端工具的执行结果：

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_123",
  "content": "程序输出：Hello",
  "is_error": false
}
```

关键字段：

| 字段 | 作用 |
|---|---|
| `type` | 固定为 `tool_result` |
| `tool_use_id` | 对应原 `tool_use.id` |
| `content` | 工具返回的实际结果 |
| `is_error` | 可选；是否为错误结果 |

其中真正必不可少的对应关系是：

```text
tool_use.id == tool_result.tool_use_id
```

`tool_result.content` 可以直接是字符串：

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_123",
  "content": "Hello"
}
```

也可以是内容块数组，例如同时返回文字和图片：

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_123",
  "content": [
    {
      "type": "text",
      "text": "截图如下"
    },
    {
      "type": "image",
      "source": {
        "type": "base64",
        "media_type": "image/png",
        "data": "..."
      }
    }
  ]
}
```

### 11.7 这段代码中有两层 `content`

原代码：

```text
messages.append({
    role: "user",
    content: [{
        type: "tool_result",
        tool_use_id: tool_call.id,
        content: tool_result
    }]
})
```

可以展开为：

```text
外层 message.content
    = 这条 user 消息包含哪些内容块

内层 tool_result.content
    = 这个工具结果块携带的实际执行结果
```

类比：

```text
Message           = 一个信封
Message.content   = 信封里的附件列表
ToolResult block  = 其中一份“工具结果”附件
block.content     = 这份附件里面的具体结果
```

### 11.8 Tool Call 的完整消息顺序

```json
[
  {
    "role": "user",
    "content": "运行 main.py"
  },
  {
    "role": "assistant",
    "content": [
      {
        "type": "tool_use",
        "id": "toolu_123",
        "name": "bash",
        "input": {"command": "python main.py"}
      }
    ]
  },
  {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "toolu_123",
        "content": "Hello"
      }
    ]
  }
]
```

然后再次调用模型，模型可以继续请求工具，也可以返回最终的 `text` block。

### 11.9 必须记住的协议约束

1. 模型的完整 assistant 响应要先原样加入消息历史。
2. `tool_result` 要放在紧接着的下一条 `user` 消息里。
3. `tool_result.tool_use_id` 必须匹配对应的 `tool_use.id`。
4. 一次响应存在多个 `tool_use` 时，要为每个调用返回一个匹配的 `tool_result`。
5. 不要把不同厂商的 `tool` role 直接套用到 Anthropic 协议。
6. `content` block 的结构由 `type` 决定，不能统一读取 `block.content`。

### 11.10 本问题的最终记忆句

```text
role 决定“谁发的”；
message.content 决定“发了哪些内容块”；
block.type 决定“当前内容块按什么结构解释”。

text 看 text；
tool_use 看 id、name、input；
tool_result 看 tool_use_id、content、is_error。
```

## 十二、补充问题：LangChain Runnable 是什么

> 核对范围：LangChain Python 当前文档，核对日期 2026-08-19。

### 12.1 一句话定义

LangChain 的 `Runnable` 是一个统一的“可执行工作单元”接口：

```text
Runnable<Input, Output>
    输入一个值
    执行一段工作
    返回一个输出
```

它支持统一的调用方式：

```text
invoke / ainvoke
stream / astream
batch / abatch
```

以及组合能力：

```text
RunnableSequence：串行组合
RunnableParallel：并行组合
```

### 12.2 Runnable 不是完整的 Agent Runtime

`Runnable` 更接近：

```text
一个统一的函数对象接口
或
一个可组合的任务节点接口
```

它本身不自动提供：

```text
Agent Loop
工具权限
消息持久化
沙箱
任务恢复
长期记忆
```

这些能力需要由具体 Runnable、Agent、LangGraph Runtime 或其他 Harness 组件实现。

### 12.3 哪些对象可以是 Runnable

例如：

```text
PromptTemplate
ChatModel
OutputParser
Retriever
普通 Python 函数的 Runnable 包装
多个组件组成的 Chain
封装了 Agent Graph 的可执行对象
```

它们的内部工作完全不同，但外部调用方式可以统一为：

```python
output = runnable.invoke(input)
```

### 12.4 Runnable 的组合

```python
chain = prompt | model | parser

result = chain.invoke({"topic": "Agent Loop"})
```

逻辑上相当于：

```text
prompt_output = prompt.invoke(input)
model_output = model.invoke(prompt_output)
result = parser.invoke(model_output)
```

前一个 Runnable 的输出会成为后一个 Runnable 的输入。

### 12.5 为什么需要 Runnable

如果没有统一接口，不同组件可能分别使用：

```text
prompt.format(...)
model.generate(...)
parser.parse(...)
retriever.search(...)
```

统一成 Runnable 后，可以使用相同的执行协议：

```text
invoke：单输入完整调用
ainvoke：异步单输入调用
stream：单输入流式输出
astream：异步流式输出
batch：多个输入
abatch：异步多个输入
```

并可以统一添加配置、追踪、并发控制、重试或组合。

### 12.6 Runnable 和 Agent 的关系

Runnable 不是 Agent，但 Agent 可以被包装或编译成一个 Runnable 风格的对象：

```python
agent = create_agent(
    model=model,
    tools=tools,
)

result = agent.invoke({
    "messages": [
        {"role": "user", "content": "完成任务"}
    ]
})
```

表面上只调用了一次 `agent.invoke(...)`，但 Agent 内部可能运行：

```text
调用模型
→ 执行工具
→ 返回工具结果
→ 再次调用模型
→ 直到结束
```

因此：

```text
llm.invoke：通常是一轮模型请求
chain.invoke：通常执行整条 Chain
agent.invoke：可能运行完整的多轮 Agent Loop
```

`invoke` 的边界由前面的对象决定。

### 12.7 Runnable、Agent Loop 和 Runtime 的区别

| 概念 | 负责什么 |
|---|---|
| `Runnable` | 统一 Input → Output 的调用和组合接口 |
| Agent Loop | 控制模型、工具、结果反馈和停止条件 |
| Runtime | 运行和管理 Agent，包括状态、持久化、恢复、流式事件、并发等 |
| Harness | 更大的外部工作环境，包括工具、权限、知识、上下文和沙箱 |

在当前 LangChain v1 架构里，`create_agent` 构建的 Agent 底层运行在 LangGraph Runtime 上。

### 12.8 一个准确的类比

```text
Runnable 接口
    ≈ 所有电器统一使用插头接口

某个具体 Runnable
    ≈ 电饭煲、空调或电脑

RunnableSequence
    ≈ 把多个设备按顺序连接

Agent
    ≈ 内部包含判断和循环的自动设备

Runtime
    ≈ 供电、调度、状态和故障恢复系统
```

插头接口让设备能以统一方式连接和调用，但插头本身不是完整的设备运行系统。

### 12.9 本问题的最终记忆句

```text
Runnable 是 LangChain 的可执行组件协议，不是 Agent 本身。
Agent 可以表现为 Runnable，但内部可能包含完整 Agent Loop。
Runtime 才负责状态、调度、持久化和恢复等运行期能力。
```
