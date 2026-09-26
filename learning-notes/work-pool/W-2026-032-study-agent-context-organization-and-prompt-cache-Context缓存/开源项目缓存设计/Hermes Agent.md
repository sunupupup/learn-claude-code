# Hermes Agent

> 调研快照：2026-09-26。依据 Hermes 官方 Prompt Assembly 文档与公开源码初读；各 section 归属以固定版本源码为准。

## System prompt 与 tools

- `agent/system_prompt.py` 构造 system prompt parts；官方文档将其分成有序的 `stable → context → volatile` 三层。
- 稳定层包含身份和通用工具/模型指导；context 层包含调用方 system message、项目上下文文件和 workspace snapshot；volatile 层包括 Skill 索引、Memory/User profile 快照、时间和运行环境信息。
- 另有 API-call-time 临时 Context 路径；它的设计目的是不必改写会话复用的 system prompt。
- 工具从有效工具集构造为模型可见定义；MCP、会话恢复和压缩可能影响可用集合或重新构建请求。

## 静态与动态

| 内容 | 相对生命周期 | 变化与缓存观察点 |
|---|---|---|
| 身份/通用规则 | 版本或配置周期 | 稳定主体。 |
| 项目文件与 workspace snapshot | 会话构建/工作区变化 | 检查读取快照时机和重建条件。 |
| Skill 索引、Memory、User profile、时间/runtime | Prompt volatile tier | 文档称其作为缓存 system prompt 的组成部分；volatile 命名不表示每轮必定重新读取。 |
| API-call-time overlay | 单次调用 | 看它在 Provider 请求里如何与缓存的 system prompt 分离。 |
| 历史和工具结果 | 每轮追加/压缩 | 追加可保留旧前缀；压缩会走显式重建路径。 |

## Skills 与 Memory 对缓存的影响

- **Skill**：Prompt Assembly 文档将 Skill 索引列入 volatile tier。索引和 Skill 正文要分开看：目录/描述可作为发现提示；技能被选中后是否把完整正文直接注入 system prompt、何时重建，需沿 Skill loader/tool 调用确认。
- **Memory**：内建 `MEMORY.md`、`USER.md` 和外部 memory provider block 被列入 volatile tier。官方文档同时说明 system prompt 会在会话内构建并复用；因此 Memory 来源可变化，但本轮已缓存的 prompt 未必自动跟着存储更新，通常要看 session 初始化/压缩等重建路径。
- **缓存观察点**：分层标签表达组装位置或变化属性，不足以推出刷新频率。记录快照创建时间、会话复用范围和临时 overlay 的请求位置，才能判断前缀何时变。
- **一致性边界**：为了缓存而复用旧 Memory snapshot 可能降低事实新鲜度；需明确何时刷新、何时重建，而不能只追求前缀相同。

## 本轮结论

Hermes 最值得观察的是“volatile 数据仍可在会话生命周期内快照化”这一点。动态来源不必然意味着每轮重写 system prompt；缓存复用和 Memory 新鲜度之间存在明确的生命周期取舍。

## 官方资料与源码入口

- [Hermes Prompt Assembly 文档](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)
- [System prompt 组装源码](https://github.com/NousResearch/hermes-agent/blob/main/agent/system_prompt.py)
- [Prompt builder 源码](https://github.com/NousResearch/hermes-agent/blob/main/agent/prompt_builder.py)
- [Memory 工具入口](https://github.com/NousResearch/hermes-agent/blob/main/tools/memory_tool.py)

## 待继续核验

固定 release/commit 后逐段核对各 tier 内容、Skill 正文加载路径、external memory provider 的注入点、工具定义何时快照，以及 session resume/compaction 是否重建 Prompt。
