# W-2026-032：Agent Context 组织与 Prompt Cache 命中

## 任务范围与状态

- 状态：已启动；已完成一次前缀命中推演，Provider 前缀缓存的常见场景已验证；本章第一小步其余缓存层次仍待学习。
- 启动日期：2026-09-25。
- 任务范围与验收：见 [C-2026-013](../../../specs/changes/C-2026-013-study-agent-context-and-prompt-cache.md)。
- 学习模式：源码线 + 理论线 + 可选实验线。先建立缓存层次与请求前缀直觉，再读固定版本 CodeWhale（原 DeepSeek-TUI）；Aider 作为 Context 设计对照，Goose 只做 Provider 适配对照。
- 当前固定源码候选：CodeWhale v0.10.0，release commit `1be1a70`（2026-09-22）；正式阅读时再确认仓库/tag 对应关系并固定 Commit。
- 第一手资料：Context7 的 Aider `/websites/aider_chat`、Goose `/aaif-goose/goose` 文档；CodeWhale 官方 `docs/CACHE.md` 和 release notes；DeepSeek API 缓存指南。Provider 细节按官方文档核验。
- 目前只有官方文档资料准备，没有下载第三方源码、运行 Agent 或调用 Provider API 的证据。

## 为什么学习它

从 [s10 System Prompt](../../../s10_system_prompt/LEARNING_NOTES.md) 的 Context 快照和本地 Prompt 组装缓存继续向外看：Harness 不仅需要构造正确 Context，还会影响模型服务端是否能复用请求前缀。它与 [W-2026-002 LLM Runtime](../W-2026-002-study-llm-runtime-foundations-模型运行基础/LEARNING_NOTES.md) 的缓存层次、[W-2026-009 Context 治理](../../../specs/work-pool/W-2026-009-study-system-prompt-production-context-governance.md) 的权限/失效、[W-2026-012 Skill 可观测性](../../../specs/work-pool/W-2026-012-study-agent-skill-engineering-observability.md) 的注入观测相连。

## 学习入口

- [Agent Context 组织与缓存命中知识图谱](Agent%20Context组织与缓存命中知识图谱.md)
- [名词清单](名词清单.md)
- 学习主线：从 Agent 应用传入的 `system_prompt` 开始，沿着一次模型调用追出应用侧组装的完整输入，再分析稳定/动态片段如何影响缓存前缀。先学 Agent 应用侧请求组装，再补 Provider 序列化边界，最后看缓存。
- 学习模块计划：System Prompt 与完整请求的应用侧组装（当前前置）；按 coding agent / 个人助手分组的源码比较；缓存对象与前缀；Context 分块和 Provider 序列化边界；指标口径与失效诊断；生产取舍。模块笔记在实际学习后按主题创建。
- 项目采样计划：[Agent 静态/动态组装与缓存友好设计](Agent静态动态组装与缓存友好设计.md)：深读 Codex CLI + Pi（coding agent）、Hermes + OpenClaw（个人助手）；CodeWhale 只做缓存专项案例，OpenHands SDK 只做 Prompt/Tools/MCP 分离的架构案例。不是六个项目都全量通读；Goose 作为先前参照暂缓扩展。
- 按项目逐步记录的索引：[开源项目缓存设计 / 那些子项目](开源项目缓存设计/那些子项目.md)；每个子项目各有独立 Markdown。每页记录 system prompt/tools 的位置与内容、静态/动态内容及重建时机，并把 Skills、Memory 的发现、注入/按需读取、刷新时机及其缓存影响作为必查项；后续阅读源码再补调用链证据，不提前扩展到缓存指标和实验。
- 已开始的前置学习：[Agent 产品 System Prompt 设计初探](Agent产品SystemPrompt设计初探.md)，此前初步观察 CodeWhale、Aider、Goose；现在按两类 Agent 重组比较主线。
- 厂商序列化调研：[厂商 API 与模型输入序列化对照](厂商API与模型输入序列化对照.md)，比较 LangChain 配置、各厂商公开 API 与开源模型 Chat Template。

### 本章观察起点与问题边界

本章从 Agent 调用代码里的 `system_prompt` 出发，但不把它误当成整次模型输入。学习重点是应用侧如何组装一次 LLM 请求：

```text
create_agent 配置（system_prompt、tools、model）
  + invoke 本轮消息与 thread_id
  → checkpointer 恢复已有会话状态
  → middleware 按需修改 Prompt / 工具 / 状态
  → Agent Loop 组织当前 messages 与可用工具
  → Provider adapter 形成一次 API 请求
  → 检查相邻请求中哪些前缀保持稳定、哪些内容变化
```

厂商内部序列化只用于理解应用输入和 Provider 行为之间的边界；除非有公开模型 Chat Template 或 Provider 文档，不假设能看到托管模型内部逐 Token 的精确布局。
- 已完成的第一个微问题：[缓存命中的前缀与新增后缀](缓存命中的前缀与新增后缀学习笔记.md)。

## 资料入口与当前证据

| 来源 | 用途 | 当前证据边界 |
| --- | --- | --- |
| [Aider Prompt Caching](https://aider.chat/docs/usage/caching.html) | 了解项目试图复用的上下文、缓存开关与保活选项 | 维护者文档；未核验固定 Commit 源码，也未实测 |
| [Aider Options](https://aider.chat/docs/config/options.html) | 查 `--cache-prompts`、`--cache-keepalive-pings` 和 repo map 更新配置 | 文档行为；版本变化时重查 |
| [CodeWhale Prompt Cache 设计](https://github.com/Hmbown/CodeWhale/blob/main/docs/CACHE.md) | pinned prefix、history append、Context drift 更新与 miss 归因 | 官方项目设计文档；源码链路与运行效果待核验 |
| [CodeWhale Releases](https://github.com/Hmbown/CodeWhale/releases) | 固定版本、cache pin 功能的变更背景与 `/cache stats` 入口 | 版本说明；不作为命中率 benchmark |
| [Goose Providers](https://github.com/aaif-goose/goose/blob/main/documentation/docs/getting-started/providers.md) | 确认其公开的 Claude Prompt Cache Provider 范围与 `cache_control` 说明 | 官方仓库文档；不是当前运行遥测 |
| [DeepSeek Context Caching](https://api-docs.deepseek.com/guides/kv_cache/) | 服务端自动缓存、hit/miss token 字段与 best-effort 边界 | Provider 官方文档；具体字段按当前 API 核验 |
| [Anthropic Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) | 核验 Anthropic 专有的缓存断点、TTL、Usage 与费用 | Provider 文档；参数不可外推至其他 Provider |
| [OpenAI Prompt Caching](https://developers.openai.com/api/docs/guides/prompt-caching) | 对照缓存 Token 指标、统计与诊断能力 | 当前官方 API 文档；支持模型和字段可能更新 |
| [OpenAI Prompt Cache Diagnostics](https://developers.openai.com/api/docs/guides/prompt-caching/diagnostics) | 了解单请求比较与 miss 原因诊断 | Provider 专属、模型/接口支持范围受限 |

启动期文档核对（2026-09-25）：Aider 文档列出的缓存内容包括 system prompt、只读文件、repo map 和已加入对话的可编辑文件；文档提示 streaming 时看不到缓存统计/成本，提供周期 ping 保持缓存。Goose 文档描述在若干 Claude Provider 路径中添加 `cache_control`。这些是 `documented`，尚未成为 `source-verified` 或 `observed-runtime`。

### 用户提出的 DeepSeek-TUI 产品线索

用户记忆中的 DeepSeek-TUI 很可能是 Hmbown 的终端编码 Agent；官方仓库现已重命名为 CodeWhale。官方发布说明显示，项目采用 session 内固定 system/tool 前缀、历史追加、Context 漂移通过 bounded `<context_update>` 注入，并提供 `/cache stats` 解释 miss 和更新原因。这个设计足够让它成为本章主源码案例，但“高命中率”仍要以固定会话数据与 DeepSeek Usage 指标核实。

DeepSeek 官方说明服务端缓存自动运行、按前缀尝试复用且 best-effort，并提供 hit/miss token 数。网上看到的 90%–98% 属特定用户与工作负载，不是产品承诺。DeepSeek Harness（DSH）是另一个项目，不能与 DeepSeek-TUI/CodeWhale 混称。

## 我的原始理解

> “有些开源 agent 工具，缓存命中率非常高；想看看他们怎么设计、有什么可取之处、怎么观察。”
>
> “这块应该算是缓存命中和 Context 组织方式的知识是吧？”

已完成一次局部校准；完整第一小步仍未完成。待区分：“某项目支持缓存”与“在固定工作负载下测得高命中率”不是同一条证据。

本轮复述：

> “原有前缀 都算是 缓存吧”

🔴 **已验证理解（限常见前缀追加场景）**：新请求保留已持久化且完全匹配的旧前缀时，这段旧前缀可能命中；末尾新追加的工具结果通常是未命中的新输入。DeepSeek 缓存是 best-effort，实际命中范围以响应 Usage 中的 hit/miss Token 数核对。逐条证据与术语解释见[模块笔记](缓存命中的前缀与新增后缀学习笔记.md)。

## 术语速查

详见[名词清单](名词清单.md)。本轮已验证“Provider 前缀缓存的常见追加场景”；其他缓存层次仍待学习。

## 模块索引与掌握状态

| 模块 | 状态 | 证据/入口 |
| --- | --- | --- |
| 缓存对象、层次与稳定前缀 | 🟡 部分掌握 | 已验证 Provider 前缀在“保留旧前缀、末尾追加工具结果”场景中的常见命中范围；本地 Prompt 组装缓存与 Runtime KV Cache 区别、实际 hit 指标仍待学习 |
| Context 分段、排序和动态信息 | 🔴 待学习 | 后续分析 Prompt 构造 |
| CodeWhale pinned-prefix 与 Context drift 链路 | 🔴 待学习 | 固定 v0.10.0 源码后补充笔记 |
| Aider Context 编排对照 | 🔴 待学习 | 按需要固定版本后补充笔记 |
| Goose Provider 适配对照 | 🔴 待学习 | 固定版本源码后补充笔记 |
| Cache Usage、命中率和失效诊断 | 🔴 待学习 | 官方文档与观测证据后补充笔记 |
| 对照实验与生产取舍 | 🔴 待学习/选做 | 是否运行真实 Provider 实验待评估 |

## 下一步

下一步补齐“缓存命中的到底是什么”：对比 Provider Prefix Cache、本地 Prompt 组装缓存和 Runtime KV Cache 各自缓存的对象与所在层；然后再看只追加 User 消息和追加工具结果的两轮请求差异。此前复述只覆盖了 Provider 前缀缓存的一个常见场景，尚不足以判定整个模块掌握。
