| 接口 | 谁定义的 | 大致怎样组织请求 |
| --- | --- | --- |
| **Responses API** | OpenAI | 用 `input` 放消息、工具调用与结果等条目，`tools` 声明工具 |
| **Anthropic Messages API** | Anthropic | 用 `system`、`messages` 和内容块组织对话，`tools` 声明工具 |



## OpenAI Response

请求入口通常是 POST /v1/responses：
重点：消息放 input，函数定义直接放在工具对象上，参数规则叫 parameters。

```json
{
  "model": "<模型名>",
  "instructions": "你是天气助手。",
  "input": [
    {
      "role": "user",
      "content": "北京天气怎么样？"
    }
  ],
  "tools": [
    {
      "type": "function",
      "name": "get_weather",
      "description": "查询指定城市的天气",
      "parameters": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
        "additionalProperties": false
      },
      "strict": true
    }
  ],
  "max_output_tokens": 1000,
  "stream": true
}
```

## Anthropic Messages 格式

请求入口通常是 POST /v1/messages：

```json
{
  "model": "<模型名>",
  "system": "你是天气助手。",
  "messages": [
    {
      "role": "user",
      "content": "北京天气怎么样？"
    }
  ],
  "tools": [
    {
      "name": "get_weather",
      "description": "查询指定城市的天气",
      "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
        "additionalProperties": false
      }
    }
  ],
  "max_tokens": 1000,
  "stream": true
}
```

重点：系统指令放 system，消息放 messages，参数规则叫 input_schema。 官方说明

## Chat Messages

它看起来就是一份完整的“对话＋行动记录”。

```json
{
  "messages": [
    {"role": "system", "content": "你是天气助手。"},
    {"role": "user", "content": "北京天气怎么样？"},
    {
      "role": "assistant",
      "tool_calls": [
        {
          "id": "call_123",
          "type": "function",
          "function": {
            "name": "get_weather",
            "arguments": "{\"city\":\"北京\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_123",
      "content": "北京晴，25℃"
    }
  ],
  "tools" 、 "response_format" 等其他字段
}
```

## 不同api格式转换

基础消息格式通常容易转换，真正决定兼容程度的是特殊字段及其语义。

| 层次 | 转换难度 | 例子 |
| --- | --- | --- |
| **基础格式** | 通常容易 | `messages` ↔ `input`，`parameters` ↔ `input_schema` |
| **功能语义** | 需要上游实际支持 | 中途 system 更新、工具增量声明、推理内容的保留 |
| **执行与计费行为** | 不能靠改字段保证 | 缓存命中、延迟工具是否真的不进入初始上下文 |

例如：
- 把 cache_control 原样转发过去，不代表上游会按它缓存。
- 把 tool_addition 转成普通文本，不代表新增工具获得了正式声明和调用约束。
- 把中途 system 消息合并到开头，可能让请求可用，但指令作用位置和缓存前缀已经变了。

很大考验 某些API中转站的 代理/适配 层的核心能力了

需要完全理解不同厂家的协议能力和语义

它需要判断：
- 能原生映射的：准确转换。
- 需要降级的：采用替代方式，并说明行为或缓存影响。
- 无法保真的：明确报错，避免悄悄丢掉关键能力。

## 需要注意的问题

| 适配点 | 错了会怎样 | 必须守住什么 |
| --- | --- | --- |
| 🔴 **1. 消息角色与指令优先级** | 中途 system 转成普通消息或合并到开头，语义可能改变；工具输出被提升成 system，还可能让外部内容变成高优先级指令 | 保留角色、可信程度及指令作用位置；无法等价表达时明确处理 |
| **2. 工具调用与结果关联** | 结果对应错调用，模型可能根据错误结果继续操作 | 保留调用 ID、名称、参数与结果的对应关系；不能因并行完成顺序不同而错配 |
| **3. 完整参数与结束原因** | 把被截断的参数当作完整调用执行，可能操作错误目标 | 区分正常完成、长度截断、错误、取消；不执行不完整参数 |
| **4. 重试、故障切换与取消** | 超时后盲目重跑，可能重复产生副作用；界面停止但后台仍运行 | 区分“请求失败”和“执行结果未知”；取消信号尽量传到底层 |
| 🔴 **5. 工具声明与结构化输出约束** | `tools`、Schema、`strict` 等字段被静默忽略，下游却仍按“约束已生效”处理 | 区分工具参数 Schema 与回答 Schema；不支持的约束不能假装生效 |
| 🔴 **6. 流式事件转换** | 特殊事件或内容块被丢弃；参数片段重复拼接，工具卡片错乱，失败被显示成成功 | 正确转换事件类型，区分增量与完整快照，保持事件归属和最终状态 |
| 🔴 **7. 中途 system、工具增量与缓存** | 把新增工具或系统指令合到头部，可能改变指令作用、破坏缓存前缀 | 核验上游是否原生支持；明确降级方式，不能把“请求可用”当成“语义与缓存等价” |
| **8. 凭证、用户隔离与日志** | Key、提示词或工具结果泄漏；不同用户的状态串用 | 隔离凭证与会话，日志脱敏，缓存及状态按正确范围隔离 |