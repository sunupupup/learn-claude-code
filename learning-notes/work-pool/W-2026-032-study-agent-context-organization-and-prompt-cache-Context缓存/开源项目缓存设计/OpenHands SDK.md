# OpenHands SDK

> 调研快照：2026-09-26。基于 OpenHands Software Agent SDK 文档、源码与示例初读；不等同于 OpenHands 所有产品部署行为。

## System prompt 与 tools

- Agent 用 Jinja2 模板生成静态 system prompt；`SystemPromptEvent` 将静态 Prompt 和动态 Context 分别保存为 system message 的不同 content block。
- 动态 Context 可由 `AgentContext` 与 conversation state 构建，也可含会话 secrets；源码注释说明将它放在第二个 block、不加 cache marker，是为跨会话复用静态 Prompt。
- Tools 以 `ToolDefinition` 独立保存，并在 LLM completion 时转换成 Provider 所需格式；不是全部拼成 Prompt 字符串。

## 静态与动态

| 内容 | 相对生命周期 | 变化与缓存观察点 |
|---|---|---|
| 模板渲染出的静态 system prompt | Agent 配置/版本周期 | 稳定块适合跨会话复用；模板/参数变化会改变前缀。 |
| AgentContext 动态块 | 会话状态/初始化时 | Memory、secrets 等更新可能改变第二块；检查更新是否重建事件。 |
| ToolDefinition | Agent/tool 集合 | 工具选择或风险字段变化会改变独立工具输入。 |
| messages、工具结果 | 每轮追加 | 观察 conversation state 转换及 compaction。 |

## Skills 与 Memory 对缓存的影响

- **Skill**：SDK 的 Skill 架构根据触发条件把专门指令注入 Agent Context；可在渲染时执行受控动态命令，也可为 repo Skill 配置 MCP tools。Skill 因而可能同时改变 prompt content 和可用 tool set；不能将“Skill 正文变化”与“工具 schema 变化”合并成一个缓存事件。
- **Memory**：官方持久 Memory 示例通过 `AgentContext(load_memory=True)` 在新会话启动时读取用户/项目 `MEMORY.md` 索引，作为 `<MEMORY_CONTEXT>` 放入动态 Context；Memory 默认关闭。旧会话中的动态块与磁盘最新内容是否一致，要看会话何时初始化或重建。
- **缓存观察点**：这个设计把静态 system block 与动态 context block 分开，使 Memory/Skill 更新理论上不必改写静态前缀；但是否保留缓存还取决于 Provider adapter 如何编码多个 content blocks、tool schemas 与 cache marker。源码注释表达的是设计目标，不是运行命中率证据。
- **安全边界**：动态 Context 可包含 secrets；不要把它们误当静态 Prompt，避免缓存/日志策略使敏感内容超出预期生命周期。

## 本轮结论

OpenHands SDK 展示了三种要分别追踪的东西：静态 Prompt block、动态 Context block、独立 ToolDefinition。Memory/Skill 会影响后两者或扩展工具集合，但静态块能否跨会话缓存，仍需查具体 Provider 请求路径。

## 官方资料与源码入口

- [Agent 初始化与静态/动态 Context](https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/agent/agent.py)
- [SystemPromptEvent 转换](https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/event/llm_convertible/system.py)
- [Skill 架构说明](https://github.com/OpenHands/docs/blob/main/sdk/arch/skill.mdx)
- [持久 Memory 示例](https://github.com/OpenHands/software-agent-sdk/blob/main/examples/01_standalone_sdk/55_persistent_memory.py)

## 待继续核验

固定版本后追 Skill trigger/渲染 → AgentContext → SystemPromptEvent → Provider completion 的完整路径；验证每个 Provider 对动态 block、工具定义和缓存标记的处理。
