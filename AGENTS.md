# AGENTS — 本仓库学习协作说明

> **全局入口**：协助我学习本仓库时请先读此文件。  
> 每章笔记：`learn/notes/sXX_*.md` · Cursor 规则：`.cursor/rules/learner-profile.mdc`

## 我是谁

我是 **Agent / Harness 工程初学者**。

- **起点**：对 agent loop、tool use、harness、context compact、tool calling 协议等 **几乎零基础**
- **理论**：相关概念、业界术语、API 格式差异 **都不熟**，需要从实际问题入手慢慢建立体系
- **目标**：系统学完新版主线 `s01` → `s20`，最终理解「模型 + Harness」如何组成一个能干活、可迭代的 Agent
- **学习方式**：读教程 → 跑代码 → 提问 → **把问答沉淀进笔记** → 不断积累，而不是聊完就忘

## 学习积累工作流（重要）

本仓库的学习靠 **持续沉淀**，不是一次性对话。

### 对话中产生的每一个问题

学习过程中在对话里出现的 **所有问题**（包括追问、澄清、类比、踩坑），在讲解清楚之后，AI 必须：

1. **消化整理** — 去掉口语废话，提炼成可复用的知识点
2. **写入当前章节笔记** — 更新 `learn/notes/sXX_*.md`（`sXX` = 当前正在学的章）
3. **可适当扩展** — 补充必要背景、对比、示例、与仓库代码/trace 的关联，帮助举一反三
4. **避免重复** — 写入前先读该章笔记已有内容，合并同类项，不堆重复段落

### 笔记里写什么

| 来源 | 写入笔记的位置（示例） |
|------|------------------------|
| 「这是什么意思？」 | **核心概念** 或新增小节 |
| 「为什么这样？」 | **代码要点** / **原理** |
| 跑实验、看 trace | **实验记录** |
| 踩坑、易错点 | **疑问与心得** 或 **易错点** |
| 和 OpenAI / 其他厂商对比 | **扩展阅读** / **格式对比** |

### 节奏

- **每次辅导结束**（或一个话题讲透时）→ 主动更新笔记，**不必等我提醒**
- 我若没有明确说「不要写笔记」，默认 **就是要沉淀**
- 笔记是给未来的我看的「第二大脑」，要比聊天回复更结构化、更可翻阅

## 学习路径

| 类型 | 位置 | 说明 |
|------|------|------|
| **主线教程** | `s01_agent_loop/` … `s20_comprehensive/` | README + `code.py` + 配图 |
| **学习笔记** | `learn/notes/sXX_*.md` | 每章一个 md，**对话问答的最终归宿** |
| **执行 trace** | `s01_agent_loop/traces/` 等 | 运行链路日志，可引用进笔记 |
| **旧版代码** | `agents/*.py` | 仅对比参考，不按旧章节号学习 |

**当前进度**：S01 Agent Loop（学习中）

## 请 AI 协助时的默认方式

1. **先概念，后代码**；术语第一次出现用通俗话解释
2. **不要默认我已懂** — 我是初学者，从零讲起
3. **用中文（简体）回答**
4. 结合本仓库具体文件、trace、代码行号讲解，少讲空泛理论
5. 未学章节可简短预告，**重点放在当前章节**
6. 代码改动以理解为主；非必要不大改仓库
7. **辅导前**：读 `AGENTS.md` + 当前章 `learn/notes/sXX_*.md`，了解我已掌握什么
8. **辅导后**：按上文「学习积累工作流」更新当前章笔记

## 分支与环境

- **学习分支**：`learn_note`
- **API**：OpenRouter（根目录 `.env`）
  - `ANTHROPIC_BASE_URL=https://openrouter.ai/api`（不要写成 `/api/v1`）
  - `MODEL_ID=z-ai/glm-5.2`
- **运行**：在项目根目录执行 `python sXX_xxx/code.py`

## 笔记索引（s01–s20）

| 章 | 主题 | 笔记 | 状态 |
|----|------|------|------|
| s01 | Agent Loop | [learn/notes/s01_agent_loop.md](learn/notes/s01_agent_loop.md) | 学习中 |
| s02 | Tool Use | [learn/notes/s02_tool_use.md](learn/notes/s02_tool_use.md) | 待学习 |
| s03 | Permission | [learn/notes/s03_permission.md](learn/notes/s03_permission.md) | 待学习 |
| s04 | Hooks | [learn/notes/s04_hooks.md](learn/notes/s04_hooks.md) | 待学习 |
| s05 | TodoWrite | [learn/notes/s05_todo_write.md](learn/notes/s05_todo_write.md) | 待学习 |
| s06 | Subagent | [learn/notes/s06_subagent.md](learn/notes/s06_subagent.md) | 待学习 |
| s07 | Skill Loading | [learn/notes/s07_skill_loading.md](learn/notes/s07_skill_loading.md) | 待学习 |
| s08 | Context Compact | [learn/notes/s08_context_compact.md](learn/notes/s08_context_compact.md) | 待学习 |
| s09 | Memory | [learn/notes/s09_memory.md](learn/notes/s09_memory.md) | 待学习 |
| s10 | System Prompt | [learn/notes/s10_system_prompt.md](learn/notes/s10_system_prompt.md) | 待学习 |
| s11 | Error Recovery | [learn/notes/s11_error_recovery.md](learn/notes/s11_error_recovery.md) | 待学习 |
| s12 | Task System | [learn/notes/s12_task_system.md](learn/notes/s12_task_system.md) | 待学习 |
| s13 | Background Tasks | [learn/notes/s13_background_tasks.md](learn/notes/s13_background_tasks.md) | 待学习 |
| s14 | Cron Scheduler | [learn/notes/s14_cron_scheduler.md](learn/notes/s14_cron_scheduler.md) | 待学习 |
| s15 | Agent Teams | [learn/notes/s15_agent_teams.md](learn/notes/s15_agent_teams.md) | 待学习 |
| s16 | Team Protocols | [learn/notes/s16_team_protocols.md](learn/notes/s16_team_protocols.md) | 待学习 |
| s17 | Autonomous Agents | [learn/notes/s17_autonomous_agents.md](learn/notes/s17_autonomous_agents.md) | 待学习 |
| s18 | Worktree Isolation | [learn/notes/s18_worktree_isolation.md](learn/notes/s18_worktree_isolation.md) | 待学习 |
| s19 | MCP Plugin | [learn/notes/s19_mcp_plugin.md](learn/notes/s19_mcp_plugin.md) | 待学习 |
| s20 | Comprehensive | [learn/notes/s20_comprehensive.md](learn/notes/s20_comprehensive.md) | 待学习 |

---

*最后更新：2026-06-22*
