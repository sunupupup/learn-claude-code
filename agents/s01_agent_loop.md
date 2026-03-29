# Harness第一步：调用LLM

# 标准 Tool Call 流程
这是一次标准的 Tool Call 对话记录

```python
[
  # 1. 用户原始提问（必须存）
  {"role": "user", "content": "用户输入"},

  # 2. AI 助手的完整回复（包含 tool_use 块）
  # 这边的 content 是个对象数组，有些对象的 type 是 tool_use , 代表需要客户端执行工具调用流程
  {"role": "assistant", "content": response.content},

  # 3. 把工具执行结果，以 user 身份发回给 AI（必须存）
  {"role": "user", "content": [工具结果数组]}
]
```

比如咨询：今天北京的天气如何？
```python
[
  # 第1条：用户提问
  {"role": "user", "content": "今天北京天气？"},

  # 第2条：AI 回复（包含 tool_use）
  {"role": "assistant", "content": [
    {"type": "tool_use", "id": "1", "name": "get_weather", "input": {"city": "北京"}}
  ]},

  # 第3条：工具结果（以 user 身份发送）
  {"role": "user", "content": [
    {"type": "tool_result", "tool_use_id": "1", "content": "北京今天晴天 25℃"}
  ]}
]
```

- 客户端解析 response content
- 拿到要调用的工具名字
- 提供调用工具的方法
- 将工具结果添加到 history


# 利用 Prompt Cache

上面的 history 天生支持缓存，只要不断往后添加内容

只要历史消息（history）前面的部分完全一模一样、一字不差、顺序不变 → 就能命中缓存！
```bash
历史1：
A → B → C → D

历史2：
A → B → C → D → E
```
历史 2 的 A→B→C→D 完全复用缓存
不需要重新计算
省 token、省时间、降成本