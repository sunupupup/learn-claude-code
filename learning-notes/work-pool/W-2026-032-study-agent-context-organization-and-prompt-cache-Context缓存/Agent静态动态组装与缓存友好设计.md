# Agent 的静态/动态组装与缓存友好设计

> 研究快照：2026-09-25。以下按各项目当前公开 `main` 源码/文档初读；分支会变动，正式源码学习时应固定 release 与 commit。本笔记区分“源码明确实现”“文档说明”与“工程推论”，不把设计意图当成缓存命中率实测。

逐项目的独立记录与 Skills/Memory 缓存观察项见[开源项目子项目索引](开源项目缓存设计/那些子项目.md)；本文保留跨项目比较与通用缓存设计提炼。

## 先给结论

成熟 Agent 通常不是把整份 system prompt 写死，也不是每轮随意拼一大段。常见实现是：稳定的基础规则 + 按模式/会话配置渲染的片段 + 本轮上下文；工具则由独立的工具定义与运行时注册表共同决定。关键不是内容是否“动态”，而是**变化频率、变化边界、最终落在请求的哪里，以及变化是否发生在可复用前缀之前**。

`FC` 可以作为“构造请求的函数（request/prompt builder）”的直觉模型，但不一定只有一个函数。真实程序常拆成配置加载、Prompt 模板渲染、Extension/MCP 初始化、memory/skill 选择、消息恢复、Provider adapter 等阶段。建议从模型调用入口沿调用链追，不要只搜一个 `SYSTEM_PROMPT` 常量。

```text
稳定基础规则 ─┐
Agent/模式配置 ├─> Prompt 构造与 Context 选择 ─┐
会话级工具集 ─┘                              ├─> Provider 请求 + 历史 messages
本轮 memory / skill / 环境 / 用户输入 ───────┘
```

## 用生命周期分静态和动态

| 层 | 例子 | 通常何时变化 | 观察重点 |
|---|---|---|---|
| 产品/模型稳定层 | 基础行为规则、输出约定、通用安全边界 | 发版或明确修改配置时 | 是否保持确定性、是否按模型/模式选不同模板 |
| Agent/会话配置层 | mode、启用的 MCP/Extension、工具 schema、项目指令、Skill 目录 | 新会话、重连、配置变化时 | 工具集合是否整会话固定；变化是否导致工具定义或 Prompt 改写 |
| 会话动态层 | 会话 secrets、工作区快照、memory、session goal | 会话初始化或会话中编辑时 | 是否单独分块；是否冻结为快照，何时刷新 |
| 每轮动态层 | 当前 user message、刚读到的文件、检索到的记忆、工具结果、时间/环境状态 | 每轮或每次工具调用 | 是追加到消息历史、放进动态 Prompt 块，还是重写前面的固定内容 |

分类不是绝对属性。例如 memory 文件是动态数据源，但应用可以在会话开始时读取一次并当作“会话稳定快照”；MCP tool schema 在连接期间可能稳定，但重连、工具发现或权限改变时会变。应记录“相对谁、在多长时间内稳定”。

## 项目观察

### 0. 按产品类别组织样本，避免把六个项目都当成同一类 Agent

这章建议分成两个主赛道，每个赛道深读两个项目，再加两个只读一个窄问题的案例：

| 赛道/角色 | 项目 | 为什么选它 | 本轮阅读深度 |
|---|---|---|---|
| Coding Agent | **Codex CLI** | OpenAI 主导的开源终端编码 Agent；适合观察基础指令、项目 `AGENTS.md`、工具和审批/执行层如何配合。 | 主读：system/developer prompt、MCP/工具组装、请求生命周期；缓存行为另看当前模型/API。 |
| Coding Agent | **Pi Coding Agent** | 可组合、可扩展的开源 coding agent；`SYSTEM.md`/`APPEND_SYSTEM.md`、context files、skills、extensions 都有明确用户配置入口。 | 主读：哪些入口替换基础 Prompt，哪些是追加；工具/extensions 怎么进入 Agent。 |
| 个人助手 | **Hermes Agent** | Nous Research 的持续会话型助手；官方 Prompt Assembly 文档和源码详细解释 cache-stable session prompt、memory/skill/context tiers。 | 主读：session prompt 一次构建/复用，动态补充何时进 user message，压缩后怎样重建。 |
| 个人助手 | **OpenClaw** | 多渠道个人助手/编排系统；每次 run 重建 system prompt，但技能只放 metadata、正文按需读；memory 有工具化路径和边界。 | 主读：动态 system 的 token 预算、skill/memory on-demand、插件和 MCP 的扩展边界。 |
| 缓存专项案例 | **CodeWhale（原 DeepSeek-TUI）** | 将“稳定前缀 + volatile boundary + cache telemetry”讲得最直白。 | 窄读：哪些块放边界前/后，缓存 hit/miss 怎么观测；不要求通读全仓。 |
| Context 架构案例 | **OpenHands SDK** | 直接在事件模型中分离 static system prompt、dynamic context 和 tool definitions。 | 窄读：Prompt block、ToolDefinition 和 Memory/Skills/MCP 的接口边界。 |

**这样不会太繁重**，前提是六个项目不做六次完整 codebase tour：Codex/Pi、Hermes/OpenClaw 各成一组做同一张对照表；CodeWhale/OpenHands 各只验证一个特定设计问题。Goose 保留在此前的初步笔记作参照，本轮暂不作为第七个主读对象，因为它与 Extension/Prompt 动态组装主题的重合度较高。

项目定位/入口：[Codex CLI 仓库](https://github.com/openai/codex)、[Pi 仓库](https://github.com/earendil-works/pi)、[Hermes Agent Prompt Assembly 文档](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)、[OpenClaw token use 文档](https://github.com/openclaw/openclaw/blob/main/docs/reference/token-use.md)。

### 1. OpenHands SDK：静态 Prompt 与动态 Context 分成两个 content block

- **🟢 源码证据**：Agent 支持 Jinja2 的 `system_prompt.j2` 模板和模板参数；初始化 `SystemPromptEvent` 时分别填入 `system_prompt`、`dynamic_context`、`tools`。源码注释明确说动态 Context 作为 system 消息里的第二个 content block，且不带 cache marker，目的是让静态 system prompt 能跨会话缓存。动态 Context 会从 `AgentContext` 和 conversation state 构造，也包含 secrets。
- **🟢 数据边界**：工具以 `ToolDefinition` 保存在 Agent 中，在完成 LLM 调用时转成 OpenAI 风格的 tool schema；因此“Prompt 文本”和“工具定义”是两类输入，而不是全塞在同一段 system prompt 里。
- **🟢 Memory 例子**：官方 persistent-memory 示例将项目记忆写入 `MEMORY.md`，新会话将其注入 `<MEMORY_CONTEXT>` 动态块。这说明 memory 的内容可以变化，同时静态 Prompt 块可保持不变。
- **🟡 Skills/MCP**：OpenHands SDK 的 Skills 设计支持按触发条件激活、渲染动态内容，也允许 Skill 配置 MCP tools。需注意这是 SDK 的技能设计/源码证据，不等于所有 OpenHands 产品部署都使用相同路径。
- **值得读**：`Agent.__init__` / `init_state` / `get_dynamic_context` → `SystemPromptEvent` 转换 → LLM completion 将 tools 与消息发给 Provider。重点跟踪何时重新生成 system 事件，而非只读模板正文。

来源：[Agent 初始化与静态/动态 Context](https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/agent/agent.py)、[SystemPromptEvent](https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/event/llm_convertible/system.py)、[持久 Memory 示例](https://github.com/OpenHands/software-agent-sdk/blob/main/examples/01_standalone_sdk/55_persistent_memory.py)、[Skill 架构说明](https://github.com/OpenHands/software-agent-sdk/blob/main/docs/skills-architecture.md)。

### 2. CodeWhale（原 DeepSeek-TUI）：明确的稳定前缀和易变边界

- **🟢 源码证据**：`system_prompt_for_mode_with_context_and_skills` 依照“相对稳定 → 更易变”的顺序拼接：模式 Prompt、工作区级 Context、Skill 目录内容、Context 管理和 compact relay 模板；源码把后续区域称为 volatile boundary。
- **🟢 易变字段位置**：项目 instructions 文件、可编辑 user memory、会话 goal 等放在易变边界之后。memory/goal 改动时，设计目标是仅使后面的 relay 部分失效，保留前面的稳定部分。
- **🟢 可观测性**：配置文档说明 TUI 可展示最近一次 Provider cache hit/miss（若 Provider 返回遥测），并把该遥测用于显示/成本估算；它不用于触发 compaction 或会话重置。这是产品对缓存状态的观测设计，不是一个“命中率必达 90%”的独立基准。
- **🟡 MCP/tool schema**：这里核验到的是 Prompt 组装和缓存观测；不要据此断言所有 MCP schema 都被放在某个 Prompt 区块，也不要将 system prompt 排序等同 Provider 最终序列顺序。
- **值得读**：先读 `prompts.rs` 的组装函数和 volatile boundary 注释，再追工具 catalog / Provider request / cache usage 读取处。当前 `main` 与本章候选 v0.10.0 可能不同，正式学习前固定版本。

来源：[Prompt 组装源码](https://github.com/codrstudio/code-whale/blob/main/crates/tui/src/prompts.rs)、[缓存与 telemetry 配置文档](https://github.com/codrstudio/code-whale/blob/main/docs/CONFIGURATION.md)。

### 3. Goose：Extension 同时改变工具集和 Prompt 内容

- **🟢 源码/文档证据**：Goose 的 `system.md` 是模板；若有已启用 Extensions，就在 system prompt 中渲染每个 Extension 的名称、说明/指令，并说明它提供的工具在 tool specification 中。因此一个 Extension 可以同时带入“工具”和“告诉模型怎样使用它的 Prompt”。
- **🟢 动态配置证据**：Goose ACP schema 允许 session 级 `set` / `append` / `clear` system prompt 文本。`set` 会替换基础 Prompt，`append` 会追加额外指令。这是真正运行期改变 system instructions 的入口。
- **🟢 Provider 缓存证据**：Goose 官方 Provider 文档说明，使用 Anthropic Claude 的若干 Provider 路径会自动添加 `cache_control`。这表明缓存不只是靠应用“尽量别改 Prompt”，Provider adapter 也参与设置缓存断点。
- **🟡 缓存风险推论**：如果启用 Extension 改变 Prompt 渲染结果或 tool schema，cache breakpoint 前的累计前缀可能变化；具体保留多少前缀取决于 Provider 的字段顺序、缓存键规则和断点。不能仅凭 Goose 模板说 Extension 变化一定导致全量 miss。
- **值得读**：`system.md` → Extension 初始化与 tool schema 创建 → Provider adapter 注入 cache marker → 按 Anthropic API 规则评估实际 cache prefix。

来源：[Goose system.md](https://github.com/aaif-goose/goose/blob/main/crates/goose/src/prompts/system.md)、[Prompt template 注册](https://github.com/aaif-goose/goose/blob/main/crates/goose/src/prompt_template.rs)、[ACP system-prompt 更新定义](https://github.com/aaif-goose/goose/blob/main/crates/goose/acp-schema.json)、[Goose Provider Prompt Caching 文档](https://github.com/aaif-goose/goose/blob/main/documentation/docs/getting-started/providers.md)。

### 4. Hermes Agent：Prompt 会动态组装，但会话内冻结并复用

- **🟢 官方文档/源码证据**：Hermes 将 Prompt 分成 `stable → context → volatile` 三层，再在会话启动时构造完整 system prompt 并在后续轮次复用；官方文档称这样是为了保留 Provider prompt cache、让 Gateway/ACP/CLI 能额外给当前 API call 加 context 而不污染持久 Prompt。
- **🟢 对缓存很有启发的细节**：源码注释明确 Prompt “built once per session and reused across turns”，只有 context compression 等重建路径会重建。Memory snapshot 更新后不会自动把当前会话已缓存 Prompt 改掉；这是一种“快照一致性”选择，而不是 memory 永远不变。
- **🟡 动静分层细节需固定版本**：当前主线对 stable/context/volatile 的具体归属在文档和实现演进中有变动；应以本次选定 commit 对照 `agent/system_prompt.py`、`run_agent.py` 与官方 Prompt Assembly 文档，不从旧博客/外部 fork 推断。尤其要分清“构建时分为 volatile tier”和“每轮重新把 volatile 文本拼进请求”不是一回事。
- **值得读**：这能和 CodeWhale 的“可变后缀”对照：后者强调某些字段可以在会话中编辑并放到 volatile 边界下方；Hermes 强调在 session 生命周期内复用已经构造的 system prompt，turn-scoped additions 走独立 API-call-time 层。

来源：[Hermes Prompt Assembly 官方文档](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)、[当前 system prompt 源码](https://github.com/NousResearch/hermes-agent/blob/main/agent/system_prompt.py)。

### 5. OpenClaw：每次构造 Prompt，但用按需加载控制动态成本

- **🟢 官方文档证据**：OpenClaw 文档明确说每次 agent run 会构建 system prompt，内容包括当前工具摘要、Skill 元数据、workspace/bootstrap 文件、时间和 runtime metadata。Skills 列表默认只含 metadata，完整说明通过 `read` 按需加载；每日 memory 文件普通轮次也通过 memory tools 按需读取，而非默认全量塞入 bootstrap。
- **🟢 产品原则**：OpenClaw 的 Vision 解释 core 每轮都有 token tax，所以核心 Prompt/tool 应保持克制，增量能力优先走 plugins、skills、channels、apps 等扩展面；这是一条清晰的“常驻核心 vs 按需能力”设计原则。
- **🟡 缓存推论**：每次 run 都重建 Prompt 意味着如时间、runtime metadata、工具集合或 bootstrap 内容发生变化，可能影响 Provider 的前缀匹配；但文档没有因此承诺高缓存命中率。它提供 `/context detail` 之类上下文用量观察，与 Provider cache-read 指标是不同的观测。
- **值得读**：观察“system prompt 每轮重建”如何与 metadata-only Skills、on-demand memory、bootstrap 截断上限共同工作；并比较 Harness 缓存相同 session history 的条件。

来源：[OpenClaw Token Use / Prompt Context 文档](https://github.com/openclaw/openclaw/blob/main/docs/reference/token-use.md)、[OpenClaw 设计愿景：core token tax 与插件/Skills](https://github.com/openclaw/openclaw/blob/main/VISION.md)。

## 从项目源码提炼出的缓存设计办法

1. **先固定最底层、最常重复的基础块**：稳定指令和稳定工具定义放在缓存前缀前端；保证同一模型、同一会话路径下内容和工具顺序可复现。
2. **把真正会变化的内容放在后面或独立动态块**：如 OpenHands 的独立动态 content block、CodeWhale 的 volatile boundary。若 Provider 仅支持累积前缀，前置块一旦变了，后续旧前缀就无法匹配。
3. **MCP 不要把“连接到 server”误当成工具永远稳定**：server 可返回不同工具列表/描述/schema；工具启停、schema 更新、权限变化都要视为工具集版本变化。可考虑会话级固定工具快照、只向模型暴露当前任务需要的工具、稳定的工具发现入口再按需加载。后两项是工程建议，是否适用要看系统 UX、安全和 Provider tool-cache 机制。
4. **Skill 可分目录索引与完整正文**：常驻小型索引可以稳定；选中后再加载完整 Skill，降低每轮重复传输的动态 token。若 Skill 内容本身进入 system prompt，Skill 编辑/版本变化应成为清晰的 cache invalidation 边界。按需加载是架构选择，不是所有被观察项目的统一实现。
5. **Memory 明确刷新语义**：把“读取时刻/作用范围/最大长度/是否会话中刷新”写清楚。相对静态的 memory 可在 session init 快照化；实时 memory 可在本轮作为动态块或工具结果进入请求。不可为缓存而冻结权限或已过期事实。
6. **缓存命中是字节/Token 前缀与 Provider 规则的结果，不是 system prompt 文案很稳定就自然保证**：还受 tool schemas、模型/Provider、请求路由与缓存 TTL/阈值影响。Anthropic 当前文档明确其缓存前缀顺序为 `tools → system → messages`；因此在该 API 下，稳定 tools 和 system instructions 都要纳入前缀考虑，不能把 `system → tools → messages` 当跨 Provider 的顺序。
7. **分别看“缓存命中 token 数”和“命中率”**：对每次请求记录 Provider 返回的 cache-read/input tokens、普通 input tokens、cache creation tokens；以实际重复工作负载观察，而非只看有无 breakpoint。高缓存 token 比例还要求稳定前缀够长、动态新增量占比可控、同一前缀重复使用且未过期。

### 一张简化的应用侧设计图

```text
可缓存前缀（高稳定）
  基础指令 + 稳定工具 schemas + 稳定的项目/Skill 索引
  ───────────────────────────────────────── cache boundary
动态区域（按生命周期变化）
  session memory/goal + 本轮选中的 Skill 正文 + 检索/环境 + 当前 user 输入
  + 历史追加的 assistant/tool-use/tool-result
```

具体 Provider 可能调整工具、system、messages 的序列化顺序，故这是**应用侧组织示意图**，不是通用 token 顺序。Anthropic 官方 Prompt Caching 文档称其 prefix 顺序是 `tools → system → messages`，静态内容应前置并在复用边界打标；任何 breakpoint 之前的变化都会改变该位置的累计前缀。

来源：[Anthropic Prompt Caching：前缀、tools/system/messages 顺序与断点](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)。

## 关于“缓存 90%”要先定义分母

“缓存命中率 90%”可能是 cached tokens / 所有输入 tokens，也可能是有 cache read 的请求占比；两个指标差别很大。即使一轮中 90% 输入 tokens 命中，也不代表 90% 请求都 hit。应用设计能提高前缀的稳定性和重复使用机会，但不能单独保证某个数值；应对同一工作流同时记录 Provider 的 cache read/create/uncached input token，以及请求间隔、模型、工具集变化和线程路由。

## 学习顺序建议

1. **OpenHands**：沿 `Agent` → `SystemPromptEvent` → LLM call 读静态/动态 Prompt、tool definitions 和 Memory。
2. **CodeWhale**：读 `prompts.rs` 中稳定区/volatile boundary，再追 `/cache`/Provider telemetry。它最直观回答“memory 和 goal 改了怎么办”。
3. **Goose**：追 Extension 如何同时注册工具和 Prompt，再跟 Anthropic Provider cache marker；重点回答“MCP 扩容/启停怎样影响工具和缓存”。
4. **做一张自己的请求表**：每个字段记录来源、生命周期、放入 system/tools/messages 哪一层、更新时机、cache boundary 在它之前还是之后。

| 字段 | 示例来源 | 生命周期 | 进入位置 | 改动可能影响 |
|---|---|---|---|---|
| 基础 Agent 指令 | 模板/程序内资源 | release/配置周期 | system/developer instructions | 其后缓存前缀 |
| MCP 工具定义 | MCP `tools/list` + adapter | 会话/连接周期 | 独立 tools schema | tools 前缀及后续块 |
| Skill 正文 | 文件或注册中心 | 按激活/版本变化 | system block 或消息 | 注入点后的前缀 |
| Memory | 存储、检索器、项目文件 | session 或每轮 | dynamic system block / tool result | 注入点后的前缀 |
| Tool result | 工具执行 | 每次调用 | messages 历史 | 只追加时保留之前 prefix |

## 证据边界与待验证

- 🟢 **已验证（源码/官方文档）**：OpenHands 明确拆静态 system 与动态 context，并将 tools 独立表示；CodeWhale 明确区分稳定内容与易变尾部；Goose 扩展会影响工具与 Prompt 指令。
- 🟡 **部分验证**：这些项目的设计意图服务于稳定前缀或动态能力；不能直接推出同一 provider 下的实际高命中比例。
- 🔴 **未验证**：本次未固定 commit、运行三项目或采集真实 Provider 的 cache read/write token，因此不能比较谁的命中率最高。
- 🔴 **待源码追踪**：MCP server 工具 schema 变化时，每个项目是否重建整个会话、只更换工具子集、或保留历史 messages；要沿当前版本的连接/重连和 Provider request 路径查证。

## 术语速查

- **Request/Prompt builder（请求/提示构造器）**：Harness 层根据模板、配置和会话状态生成一次模型请求的代码路径；不必是单一函数。
- **MCP（Model Context Protocol，模型上下文协议）**：Agent 应用和外部工具/数据服务器之间的协议。MCP server 提供的 tool schema 是能力元数据；实际执行、鉴权仍由应用/runtime 负责。
- **Tool schema（工具 Schema/结构定义）**：模型可见的工具名称、描述、参数结构；不是工具实现代码，也不是授权本身。
- **Skill（技能说明/工作方法）**：可加载的领域指令或操作流程。它可能只是一段 Context，也可能附带工具配置，取决于产品实现。
- **Memory（记忆）**：跨轮/跨会话保存并可能重新读入的状态或事实；与当前 messages 历史、检索到的上下文不是同义词。
- **Cache boundary / breakpoint（缓存边界/断点）**：Provider 识别可复用前缀的截止位置；断点之前改动会影响该累计前缀的可复用性。
