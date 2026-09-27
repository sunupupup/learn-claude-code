# 我的笔记

**Codex 源码难度太大 。。。 先不看了**

学习内容：项目指令怎么进入上下文、工具和 MCP schema 怎么组装、Skills 与 Memory 何时加载，以及这些内容怎样影响每轮请求的前缀

## Session 对象

codex\codex-rs\core\src\session\session.rs

可以把 Session 想成 「这一场完整对话」在运行时里的那一坨状态——同一条聊天线、同一份配置和 history、多轮来回都在里面。

在 Codex 源码里，Session = 一条对话线程在进程里的运行时容器（注释写的是 「Context for an initialized model agent」）。

可以把它理解成：

Thread（线程/会话） 用户眼里的「这一场聊天」：有 thread_id、rollout 历史、可 resume/fork
Session 这条 thread 当前这次在内存里跑起来 的那套东西：配置、history、MCP、ModelClient、输入队列、正在跑的 turn


thread id 和 session id 并不一定是一对一

什么时候「像一对一」
普通根会话（CLI 里那一个聊天窗口）
新建：session_id == thread_id（测试 resumed_root_session_uses_thread_id_as_session_id 也这么断言）。
你心里「一个窗口 = 一个 thread」时，可以当成一对一对齐。

什么时候不是一对一
子 Agent / 从父 thread spawn 出来的子 thread
thread_id：子线程自己的新 ID
session_id：仍是 父/根那条线的 session_id（测试 resumed_subagent_session_restores_persisted_session_id：thread_id ≠ session_id）。
内存里的 Session 对象 vs 持久化

关掉再 resume：新的 Session 实例，thread_id / rollout 里的 session_id 从元数据恢复，不是「一个 Session 对象活一辈子」。 



## Prompt 对象

看着其实重要的就三个 input、tools、base_instructions

```rust
pub struct Prompt {
    /// Conversation context input items.
    pub input: Vec<ResponseItem>,

    /// Tools available to the model, including additional tools sourced from
    /// external MCP servers.
    pub(crate) tools: Arc<[ToolSpec]>,

    /// Whether parallel tool calls are permitted for this prompt.
    pub(crate) parallel_tool_calls: bool,

    pub base_instructions: BaseInstructions,

    /// Optional the output schema for the model's response.
    pub output_schema: Option<Value>,

    /// Whether the Responses API should strictly validate `output_schema`.
    pub output_schema_strict: bool,

    pub(crate) cyber_access_program: Option<codex_protocol::turn_input::CyberAccessProgram>,
}
```

在codex\codex-rs\core\src\session\turn.rs 的  build_prompt 会构建这个 Prompt 对象



## Codex 里面的 System Prompt

### 和 Chat Completions 的差异（先建立对照）

| 常见 Chat 风格 | Codex（Responses API） |
|---|---|
| `messages[].role = system` 一大段 | 拆成 **`instructions` 字符串** + **`input[]` 里多条 `developer` / `user` 消息** |
| `messages` 聊天 + tool | **`input[]` = `ResponseItem` 数组**（message、function_call、function_call_output、Lite 下 AdditionalTools 等） |
| `tools` | 仍是 **`tools` JSON**；Responses Lite 时工具定义进 **`input` 前缀的 AdditionalTools** |

心智模型：**没有本地 `buildSystemPrompt(): string` 把 tools/skills/memory 全拼进一个 system 字符串**；发 HTTP 时在 `build_responses_request` 里按协议装箱。

源码入口：`codex-rs/core/src/client.rs` → `build_responses_request`。

---

### HTTP 上「system 感」的三块

1. **`instructions`**（≈ 主 system / 模型底座）  
   - 来源：会话级 `session_configuration.base_instructions`（整段字符串，会话内相对稳定）。  
   - 发请求：`get_prompt_base_instructions()` → `build_prompt` → `request.instructions`（非 Lite）。

2. **`input[]`**（≈ 其余 system 补充 + 对话 + 工具往返）  
   - 权限、环境、Skills 目录、Memory 说明、AGENTS.md 正文、扩展片段等，多在 **history 最前面的 developer/user Message**。  
   - 用户话、assistant、tool call/output 也在同一数组里按时间追加。

3. **`tools`**（工具 / MCP schema，**不进 instructions 正文**）  
   - `capture_step_context` → `built_tools` / `ToolRouter` → `prompt.tools` → 顶层 `tools` 或 Lite 的 `AdditionalTools`。

---

### `instructions` 正文从哪来（完整链路）

```text
文案源头（优先级从高到低）
  1. config.base_instructions 显式覆盖
  2. 恢复会话 rollout 里的 base_instructions.text
  3. render_model_instructions(&model_info)
       → ResolvedModelMessages::instructions_template()
       → ModelInfo.model_messages.instructions_template
         · 默认：codex-rs/models-manager/models.json（按 slug 的 instructions_template，超长字符串）
         · 未知 slug 回退：codex-rs/models-manager/prompt.md（include_str 进 model_info.rs）
         · 在线：/models 拉 catalog，缓存 ~/.codex/models_cache.json
  ↓
session/mod.rs 建会话（约 739–743、820–836 行）
  base_instructions → SessionConfiguration.base_instructions
  ↓
SessionState.base_instructions_provenance（Model / Custom）
  ↓
每轮采样：get_prompt_base_instructions()（可能 without_update_plan_instructions）
  ↓
build_responses_request → request.instructions
```

注意：

- `prompts/src/model_instructions.rs` **只有转发**，真正长文在 **`models-manager/models.json`** 或 **`models-manager/prompt.md`**。  
- `core/gpt_5_1_prompt.md` **运行时未 include**，可当对照稿；以 catalog 为准。  
- `protocol/.../base_instructions/default.md` 是 **BaseInstructions 结构体默认值**，不是每条请求用的 Codex 模型模板。

薄封装：

```rust
// prompts/src/model_instructions.rs
render_model_instructions → model_info.model_messages.instructions_template
```

---

### 其它产品塞进 system 的内容 → Codex 放哪

| 内容 | 写入方式 | HTTP 字段 / role | 主要源码 |
|---|---|---|---|
| 模型身份 / 长行为模板 | 会话 `base_instructions` | **`instructions`**（Lite：input developer） | `models.json`、`session/mod.rs` |
| 权限 / 沙箱 | WorldState `PermissionsState` | input **developer** | `world_state/permissions.rs`、`prompts/permissions_instructions.rs` |
| 环境 cwd / 日期 | `EnvironmentsState` | input developer | `world_state/environment.rs` |
| **AGENTS.md** | `agents_md_manager.refresh` → `AgentsMdState` | input **user**（`# AGENTS.md instructions`） | `world_state/agents_md.rs`、`user_instructions.rs` |
| **Memory 用法** | `MemoriesExtension::contribute_thread_context` | input developer（`memories.instructions`） | `ext/memories/src/extension.rs`、`prompts.rs` |
| **Skills 目录** | `SkillsExtension::contribute_thread_context` | input developer（DeveloperCapabilities） | `ext/skills/src/extension.rs`、`render.rs` |
| **Skill 全文** | `build_skills_and_plugins`（显式 mention 等） | input（**按 turn** 写入 history） | `session/turn.rs` |
| 额外 rules | `config.developer_instructions`、`ManagedDeveloperInstructions` | input developer | `build_initial_context_with_world_state` |
| 工具 schema | ToolRouter | **`tools`** / AdditionalTools | `tools/spec_plan.rs`、`client.rs` |
| 延迟工具 namespace 简述 | `ToolsState`（feature） | input developer `<tools>…` | `context/world_state/tools.rs` |

**总装（类 system 文本进 history，不是 instructions）：**

- 首 turn / 丢 baseline：`record_context_updates_and_set_reference_context_item` → `build_initial_context_with_world_state`（`session/mod.rs` ~4268）。  
- 合并多条 fragment → 一条 Message：`context_manager/updates.rs`（`merge_contextual_fragments`、`build_rendered_message`）。  
- 后续 turn：WorldState **diff**，不全量重发。  
- 本轮追加：Skills 正文、插件、`build_extension_turn_input_items` → `record_conversation_items`。

WorldState 组装：`session/world_state.rs` → `build_world_state_for_step`（section 插入顺序决定首包 fragment 顺序）。

---

### Tools 与 MCP schema 组装（不进 system 字符串）

```text
run_turn / capture_step_context
  → mcp_runtime_for_step（刷新 MCP、connector）
  → turn::built_tools → tools/spec_plan.rs → build_model_visible_specs
  → ToolRouter.model_visible_specs()
  ↓
build_prompt(..., tools: model_visible_specs(), ...)
  ↓
build_responses_request → create_tools_json_* → request.tools 或 AdditionalTools
```

MCP 的 name/description/parameters 在 **ToolSpec** 里；与「给模型看的权限说明」是两层。

---

### Skills / Memory 何时加载（相对每轮前缀）

| 时机 | Skills | Memory |
|---|---|---|
| 线程 / 首包 context | 目录摘要（extension thread context）；world_state 里 skills / host_skills 等 section | developer 策略文案（`contribute_thread_context`） |
| 每个 user turn 开始 | 显式 mention → `load_skill_prompts` 注入正文 | 一般不每轮重发整段说明；读记忆走 tool / 后端 |
| 发 HTTP 前 | history 已含上述项；Lite 再在 input 前 splice tools + base | 同左 |

Guardian 等子会话：`build_skills_and_plugins` 可跳过注入。

---

### `build_prompt` 做什么（避免误以为在拼 system）

`session/turn.rs` → `build_prompt`：**只打包** `Prompt { input, tools, base_instructions, ... }`，不拼长文本。  
`input` 来自 `clone_history().for_prompt()`；`base_instructions` 来自 `get_prompt_base_instructions()`。

调试 `build_prompt_input`（`prompt_debug.rs`）**只返回 `input`**，不含顶层 `instructions` / `tools`。

---

### 经典 Responses vs Responses Lite（影响前缀形态）

| | 经典 | Lite |
|---|---|---|
| `instructions` | `base_instructions.text` | 空 |
| `tools` | 顶层 JSON | null |
| input 前缀 | 仅 history 里的 context | **先** AdditionalTools，**再** base 的 developer 消息，**再** history |

前缀 item 带稳定 id（thread UUID + 内容 hash），利于重试 / prompt cache。

---

### 与 Prompt Cache 相关的观察点

- **稳定、可复用前缀**：`instructions`（未改）、合并后的首条 developer、Lite 的 AdditionalTools + base developer（id 稳定）、未改动的 history 前段。  
- **改前缀**：换 `base_instructions`、改 AGENTS、WorldState diff、新 skill 注入、压缩/替换 history、工具集变化（tools / AdditionalTools）。  
- **不要假设**：Skill/Memory「有功能」= 每轮都进同一段固定 system；要看是否进 thread context、是否 turn 注入、是否只在 tool 路径。

---

### 建议阅读顺序（源码，仓库 `source-reading/codex/codex-rs`）

1. `models-manager/models.json` + `models-manager/src/manager.rs`（`get_model_info`）  
2. `core/src/session/mod.rs`（base_instructions 解析、`build_initial_context_with_world_state`）  
3. `core/src/session/world_state.rs`、`core/src/context_manager/updates.rs`  
4. `ext/memories`、`ext/skills` 的 `extension.rs`  
5. `core/src/session/turn.rs`（`build_skills_and_plugins`、`build_prompt`、`run_sampling_request`）  
6. `core/src/tools/spec_plan.rs`、`core/src/client.rs`（`build_responses_request`）

---

### 和下方「AI 生成笔记」的差异（以本节为准）

- 模型主模板：**以 `models-manager/models.json` 的 `instructions_template` 为主**，不是仅 `protocol/.../default.md`。  
- System 上下文：**大量在 `input` 的 developer/user**，不是全部在 `instructions`。  
- 下文「待继续核验」仍可做：固定 commit 抓一包真实 `ResponsesApiRequest` JSON，核对 `input[0..n]` 的 `content_item_kinds`。



# AI生成的笔记 Codex CLI

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
