# Repository Agent Instructions

## Spec 工作流

本仓库使用 [`specs/README.md`](./specs/README.md) 定义的轻量 Spec 工作流。涉及方案、实现或任务整理时，先按该文档判断是否需要创建或更新 Spec。

### 何时读取 Spec

- 开始多文件改动、重要功能或需求仍含歧义的实现前，先阅读 `specs/README.md`；
- 同时检查 `specs/current/`、`specs/changes/` 和 `specs/decisions/` 中与任务相关的现有约束；
- 单文件、行为明确且预计少于 30 分钟的改动，可以直接处理，不强制创建 Spec。

### 任务如何流转

- 已知但暂不开始的工作记录到 `specs/work-pool/`；不要因为它存在就自动开始，等待用户明确启动；
- 开始 Work Pool 任务时，按规范创建对应的 `specs/changes/C-*.md`，并移除原 Work Pool 文件；
- 暂时无法决定的问题进入 `specs/review-pool/`；
- 会长期影响项目的重要决定进入 `specs/decisions/`；
- Change 完成后，按需更新 `specs/current/`，并在 `specs/implementation/` 记录实现、验证和遗留事项。

### 维护原则

- 一个事实只保留一个主要来源，其他文件使用相对链接引用；
- `specs/README.md` 是目录、命名、状态与流转规则的唯一规范来源，本文件只负责告诉 Agent 何时使用它；
- 章节学习过程仍记录在对应章节的 `LEARNING_NOTES.md`，不要把聊天笔记重复写入 Spec；
- 不要为了满足形式而创建空 Spec；仅在任务复杂度、风险或后续追踪价值值得时使用。

## 代码注释

- 新增或修改代码时，关键逻辑、数据流、缓存判断、边界条件和非显而易见的设计意图，必须补充简洁准确的中文注释；
- 注释应解释代码为什么这样做、状态如何变化以及容易混淆的边界，不要求对每一行显而易见的语法逐行注释；
- 代码行为变化时同步更新相关注释，避免保留与实现不一致的学习说明。
