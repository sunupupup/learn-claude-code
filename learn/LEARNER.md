# 学习者档案

> 协助我学习本仓库时请先读这里。每章笔记在 `learn/notes/` 目录。

## 我是谁

- **身份**：Agent / Harness 工程 **初学者**
- **背景**：对 agent loop、tool use、harness、context compact 等概念 **都不熟**
- **目标**：系统学完新版主线 `s01` → `s20`，理解「模型 + Harness」如何组成可用 Agent

## 学习路径

| 类型 | 位置 | 说明 |
|------|------|------|
| **主线教程** | `s01_agent_loop/` … `s20_comprehensive/` | README + `code.py` + 配图 |
| **学习笔记** | `learn/notes/sXX_*.md` | 每章一个 md，记录概念、实验、疑问 |
| **执行 trace** | `s01_agent_loop/traces/` 等 | 部分章节有运行链路日志 |
| **旧版代码** | `agents/*.py` | 仅对比参考，不按旧章节号学习 |

**当前进度**：S01 Agent Loop（学习中）

## 请 AI 协助时的默认方式

1. **先概念，后代码**；术语第一次出现用通俗话解释
2. **不要默认我已懂** harness、tool call、messages、stop_reason 等
3. **用中文（简体）回答**
4. 结合本仓库具体文件讲解，少讲空泛理论
5. 未学章节可简短预告，**重点放在当前章节**
6. 代码改动以理解为主；学完一章可协助 **补充对应笔记 md**
7. 协助前可读 `learn/notes/sXX_*.md` 了解我已掌握的内容

## 分支与环境

- **学习分支**：`learn_note`
- **API**：OpenRouter（根目录 `.env`）
  - `ANTHROPIC_BASE_URL=https://openrouter.ai/api`
  - `MODEL_ID=z-ai/glm-5.2`
- **运行**：在项目根目录执行 `python sXX_xxx/code.py`

## 笔记索引（s01–s20）

每章笔记路径：`learn/notes/<章节目录名>.md`

| 章 | 主题 | 笔记 | 状态 |
|----|------|------|------|
| s01 | Agent Loop | [s01_agent_loop.md](notes/s01_agent_loop.md) | 学习中 |
| s02 | Tool Use | [s02_tool_use.md](notes/s02_tool_use.md) | 待学习 |
| s03 | Permission | [s03_permission.md](notes/s03_permission.md) | 待学习 |
| s04 | Hooks | [s04_hooks.md](notes/s04_hooks.md) | 待学习 |
| s05 | TodoWrite | [s05_todo_write.md](notes/s05_todo_write.md) | 待学习 |
| s06 | Subagent | [s06_subagent.md](notes/s06_subagent.md) | 待学习 |
| s07 | Skill Loading | [s07_skill_loading.md](notes/s07_skill_loading.md) | 待学习 |
| s08 | Context Compact | [s08_context_compact.md](notes/s08_context_compact.md) | 待学习 |
| s09 | Memory | [s09_memory.md](notes/s09_memory.md) | 待学习 |
| s10 | System Prompt | [s10_system_prompt.md](notes/s10_system_prompt.md) | 待学习 |
| s11 | Error Recovery | [s11_error_recovery.md](notes/s11_error_recovery.md) | 待学习 |
| s12 | Task System | [s12_task_system.md](notes/s12_task_system.md) | 待学习 |
| s13 | Background Tasks | [s13_background_tasks.md](notes/s13_background_tasks.md) | 待学习 |
| s14 | Cron Scheduler | [s14_cron_scheduler.md](notes/s14_cron_scheduler.md) | 待学习 |
| s15 | Agent Teams | [s15_agent_teams.md](notes/s15_agent_teams.md) | 待学习 |
| s16 | Team Protocols | [s16_team_protocols.md](notes/s16_team_protocols.md) | 待学习 |
| s17 | Autonomous Agents | [s17_autonomous_agents.md](notes/s17_autonomous_agents.md) | 待学习 |
| s18 | Worktree Isolation | [s18_worktree_isolation.md](notes/s18_worktree_isolation.md) | 待学习 |
| s19 | MCP Plugin | [s19_mcp_plugin.md](notes/s19_mcp_plugin.md) | 待学习 |
| s20 | Comprehensive | [s20_comprehensive.md](notes/s20_comprehensive.md) | 待学习 |

---

*最后更新：2026-06-22*
