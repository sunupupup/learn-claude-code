# Codex CLI

> 调研快照：2026-09-26。基于公开仓库初读；正式源码学习时固定 release/commit，并追到实际模型请求。

## System prompt 与 tools

- **基础指令**：`codex-rs/protocol/src/prompts/base_instructions/default.md` 定义 coding agent 的基本行为。工作区 `AGENTS.md` 是额外项目指令，进入 Context 组装链。
- **工具**：内建工具与 MCP 工具共同构成模型可用能力。MCP 客户端发现 tool schema 后交给运行时处理；可见工具定义、工具执行实现、授权/审批是不同层次。
- **已知边界**：已经找到基础指令、MCP schema 和工具运行时入口；尚未完整追完某一次 Responses 请求中的最终顺序与序列化。

## 静态与动态

| 内容 | 相对生命周期 | 变化与缓存观察点 |
|---|---|---|
| 基础指令、内建工具 | 发版/配置周期 | 无变化时可重复；模板或工具定义改版会改变后续请求前缀。 |
| `AGENTS.md` | 工作区/项目配置 | 内容、层级或工作目录改变时重新发现；检查是否导致 Prompt 改写。 |
| MCP tools | 连接/发现/权限周期 | server 返回的名称、描述、schema 变化会改变 tool set；观察何时刷新。 |
| 会话 messages、工具结果 | 每轮追加 | 追加历史一般保留此前完全相同的前缀；编辑/压缩历史需单独检查。 |

## Skills 与 Memory 对缓存的影响

- **Skill**：Codex 源码仓库包含 skills 支持及相关指令资源。Skill 是可加载的工作指令/资源，不应和基础 Prompt 或 callable tool 混为一谈。当前初读尚未确认每种 Skill 加载路径把目录、正文分别放进哪一次模型请求；需要追 Skill discovery/load → Context 注入 → model call。
- **Memory**：Codex 仓库有独立 memory read/write 子系统；read 路径负责 Memory developer-instruction 注入和使用遥测。文件系统中的记忆与发给模型的记忆指令不是同一件事，注入范围和刷新时机还需沿运行时代码核实。
- **缓存观察点**：若 Skill 正文或 Memory 作为 developer/system 指令发送，修改它们可能改变其所在位置之后的前缀；若只在触发时以消息/工具结果追加，则影响范围不同。不能根据“有 Skill/Memory 功能”直接推断它们每轮都进入请求。
- **安全边界**：Memory 或 Skill 的内容不能替代 MCP/工具的授权判断；应将模型可见说明与 Runtime 执行权限分开观察。

## 本轮结论

当前能确认产品有基础指令、项目指令、动态工具发现、Skill 与 Memory 子系统的入口；尚不能确认它们全部进入一次请求的准确顺序、是否稳定复用或缓存命中效果。把这点标为待源码追踪，而不是推测。

## 官方资料与源码入口

- [Codex CLI 仓库](https://github.com/openai/codex)
- [基础指令](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/prompts/base_instructions/default.md)
- [MCP 客户端](https://github.com/openai/codex/blob/main/codex-rs/codex-mcp/src/rmcp_client.rs)
- [工具上下文运行时](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/context.rs)
- [Memory 子系统说明](https://github.com/openai/codex/blob/main/codex-rs/memories/README.md)
- [Codex Skills 官方介绍](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)

## 待继续核验

固定版本后沿着 prompt builder、Skill 加载、Memory read、MCP refresh 到 Provider 请求追踪，并比较首轮、追加工具结果、Skill 激活、Memory 更新四种相邻请求的输入差异。
