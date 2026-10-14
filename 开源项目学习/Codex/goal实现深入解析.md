# Codex：Goal 实现深入解析

## 学习问题与范围

- 当前问题：`/goal` 如何把一个目标保存下来，并在合适的时机继续执行下一轮？
- 相关子问题：命令与模型工具入口、目标状态存储、thread 关联、上下文注入、继续条件、生命周期权限、预算与完成审查；区分 CLI、desktop 和 app-server。
- 进度：已初始化，暂缓学习。先学习 [AI 长任务工程的通用主线](../../specs/work-pool/W-2026-036-study-long-running-agent-tasks-and-goals.md)，用户明确要求后再研究本模块。

## 源码与证据

- 官方仓库：[openai/codex](https://github.com/openai/codex)；Goal 相关研究子路径待定位。
- 版本 / Commit：正式开始本模块时单独固定；不自动沿用输入预测模块的源码基线。
- 已有资料：[Using Goals in Codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)，2026-10-15 已读取官方设计说明。
- 待追踪链路：命令解析 → 目标状态与持久化 → 状态查询/上下文 → 轮次结束 → 继续判断 → 下一轮 → 完成或停止。
- 证据状态：仅有官方文档描述；本模块尚未读源码、克隆项目或运行实验。需要检查完成审查究竟由提示词、模型判断还是程序校验承担，不预设强制验证能力。

## 我的笔记
