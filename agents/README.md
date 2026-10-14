# Agent / Harness 课程

新版 20 章按学习顺序集中在本目录。每章的 `README.md` 是教材，`code.py` 是教学实现，`LEARNING_NOTES.md` 是个人学习笔记（如已有）。学习状态以各章笔记为准，不因目录整理而改变。

## 章节入口

| 章节 | 主题 |
|---|---|
| [s01](./s01_agent_loop/) | Agent Loop：模型与工具的循环 |
| [s02](./s02_tool_use/) | Tool Use：工具使用 |
| [s03](./s03_permission/) | Permission：权限 |
| [s04](./s04_hooks/) | Hooks：生命周期扩展点 |
| [s05](./s05_todo_write/) | TodoWrite：待办计划 |
| [s06](./s06_subagent/) | Subagent：子 Agent |
| [s07](./s07_skill_loading/) | Skill Loading：技能按需加载 |
| [s08](./s08_context_compact/) | Context Compact：上下文压缩 |
| [s09](./s09_memory/) | Memory：长期记忆 |
| [s10](./s10_system_prompt/) | System Prompt：系统提示词 |
| [s11](./s11_error_recovery/) | Error Recovery：错误恢复 |
| [s12](./s12_task_system/) | Task System：任务系统 |
| [s13](./s13_background_tasks/) | Background Tasks：后台任务 |
| [s14](./s14_cron_scheduler/) | Cron Scheduler：定时调度 |
| [s15](./s15_agent_teams/) | Agent Teams：多 Agent 团队 |
| [s16](./s16_team_protocols/) | Team Protocols：团队通信协议 |
| [s17](./s17_autonomous_agents/) | Autonomous Agents：自主认领任务 |
| [s18](./s18_worktree_isolation/) | Worktree Isolation：工作目录隔离 |
| [s19](./s19_mcp_plugin/) | MCP Plugin：外部工具接入 |
| [s20](./s20_comprehensive/) | Comprehensive：综合实现 |

## 运行方式

仍从仓库根目录执行，避免把 `.env`、`skills/` 和运行状态目录解析到章节目录：

```sh
python agents/s01_agent_loop/code.py
```

Web 平台的内容提取同样读取这里的 20 章：在 `web/` 中执行 `npm run extract`。

## 历史路径

原根目录 `sXX_主题/` 已移入 `agents/sXX_主题/`。旧版 `agents/*.py` 和 `docs/en`、`docs/zh`、`docs/ja` 教材已删除；`mini-swe-agent` 子模块也已移除。

旧版编号不能直接套用到新版：

| 旧版 12 章 | 新版 20 章 |
|---|---|
| s01 Agent Loop | s01 |
| s02 Tool Use | s02 |
| s03 TodoWrite | s05 |
| s04 Subagent | s06 |
| s05 Skill Loading | s07 |
| s06 Context Compact | s08 |
| s07 Task System | s12 |
| s08 Background Tasks | s13 |
| s09 Agent Teams | s15 |
| s10 Team Protocols | s16 |
| s11 Autonomous Agents | s17 |
| s12 Worktree Isolation | s18 |

新版新增 s03、s04、s09、s10、s11、s14、s19、s20。旧综合脚本 `s_full.py` 已删除，新版综合课程入口是 s20，二者不保证行为完全一致。

历史笔记和索引不批量修复；遇到失效引用时，先确认主题及实际位置，再局部修改。具体维护规则见[根 AGENTS.md](../AGENTS.md#课程目录与历史引用)。
