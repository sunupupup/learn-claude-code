# C-2026-013：Agent Context 组织与 Prompt Cache 命中学习

- Status: active
- Area: Agent Harness / Context Engineering / Prompt Cache / Cost & Latency Observability
- Difficulty: D2 → D3；从缓存对象和常见请求链路开始
- Started: 2026-09-25
- Source Task: W-2026-032-study-agent-context-organization-and-prompt-cache（原任务卡已迁入本 Change）
- Learning entry: [总览](../../learning-notes/work-pool/W-2026-032-study-agent-context-organization-and-prompt-cache-Context缓存/LEARNING_NOTES.md)、[知识图谱](../../learning-notes/work-pool/W-2026-032-study-agent-context-organization-and-prompt-cache-Context缓存/Agent%20Context组织与缓存命中知识图谱.md)、[名词清单](../../learning-notes/work-pool/W-2026-032-study-agent-context-organization-and-prompt-cache-Context缓存/名词清单.md)、[开源项目缓存设计：那些子项目](../../learning-notes/work-pool/W-2026-032-study-agent-context-organization-and-prompt-cache-Context缓存/开源项目缓存设计/那些子项目.md)
- Start Trigger: 用户明确要求“构建相关的学习章节”并“开始深入学习”，正式启动本 Work Pool。

## 本次学习范围

理解 Agent 如何组织模型请求的 system prompt、tools 和 messages，以及静态/动态 Context 的生命周期如何影响 Provider Prompt Cache 的可复用前缀。Skill 与 Memory 作为会改变 Prompt、工具集合或消息历史的上下文来源，纳入每个项目的缓存分析。项目对比按 coding agent（Codex CLI、Pi）和个人助手（Hermes Agent、OpenClaw）分组；CodeWhale 用作缓存设计专题，OpenHands SDK 用作 Prompt/Tools 分离的架构专题。各项目只追本 Change 指定的源码链路，不做完整代码库导览；按需补读 DeepSeek、Anthropic 与 OpenAI 官方缓存文档。

主线：

```text
Context 来源与更新频率
  → Harness 选择 / 排序 / 序列化
  → 稳定 Prompt 前缀与缓存边界
  → Provider cache read / write / uncached 指标
  → 命中、成本、延迟与失效原因
```

必学主线覆盖 Provider Prompt Cache 与应用层 Prompt 组装缓存的边界、稳定/动态 Context 编排、Aider 真实请求链路、Goose Provider 适配、命中指标与常见失效/隔离风险。真实 API 实验属于有条件的加深证据，不是理解或完成主线的前提。

## 启动检查与依据

- 前置：s01 Agent Loop 与模型调用；s10 System Prompt Section、Context 快照和应用层组装缓存；W-2026-002 已引入 KV Cache / Prompt Prefix Cache / Context Cache 区分，但仍在学习中，本 Change 不假定其全部内容已掌握。
- 直接关联：W-2026-009 负责广泛的 Context 来源、租户隔离、版本与失效；W-2026-012 研究 Skill 注入及 Token/缓存观测；W-2026-031 负责通用 Trace/Eval。此处只复用边界，不复制完整主题。
- 现有约束：已读取 `specs/README.md`；`specs/current/`、`specs/decisions/` 没有相关新增约束。W-2026-002、W-2026-009、W-2026-012、W-2026-031 与 s10 文档提供前置概念和范围边界。
- 工作区基线：启动前 `git status --short` 显示已有的 `learning-notes/work-pool/README.md`、W-2026-031 学习笔记和新增模块笔记、W-2026-030 学习目录、C-2026-010、C-2026-011，以及主路线中的既有改动。本 Change 只新增本任务文件并迁移 W-2026-032；不覆盖或整理其他改动。主路线里原有 W-2026-031 索引保留。
- 当前资料准备（2026-09-25）：Context7 已查询 Aider 官方文档 `/websites/aider_chat` 和 Goose 官方仓库 `/aaif-goose/goose`；另对照 OpenAI Prompt Caching/Diagnostics 和 Anthropic Prompt Caching 官方页面。它们仅支持文档层面的项目行为与概念导航，不是本机运行或生产性能证据。
- 用户补充怀疑 DeepSeek-TUI 后，核实旧仓库 `Hmbown/DeepSeek-TUI` 已重命名并导向 `Hmbown/CodeWhale`。截至 2026-09-25 当前发布为 v0.10.0（release commit `1be1a70`）；正式源码阅读固定该版本，后续再决定是否查看更早版本差异。
- CodeWhale 官方 `docs/CACHE.md` 描述“固定 system prompt + tool catalog，history 只追加”的 prefix invariant；workspace、AGENTS.md、skills、memory 等漂移通过下一轮追加 bounded `<context_update>`，`/cache stats` 提供 pin/miss reason 和 drift/update 计数。v0.9.8 release notes 记录此设计；这是产品设计主张，不代表每个工作负载的命中率保证。
- DeepSeek API 官方缓存指南称缓存由服务端自动 best-effort 执行，按相同输入前缀尝试复用，并在 Usage 返回 `prompt_cache_hit_tokens` 与 `prompt_cache_miss_tokens`；文档明确不保证 100% 命中。网上 90%–98% 比例属于特定使用者、版本和工作负载的会话测量或自报，不能外推为 CodeWhale 的产品承诺或普遍性能。
- Aider 文档称其缓存目标包括 system prompt、只读文件、repo map 和已加入对话的可编辑文件；缓存统计/费用在 streaming 下不可见，并提供 keepalive 选项。Goose 文档称 Claude 模型经 Anthropic、Bedrock、Databricks、OpenRouter 和 LiteLLM 等 Provider 时会加入 `cache_control` 标记。正式源码学习时仍需固定 Commit 并核实实现。
- OpenAI 现行文档提供缓存 Token 指标与诊断入口，但支持范围和参数是版本相关的；不得将其字段、TTL 或 Provider 路由行为直接推广到 Aider、Goose 或 Anthropic。

## 学习建议与项目选择

1. 按两组各比较两个项目：Codex CLI + Pi（coding agents）；Hermes Agent + OpenClaw（个人助手）。CodeWhale 与 OpenHands SDK 分别作为窄范围案例。每个项目独立维护一个 Markdown 调研页；总表只作索引。每页记录 system prompt / tools 放在哪里、有哪些内容、哪些静态/动态、何时重建，以及 Skill / Memory 从发现、快照或按需加载到进入模型请求的路径和缓存影响。
2. 用 CodeWhale 对照显式 stable-prefix / volatile-boundary 设计；用 OpenHands SDK 对照静态 system prompt、动态 Context 与 ToolDefinition 的结构分离。
3. 从项目源码继续追模型请求边界：Prompt builder → 工具注册/发现 → tool schema 生成 → Provider request adapter。不同项目标记为 `documented` / `source-verified` / `observed-runtime`，不把源码推论混成运行事实。
4. 用 DeepSeek、Anthropic 与 OpenAI 官方文档校准缓存前缀/指标差异。先明确指标口径，再决定是否需要真实调用；未获用户明确要求前，不使用付费 API。

推荐项目：

| 项目 | 本章用途 | 建议观察点 |
| --- | --- | --- |
| Codex CLI | Coding Agent 主读之一 | Base instructions、AGENTS.md、内建/MCP tools、tool specs 与请求构造 |
| Pi Coding Agent | Coding Agent 主读之一 | Prompt section builder、SYSTEM/APPEND_SYSTEM、工具清单与 schema、Skills/Extensions、cache warming |
| Hermes Agent | 个人助手主读之一 | Prompt tiers、会话内缓存 Prompt、memory/skills/context snapshot 与临时 overlays |
| OpenClaw | 个人助手主读之一 | 每次 run 的 Prompt 组装、tool list、Skills metadata/on-demand body、memory tools 与 workspace files |
| CodeWhale（原 DeepSeek-TUI） | 缓存设计专题 | stable prefix、volatile boundary、Prompt/tools 分界和 cache telemetry |
| OpenHands SDK | Context 结构专题 | static/dynamic system content blocks、ToolDefinition、Memory/Skills/MCP 入口 |
| Goose | 暂作已读参照，不纳入本轮主读 | Extension 同时包含 tools 与 prompt 指令；需要讨论工具扩展与 Provider cache_control 时再回看 |

## 第一小步

先回答“缓存命中的到底是什么”。拿两个多轮请求作图：固定 system/tool 定义和既有历史；第二次只追加一条新 user 消息。先区分文本相似、本地 Prompt 字符串缓存、Provider 可复用前缀和 Runtime KV Cache；暂不要求猜任何 Provider 是否命中。第一步验收是用户能够用自己的话说明四者处于哪一层、缓存对象分别是什么，并指出后续需要何种证据才能确认真实命中。

## 后续记录

用户原始理解、概念校准、源码调用链、实验输入/输出和掌握状态只记录在 [学习总览与模块笔记](../../learning-notes/work-pool/W-2026-032-study-agent-context-organization-and-prompt-cache-Context缓存/LEARNING_NOTES.md) 及其子笔记中，不在本 Change 重复维护。正式源码阅读时记录 Commit、路径和行号；实验结论区分 `source-verified`、`documented`、`observed-runtime` 和 `production-proven`。

## 验收与遗留

完成时按迁移自 W-2026-032 的 Success Criteria 验收。真实 Provider 指标若无法取得，明确保留为“未验证运行命中”；不以静态代码或 Mock 结果替代。无代码实现时不创建空的 Implementation 记录。
