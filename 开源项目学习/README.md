# 开源项目学习

按“项目 → 模块笔记”集中学习真实实现；想研究同一种机制时，从模块索引进入不同项目的笔记。

使用 [Prompt 7](../PROMPT_7_OPEN_SOURCE_PROJECT_LEARNING.md) 加入项目、登记模块并逐步学习。每次学习时由 Agent 同步维护下面两张索引表；目录、模板和保护规则统一维护在 Prompt 7。

## 项目索引

| 项目 | 简介与特色 | 已加入的学习模块 |
| --- | --- | --- |
| [Codex](Codex/README.md) | OpenAI 的编程 Agent；公开 CLI 与 app-server 源码可用于观察会话协议和执行支撑机制，桌面端行为须另行核验。 | [输入预测（Composer Prediction）](Codex/输入预测模块.md)、[Goal 实现深入解析](Codex/goal实现深入解析.md) |
| [Pi Coding Agent](<Pi Coding Agent/README.md>) | 可扩展的终端编程 Agent；会话使用 JSONL 条目树保存，可观察分支历史与模型上下文的分离。 | [会话管理](<Pi Coding Agent/会话管理模块.md>)、[上下文压缩策略](<Pi Coding Agent/上下文压缩策略模块.md>)、[工具管理](<Pi Coding Agent/工具管理模块.md>)、[运行生命周期管理](<Pi Coding Agent/运行生命周期管理模块.md>) |

## 模块索引

| 模块 | 学习问题与范围 | 项目入口与进度 |
| --- | --- | --- |
| 输入预测 | Composer（消息输入框）的候选输入如何生成；触发时机、上下文来源、预测分支、接受与丢弃的边界。 | [Codex](Codex/输入预测模块.md)：已初始化；预测分支协议已静态核验，桌面端完整链路待验证。 |
| 长任务目标与持续执行 | 目标持久化、跨轮继续、停止条件、预算与完成审查；与通用长任务知识分开学习。 | [Codex Goal](Codex/goal实现深入解析.md)：已初始化，暂缓学习；源码与运行待验证。 |
| 会话管理 | 会话持久化、重启恢复、模型上下文重建与上下文压缩；先学“重启后如何接着聊”。 | [Pi Coding Agent](<Pi Coding Agent/会话管理模块.md>)：学习中；固定版本源码初读，未运行验证。 |
| 上下文压缩策略 | 从“100 条消息触发自动压缩”研究触发条件、保留预算、切分点与摘要生成。 | [Pi Coding Agent](<Pi Coding Agent/上下文压缩策略模块.md>)：学习中；默认策略与切分依据已静态核验，未运行验证。 |
| 工具管理 | 注册与启用、描述与参数、调用执行、权限、结果、错误和观测。 | [Pi Coding Agent](<Pi Coding Agent/工具管理模块.md>)：学习中；工具机制地图已静态梳理，未运行验证；后续逐项深入。 |
| 运行生命周期管理 | 启动、执行状态、中断与取消、完成与失败收尾；先学流式调用时的取消。 | [Pi Coding Agent](<Pi Coding Agent/运行生命周期管理模块.md>)：已初始化；部分取消路径已静态核验，未运行验证。 |

## 旧专题入口

- [开源项目权限审批设计](../learning-notes/work-pool/W-2026-005-study-production-agent-permissions-and-approval-权限审批/开源项目权限审批设计/子项目.md)：原有项目候选和权限审批阅读路线，保留为历史来源；后续项目模块学习通过 Prompt 7 集中记录。

旧专题尚未迁移，其项目不计入上面的“已加入”索引。
