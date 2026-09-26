# CodeWhale（原 DeepSeek-TUI）

> 调研快照：2026-09-26。官方仓库曾用名 DeepSeek-TUI；本文记录其公开 Prompt/cache 设计，不把产品设计意图当成命中率实测。固定源码学习应按 Change 中指定版本与 commit 复核。

## System prompt 与 tools

- `crates/tui/src/prompts.rs` 按相对稳定程度组装模式 Prompt、workspace context、Skills 以及 context-management/compaction 指令，并标出 volatile boundary。
- MCP 工具定义与 Prompt 里的工具说明/catalog 应分开追；仅从 Prompt builder 不能判断所有 tool schemas 在请求中的位置。
- 配置允许选择技能目录和 MCP 配置路径；MCP 配置变更后，重建 model-visible tool pool 需要重启 TUI（按当前官方配置说明）。

## 静态与动态

| 内容 | 相对生命周期 | 变化与缓存观察点 |
|---|---|---|
| 模式基础 Prompt、稳定 tool catalog | 会话期间相对固定 | 维持可重复前缀；模式/工具变化可能改变前缀。 |
| workspace instructions、Memory、session goal | 易变上下文 | 设计上位于 volatile boundary 后，通过后续 relay/update 更新。 |
| Skill 目录/内容 | 配置或技能更新周期 | 被 Prompt builder 纳入的内容改变会影响相应位置后的前缀。 |
| 历史、工具调用/结果 | 每轮追加 | 追加后保留旧输入前缀的机会由 Provider cache 规则决定。 |

## Skills 与 Memory 对缓存的影响

- **Skill**：配置可指定 `skills_dir`；每个 Skill 以含 `SKILL.md` 的目录组织。Prompt builder 会把 workspace 级 Context、Skill 信息放进 prompt 结构。应核对进入 prompt 的究竟是 Skill 列表、全文还是按需读取内容，并观察技能文件变化如何越过 stable prefix。
- **Memory**：当前配置说明中 Memory 默认关闭。开启后，TUI 将用户 Memory 文件放入 `<user_memory>` prompt block，并同时开放快捷捕获、`/memory` 命令和 `remember` 工具。即 Memory 同时有“被注入的状态”和“更新记忆的工具”两面。
- **缓存观察点**：Memory 文件编辑、Skill 变更和 MCP 工具池重建均可能触发不同范围的输入变化；volatility boundary 只有在实际请求中与缓存累积前缀相符才有意义。记录 `/cache stats` 的 provider hit/miss telemetry，并将它与具体更新事件关联。
- **关键取舍**：将 Memory/goal 作为边界后的增量可减少稳定前缀被改写，但会话消息仍会随更新追加；要确认实际 relay 如何表达更新、是否引入重复或过期上下文。

## 本轮结论

CodeWhale 对本章特别有价值，因为它把稳定区、易变边界和缓存观测都做成显式设计。Skills、Memory、MCP 都是会改变上下文或工具集合的动态来源，必须一起纳入缓存控制，而不能只固定基础 system prompt。

## 官方资料与源码入口

- [Prompt 组装源码](https://github.com/codrstudio/code-whale/blob/main/crates/tui/src/prompts.rs)
- [缓存与遥测配置](https://github.com/codrstudio/code-whale/blob/main/docs/CONFIGURATION.md)
- [Prompt Cache 设计说明](https://github.com/Hmbown/CodeWhale/blob/main/docs/CACHE.md)
- [CodeWhale Releases](https://github.com/Hmbown/CodeWhale/releases)

## 待继续核验

固定 release/commit 后沿 Prompt builder → Skill/Memory 读取 → tool pool → Provider 请求 → cache usage 读取完整追踪；验证变更前缀/后缀及 `prompt_cache_hit_tokens`、miss telemetry 的对应关系。
