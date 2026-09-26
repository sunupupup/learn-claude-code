# 厂商 API 与模型输入序列化对照

核验日期：2026-09-25。**本文是应用侧主线的边界辅助材料，不是本章起点。**本章先追 Agent 如何组装 `system_prompt + tools + messages`；只有走到 Provider adapter 后，才用本文区分公开 API 合同、开源模型 Chat Template（聊天模板）与托管 Provider 内部实现。这三类证据不能互相替代。

## 学习者的初始模型

> “在一次 LLM call 的时候传入 system_prompt、tool_schema、messages；引用层再将 JSON 转成完整字符串；用特殊 Token 标明字段；并按 system_prompt、tool_schema、messages 的顺序放置。”

🔴 **已验证理解**：Harness 确实会把指令、工具定义和对话历史作为模型请求输入；模型推理最终处理的是 Token 序列，边界/角色信息可由专门 Token 表示。

需要修正的是：

1. `system_prompt, tool_schema, messages` 是一种合理的应用抽象，不是统一的厂商 API 签名。
2. API 请求常是带有不同字段的 JSON 对象；模型侧的 Chat Template 才负责将其转换为该模型接受的输入格式。对托管 API，完整内部序列化通常不公开。
3. 工具定义可能被转换成模型 Prompt 中的一段工具描述，也可能由 Provider 以私有结构喂给模型。不能从 API JSON 字段顺序直接推出模型 Token 顺序。
4. `messages` 数组本身有语义顺序；JSON 对象键的书写顺序不等于模型输入的消息顺序。

## 本章需要保留的粗粒度模型

学习者确认的直觉：

> “不管 token 化方式，我只需要知道，他们必然是吧 system prompt 和 tool 放在最前面的，应该是这样吧。”

🔴 **已验证理解（作为应用侧观察起点）**：在常见 Agent API 中，`system_prompt` 和可用工具定义是当前模型调用的配置；会话 `messages` 则承载对话历史与本轮消息。做第一轮应用侧分析时，可以先画成：

```text
[稳定或较少变化的 system_prompt + tools 配置]
                         +
[当前会话 messages 历史与新消息]
```

需要留一条边界：这张图表达“应用组织模型调用时的稳定配置与对话状态”，不保证所有 Provider 会把 system 与 tools 严格串成 Token 序列最前面的连续文本块。OpenAI 文档明确说函数定义会注入 system message；Anthropic 和 Gemini 的公开 API 则把它们作为独立字段，并未承诺内部逐 Token 排列。因此做缓存分析时，把“system + tools”当作候选稳定前缀；要声称它们实际形成了前缀，还得查看具体 Agent 的请求构造和 Provider/模型公开格式。

## LangChain：固定的是 Agent 配置，不代表只发送一次

`create_agent(model, tools, system_prompt, checkpointer)` 在 Agent 创建时配置模型、可用工具、基础指令和状态持久化器。`invoke({"messages": [...]}, config=...)` 向有状态 Agent 提交消息；同一个 `thread_id` 可恢复此前检查点中的消息状态。

Agent 执行模型步骤时，会根据当前状态把系统指令、对话消息和当前可用工具交给模型调用层。若模型请求工具，LangChain 执行后把工具结果加入消息状态，再进入下一次模型调用。因此：

- tools 在 Agent 配置上可以长期固定；
- 在每一步模型调用中，当前可用的工具定义仍属于模型调用输入（具体 Provider 适配方式不同）；
- `messages` 是对话状态，通常包含历史与新消息；不是只把当前这一条 user 消息单独传给模型；
- Middleware 可以按对话状态动态更改 system prompt 或工具集合。

`checkpointer` 保存/恢复的是 Agent 状态（例如 messages），不是模型服务端的 KV Cache，也不代表 Provider 只接收增量消息。

## 厂商与模型格式对照

| 厂商/模型路径 | 公开 API 或格式证据 | 对“System / Tools 放在前面”的结论 | 不能据此断言的内容 |
| --- | --- | --- | --- |
| OpenAI API | Function calling 文档明确说，函数定义会以模型训练过的语法注入 system message，并计入 Context Token。 | 🟢 工具 Schema 会进入模型可见的输入上下文，并处在生成本轮回复之前；概念上与 system/developer 指令区域相邻。 | 这没有公开所有托管模型、所有端点的逐 Token 序列，也不等于每个 OpenAI API 都采用完全相同的可见串。 |
| OpenAI gpt-oss + Harmony | OpenAI 的公开 Harmony 格式示例为 system message、developer message（指令与 `# Tools` 定义）、user message；工具调用由 assistant header 中的 `to=...` 和控制 Token 表示。 | 🟢 对 gpt-oss 自托管格式，可以直接说：指令/工具定义在对话输入前部，随后是用户消息；工具调用有专用结构。 | Harmony 文档说明 gpt-oss 格式；不能把它直接当成 OpenAI 托管闭源模型的内部 Prompt dump。 |
| Anthropic Messages API | `system`、`tools` 是顶层参数；`messages` 是有序对话数组，且 Messages API 不接受 `role: system` 消息。 | 🟢 API 逻辑层把系统指令与工具定义作为本轮模型请求的配置，消息数组承载对话；system 在 API 语义上是请求级指令。 | API 参数表没有公开 Claude 推理服务内部的精确特殊 Token 字符串与 tools/system/messages 的逐 Token 排列。 |
| Google Gemini API | `systemInstruction`、`tools` 与 `contents` 是请求的不同字段；`contents` 保存对话内容。 | 🟢 API 逻辑层明确把系统指令、工具声明、对话内容分开表达。 | 字段结构不披露 Gemini 内部模型 Token 的完整序列化形式。 |
| DeepSeek API（托管服务） | OpenAI-compatible Chat Completions 使用 `messages` 和顶层 `tools`；system 可作为 `messages` 中的 system role。 | 🟢 API 逻辑层中，system 消息在消息数组中按请求顺序提供，tools 是独立配置字段。 | 公开 API schema 不等于托管 DeepSeek 模型内部最终串行化格式。 |
| DeepSeek-V3 开放权重 + 官方 HF Tokenizer | `tokenizer_config.json` 的 `chat_template` 先拼接 system 文本到 BOS，之后遍历 user/assistant/tool 对话并输出 DeepSeek 专属标记；还定义 tool call/output 的消息形式。 | 🟢 对这一特定开放权重模型和模板，system 文本确实在对话消息前部。 | 当前模板中看不到 `tools` 参数如何被注入；不能把该模板外推到 DeepSeek 托管 API，也不能据此说工具 Schema 一定就在 system 文本之后。 |

## 用最小图把两层分开

```text
Agent / LangChain
  system_prompt + 当前可用 tools + messages 历史
                 │
                 ▼
Provider API JSON
  厂商定义字段；字段名和字段结构各不相同
                 │ Provider/模型适配
                 ▼
模型专用输入序列
  system/developer / tools / user / assistant / tool
  用该模型的边界与控制 Token 表示
                 │ tokenizer
                 ▼
Token ID 序列 → 模型 Runtime
```

一个开源模型例子（只作格式示意，不代表所有模型）：

```text
<｜begin▁of▁sentence｜>固定 system 文本
<｜User｜>用户消息
<｜Assistant｜>模型回复
```

DeepSeek-V3 的官方 Tokenizer 模板会这样排 system 与对话；OpenAI Harmony 的 token 名称和结构则不同，例如 `<|start|>`、`<|message|>`、`<|call|>`。所以不要把 `<|im_start|>` 当成通用厂商协议。

## 对前一轮缓存学习的意义

虽然不同 API 会把工具定义放在各自字段中，但 Provider/模型适配最终可能把工具定义放进前置输入。因此，“Agent 配置长时间不变”有利于保持请求稳定，却不等于 tool schema 只发送一次。若 Context 顺序发生变化，是否影响缓存要看具体 Provider 的内部序列化与 Cache Usage；托管 API 无法仅凭 LangChain 调用代码证明命中。

还有一个安全边界：Prompt 中写“不要调用某工具”是对模型的指导；工具是否真的可执行、是否需要审批，仍应由 Harness / Runtime 权限代码控制。

## 学习结论与未确认项

- 🟢 **已验证（API 文档）**：Anthropic、Gemini、DeepSeek 的 API 字段组织不同；不存在跨厂商统一的 `system_prompt → tool_schema → messages` 请求顺序。
- 🟢 **已验证（厂商文档）**：OpenAI 文档明确工具定义注入模型 system message；OpenAI gpt-oss Harmony 又公开了该开源模型的确切消息结构。
- 🟢 **已验证（模型文件）**：DeepSeek-V3 开放权重的官方 Tokenizer 配置公开了其特定 chat template，system 文本先于对话消息。
- 🟡 **待核实**：各托管模型 Provider 内部工具 Schema 的逐 Token 编码和精确位置，多数没有官方公开信息。
- 🔴 **未运行验证**：没有抓包、运行本地模型或向厂商 API 发请求观察实际 Token ID；这里依据公开规范/模型文件，不是运行时采样。

## 资料

- [LangChain Agent 创建与模型调用](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain Context Engineering：Agent Loop](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangChain 动态限制工具的 Middleware](https://docs.langchain.com/oss/python/langchain/tools)
- [OpenAI Function Calling：工具进入 System Message 的说明](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI Harmony 格式（gpt-oss）](https://github.com/openai/harmony/blob/main/docs/format.md)
- [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages/create)
- [Gemini GenerateContent API](https://ai.google.dev/api/generate-content)
- [Gemini Function Calling 工具流程](https://ai.google.dev/gemini-api/docs/tools)
- [DeepSeek Chat Completions API](https://api-docs.deepseek.com/zh-cn/api/create-chat-completion)
- [DeepSeek-V3 官方 Tokenizer 配置](https://huggingface.co/deepseek-ai/DeepSeek-V3/blob/main/tokenizer_config.json)
