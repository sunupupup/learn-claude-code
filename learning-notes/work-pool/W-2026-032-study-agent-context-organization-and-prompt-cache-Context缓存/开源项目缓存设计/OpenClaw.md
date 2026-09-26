# OpenClaw

> 调研快照：2026-09-26。基于 OpenClaw 官方文档初读；运行配置可能改变哪些文件和技能进入请求。

## System prompt 与 tools

- OpenClaw 在每次 Agent run 组装 system prompt；基础提示、当前工具简述、Skill 目录、workspace/bootstrap 文件、时间和 runtime metadata 都可能参与。
- Prompt 中的工具简述给模型导航；实际 callable tool schema 由 core/plugin/runtime 组装。Prompt 提到某工具并不授予执行权限。
- bootstrap 文件有单文件和总量上限；不同 agent、workspace 和插件配置会改变有效上下文。

## 静态与动态

| 内容 | 相对生命周期 | 变化与缓存观察点 |
|---|---|---|
| 核心 Prompt 骨架 | 版本周期 | 版本升级时变化。 |
| 工具摘要和 tool schema | 每次 run 按有效能力构造 | 插件/MCP 配置、权限或技能关联工具变化时可能改变。 |
| Skills 目录块 | 每次 run 按当前有效技能构造 | 文件、allowlist、环境门控、优先级变化会改变目录。 |
| bootstrap 文件和 Memory | workspace 状态/每次 run | 文件内容改变或截断策略触发时会改变注入文本。 |
| 时间/runtime 信息 | 每次 run | 天然易变，需查它在 Prompt 中的位置和 Provider 前缀规则。 |
| messages、工具结果、按需 Skill/Memory 读取结果 | 对话运行期间 | 通常沿历史追加；重试、压缩、重建要单独追踪。 |

## Skills 与 Memory 对缓存的影响

- **Skill**：官方文档说明有效 Skills 会以紧凑 XML 目录进入 system prompt，目录主要包含元数据；完整 `SKILL.md` 在需要时由 `read` 工具按需加载。Skills 的有效集合会经过来源优先级、配置、allowlist 和环境门控计算，因此插件或目录变化可能改变常驻 Prompt。描述应简短，既控制 token 成本，也减少不必要的前缀变化。
- **Memory**：正常路径下，workspace 的 `MEMORY.md`（存在时）作为 bootstrap context 注入；`memory/*.md` 日记通常通过 Memory tools 按需检索。部分 Native Codex 路径在 Memory tools 可用时只注入 pointer，不直接粘贴整个 `MEMORY.md`；这是特定运行路径，不能推广到所有 harness。
- **缓存观察点**：Skill metadata 和 bootstrap Memory 若每次 run 重算，其内容/顺序稳定性决定已有前缀能否复用；按需读出的 Skill/Memory 则在调用之后新增上下文。对比冷启动、普通连续轮、Memory 检索轮和重置/压缩轮。
- **安全边界**：Skill 环境变量和密钥注入属于运行时环境，不应误当成 Prompt 文本；秘密不能为了“缓存稳定”而写入 Prompt 或日志。

## 本轮结论

OpenClaw 的重点是“Skill 元数据常驻，Skill 正文按需；部分 Memory 常驻，细节按需”。要观察缓存，必须把每次 run 的重建和输入内容实际是否变化分开。

## 官方资料与源码入口

- [Token 使用与 Prompt Context](https://github.com/openclaw/openclaw/blob/main/docs/reference/token-use.md)
- [Skills 文档](https://github.com/openclaw/openclaw/blob/main/docs/tools/skills.md)
- [Agent 概念与 bootstrap 文件](https://github.com/openclaw/openclaw/blob/main/docs/concepts/agent.md)
- [Agent loop 与 Prompt 组装](https://github.com/openclaw/openclaw/blob/main/docs/concepts/agent-loop.md)

## 待继续核验

固定版本后追每次 run 的最终 system prompt、tool schema、各类 Memory 路径、plugin hooks 对 Prompt 的修改，以及 session continuity/compaction 对旧前缀的保留情况。
