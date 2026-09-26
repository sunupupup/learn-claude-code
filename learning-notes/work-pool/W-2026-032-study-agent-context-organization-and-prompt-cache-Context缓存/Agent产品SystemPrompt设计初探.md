# Agent 产品 System Prompt 设计初探

## 学习目标

本章从 Agent 代码中的 `system_prompt` 出发，追踪应用侧怎样把它与工具定义、会话历史及动态上下文组装成一次完整的模型调用，再看哪些部分在相邻调用间稳定、怎样影响 Prompt Cache。这里的结论是对项目当前 `main` 分支的文档/源码初读；正式源码学习时仍要固定版本和 Commit。

```text
System Prompt 来源和分段
  → tools / schema 配置
  → thread 中恢复的 messages 历史 + 本轮输入
  → middleware 动态修改与 Context 组装
  → Provider adapter 的请求对象
  → 稳定前缀 / 动态后缀 / 缓存观测
```

厂商内部的 Chat Template 和 Token 顺序是这条链路的后段边界。若托管厂商没有公开内部模板，本章就停在公开 API 请求和 Usage 指标，不反推私有格式。

## 先校准一个词

**System Prompt（系统提示词）**：传给模型的高优先级指令，属于应用/Harness 到模型 API 的请求内容。Agent 产品里人们常把“整个模型输入上下文”都叫 system prompt，但代码中项目规则、文件内容、工具定义和对话历史可能分别位于 system/developer 消息、user 消息、独立工具 Schema 或历史消息中。读代码时要追踪它们最终进入请求的哪一部分。

## API 字段不等于模型内部的 Token 顺序

你的直觉是：Harness 调用类似 `llm_call(system_prompt, tool_schema, messages)`，SDK 再把它们转成带角色标记的模型输入。这抓住了“结构化输入最后会变成模型可处理序列”的方向；需要修正的是：API 字段布局不等于通用的内部拼接顺序。

```text
Agent / Harness
  → SDK 按 Provider API 组织 JSON 请求
  → Provider 解析 system / tools / messages 等字段
  → Provider 或模型聊天模板（chat template）将结构转换成模型专用输入
  → Tokenizer 转成 Token ID，Runtime 执行推理
```

例如，本仓库 s10 的教学调用接近 Anthropic Messages API：`system`、`messages`、`tools` 是分别命名的请求参数。DeepSeek Chat Completions 则把 system 指令写成 `messages` 数组中 `role: "system"` 的一条消息，同时 `tools` 是独立字段。因此，`system_prompt → tool_schema → messages` 不是通用 API 约定。

模型实际收到的顺序也不能仅从 SDK 函数的参数顺序推导。JSON 对象的字段顺序通常不表达消息先后；`messages` 数组内部的排列才明确承载对话先后。Provider 可以把工具 Schema 编码到模型要求的位置或结构中。使用本地模型时，聊天模板可能把结构化输入渲染为类似下面的文本，再由 Tokenizer 编成 Token ID：

```text
<|im_start|>system
...system instructions...<|im_end|>
<|im_start|>user
...user message...<|im_end|>
<|im_start|>assistant
```

这只是某类模板的示意，不代表所有模型都使用这些标记或都把工具 Schema 放在同一个位置。可见拼写是特殊 Token 的人类可读表示之一；实际推理通常以 Token ID 序列运行。托管 API 的内部模板也可能不向调用者公开。

| 层次 | 传递/处理的内容 | 顺序由什么决定 |
| --- | --- | --- |
| Harness 与 SDK API | 命名字段和结构化消息，例如 `system`、`tools`、`messages` | 对应 Provider 的 API 定义；SDK 参数书写顺序不代表模型顺序 |
| Chat template（聊天模板） | 把消息、角色、工具等渲染成模型训练时采用的对话格式 | Provider 或具体模型/Tokenizer 的模板 |
| Tokenizer / Runtime | Token ID 序列与推理状态 | 模型词表、特殊 Token 和推理实现 |

资料：本仓库 [s10 教学调用](../../../s10_system_prompt/code.py)；[Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)；[DeepSeek Chat Completions API](https://api-docs.deepseek.com/zh-cn/api/create-chat-completion)；[Hugging Face Chat Template 文档](https://huggingface.co/docs/transformers/chat_templating)。

## 三个项目的初步观察

| 项目 | 设计方式 | 可学习点 | 当前证据边界 |
| --- | --- | --- | --- |
| CodeWhale（原 DeepSeek-TUI） | 将 Constitution（基础行为准则）、语言规则和输出规则分层组装；再接入项目上下文、环境、指令和 Skill。注释说明较稳定的块放前面，易变内容放后面。工具是否可用由工具目录与执行层控制，不靠不同模式的 Prompt 文本授权。 | 将稳定规则与易变 Context 分开；明确 Prompt 指令与 Runtime 权限的边界；考虑前缀复用。 | 初读当前 `main` 的 `prompts.rs`；与本章计划固定的 v0.10.0 不一定相同。分层和顺序是源码设计证据，实际缓存效果尚未运行验证。 |
| Aider | 按编辑模式提供专门的 `main_system`。EditBlock 模式告诉模型接受哪些代码变更请求、文件不在对话中时先请求用户添加、并严格使用 Search/Replace 区块。Repo map 和文件正文另作为 user/assistant 消息加入对话。 | System Prompt 不只是身份人设；它可以定义产品工作流和机器可解析的输出协议。输入上下文也不都塞在 system 消息里。 | 初读当前 `main` 的 Prompt 与消息组装源码；其他 coder 模式会有各自设计，正式对比需固定版本。 |
| Goose | 用模板构造通用 Agent 指令；根据运行模式动态插入 Extensions 及其说明。Prompt 代码还注册 compaction、subagent、权限判断等不同用途的模板，并允许用户覆盖模板。 | 核心指令、动态扩展信息和专用子任务模板分开维护；Context 可以按当前启用能力生成。 | 初读当前 `main` 的模板源码；不同 Provider 路径和运行模式是否都使用同一模板，需要进一步跟调用链。 |

## 当前可用的观察框架

读 Agent 的 System Prompt 时，按这五个问题做标记：

1. **要约束什么？** 身份、行为准则、任务流程、工具使用方式，还是输出格式？
2. **来自哪里？** 编译进程序的常量、用户配置、项目文件、当前环境，还是动态启用的 Skill/Extension？
3. **放在哪里？** System Prompt、其他消息、工具 Schema，还是 Runtime 状态？
4. **何时变化？** 跨会话稳定、会话固定，还是每轮/每次工具调用都会变化？
5. **谁负责强制？** 模型指令只是引导；工具授权、审批、路径限制等还要由程序执行层落实。

这和已学 s10 的关系是：`context → 选择/填充 Prompt section → 组装 system prompt` 是教学代码中的基本模型；产品源码还要继续追踪文件、配置、工具和消息怎样被组装为真实 API 请求。再往后才看稳定前缀对 Provider 缓存的影响。

## 初步结论

- 🟢 **文档/源码已验证**：所观察的 Agent 并不是只有一条固定人设文案；至少有按模式或状态组合的指令片段。
- 🟢 **文档/源码已验证**：System Prompt 与模型可见的全部 Context 不是同义词。Aider 的 repo map/文件内容可以作为普通对话消息加入。
- 🟢 **文档/源码已验证**：Prompt 中的“不要做某事”不等于程序真的拦截了该动作；应找到工具目录、授权和执行逻辑。
- 🟡 **待进一步核验**：哪种分层方式更有效，要用代表性任务和模型评测验证，不能从 Prompt 写得详细就推断 Agent 更可靠。
- 🔴 **尚无运行证据**：本笔记没有运行这些项目或比较其行为，也没有在固定版本上对照实际发送给 Provider 的完整请求。
- 🟢 **已验证理解（API/模型输入边界）**：`system/tool_schema/messages` 可作为 Harness 的概念抽象；具体 Provider API 字段布局不同，模型专用 Token 顺序由 Provider/聊天模板决定，不能仅按 SDK 调用参数顺序猜测。

## 资料入口

- [CodeWhale Prompt 组装源码](https://github.com/Hmbown/CodeWhale/blob/main/crates/tui/src/prompts.rs)：分层顺序、稳定与易变内容、工具权限边界。
- [CodeWhale 配置说明](https://github.com/Hmbown/CodeWhale/blob/main/docs/CONFIGURATION.md)：项目/用户指令文件加载与安全边界。
- [Aider EditBlock Prompt](https://github.com/Aider-AI/aider/blob/main/aider/coders/editblock_prompts.py)：代码编辑任务的流程与输出格式契约。
- [Aider 消息组装](https://github.com/Aider-AI/aider/blob/main/aider/coders/base_coder.py)：repo map 与文件内容如何进入聊天消息。
- [Goose 主 System Prompt](https://github.com/aaif-goose/goose/blob/main/crates/goose/src/prompts/system.md)：模板中的 Extension 条件块。
- [Goose Prompt 模板管理](https://github.com/aaif-goose/goose/blob/main/crates/goose/src/prompt_template.rs)：内置模板、专用模板与用户覆盖入口。
