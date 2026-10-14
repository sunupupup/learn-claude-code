# 开源项目学习

按“项目 → 模块笔记”集中学习真实实现；想研究同一种机制时，从模块索引进入不同项目的笔记。

使用 [Prompt 7](../PROMPT_7_OPEN_SOURCE_PROJECT_LEARNING.md) 加入项目、登记模块并逐步学习。每次学习时由 Agent 同步维护下面两张索引表；目录、模板和保护规则统一维护在 Prompt 7。

## 项目索引

| 项目 | 简介与特色 | 已加入的学习模块 |
| --- | --- | --- |
| [Chatwoot](Chatwoot/README.md) | 可自部署的多渠道客服平台，提供共享收件箱、在线聊天与 Captain AI 客服；用于学习客服业务与 Agent 执行机制的衔接。 | [客服消息进入Agent](Chatwoot/客服消息进入Agent.md)、[Agent循环与对话状态](Chatwoot/Agent循环与对话状态.md)、[Scenario与多Agent协作](Chatwoot/Scenario与多Agent协作.md)、[Agent上下文组织](Chatwoot/Agent上下文组织.md)、[工具管理与执行](Chatwoot/工具管理与执行.md)、[转人工与会话归属](Chatwoot/转人工与会话归属.md)、[Agent记忆分层](Chatwoot/Agent记忆分层.md)、[Agent评估闭环](Chatwoot/Agent评估闭环.md)、[客服Agent生产架构](Chatwoot/客服Agent生产架构.md) |
| [Codex](Codex/README.md) | OpenAI 的编程 Agent；公开 CLI 与 app-server 源码可用于观察会话协议和执行支撑机制，桌面端行为须另行核验。 | [输入预测（Composer Prediction）](Codex/输入预测模块.md)、[Goal 实现深入解析](Codex/goal实现深入解析.md) |
| [Pi Coding Agent](<Pi Coding Agent/README.md>) | 可扩展的终端编程 Agent；会话使用 JSONL 条目树保存，可观察分支历史与模型上下文的分离。 | [会话管理](<Pi Coding Agent/会话管理模块.md>)、[上下文压缩策略](<Pi Coding Agent/上下文压缩策略模块.md>)、[工具管理](<Pi Coding Agent/工具管理模块.md>)、[运行生命周期管理](<Pi Coding Agent/运行生命周期管理模块.md>) |

## 模块索引

| 模块 | 学习问题与范围 | 项目入口与进度 |
| --- | --- | --- |
| 客服消息进入Agent | 追踪 Conversation → ResponseBuilderJob → AgentRunnerService；确认谁触发任务、依据什么条件进入 Agent，以及回复如何回到会话。 | [Chatwoot](Chatwoot/客服消息进入Agent.md)：已初始化，待学习；源码与运行待验证。 |
| Scenario与多Agent协作 | 观察 Scenario（业务场景）是否将指令、工具、Guardrails（行为约束）和启用状态组织为独立 Agent 节点，以及如何通过移交构成 Agent Graph（智能体连接图）。 | [Chatwoot](Chatwoot/Scenario与多Agent协作.md)：已初始化，待学习；源码与运行待验证。 |
| Agent上下文组织 | 追踪 Conversation、Instructions（指令）、Knowledge（知识）、Citation（引用）、Guidelines（指导规则）与 Guardrails 的来源、组装位置和实际模型输入。 | [Chatwoot](Chatwoot/Agent上下文组织.md)：已初始化，待学习；源码与运行待验证。 |
| 转人工与会话归属 | 追踪转人工的判断、正式 Action（动作）、Handoff Reason（移交原因）记录与 Conversation 处理归属变化；区分 Agent 之间移交与转给人工。 | [Chatwoot](Chatwoot/转人工与会话归属.md)：已初始化，待学习；源码与运行待验证。 |
| Agent记忆分层 | 对比当前 Run（一次执行）的消息历史、同一用户的长期 Memory（记忆）、共享 FAQ（常见问答）的 Scope（作用范围）、持久化与生命周期。 | [Chatwoot](Chatwoot/Agent记忆分层.md)：已初始化，待学习；源码与运行待验证。 |
| Agent评估闭环 | 核验 Eval（评估）如何关联回答质量、工具、转人工、Human Reply（人工回复）、Reopen（会话重开）和最终 Outcome（处理结果），以及哪些是评估、哪些只是业务统计。 | [Chatwoot](Chatwoot/Agent评估闭环.md)：已初始化，待学习；源码与运行待验证。 |
| 客服Agent生产架构 | 将会话、任务编排、Agent Runtime（执行支撑程序）、Scenario、工具、移交、记忆、并发与评估拼成完整架构图，补充失败与恢复边界。 | [Chatwoot](Chatwoot/客服Agent生产架构.md)：已初始化，待学习；源码与运行待验证。 |
| 输入预测 | Composer（消息输入框）的候选输入如何生成；触发时机、上下文来源、预测分支、接受与丢弃的边界。 | [Codex](Codex/输入预测模块.md)：已初始化；预测分支协议已静态核验，桌面端完整链路待验证。 |
| 长任务目标与持续执行 | 目标持久化、跨轮继续、停止条件、预算与完成审查；与通用长任务知识分开学习。 | [Codex Goal](Codex/goal实现深入解析.md)：已初始化，暂缓学习；源码与运行待验证。 |
| 会话管理 | 会话持久化、重启恢复、模型上下文重建与上下文压缩；先学“重启后如何接着聊”。 | [Pi Coding Agent](<Pi Coding Agent/会话管理模块.md>)：学习中；固定版本源码初读，未运行验证。 |
| 上下文压缩策略 | 从“100 条消息触发自动压缩”研究触发条件、保留预算、切分点与摘要生成。 | [Pi Coding Agent](<Pi Coding Agent/上下文压缩策略模块.md>)：学习中；默认策略与切分依据已静态核验，未运行验证。 |
| 工具管理 | 注册与启用、描述与参数、调用执行、权限、结果、错误和观测。 | [Pi Coding Agent](<Pi Coding Agent/工具管理模块.md>)：学习中；工具机制地图已静态梳理，未运行验证；后续逐项深入。<br>[Chatwoot](Chatwoot/工具管理与执行.md)：已初始化，待学习；配置、解析、校验、装配、执行与结果回填待核验。 |
| 运行生命周期管理 | 启动、执行状态、中断与取消、完成与失败收尾；先学流式调用时的取消。 | [Pi Coding Agent](<Pi Coding Agent/运行生命周期管理模块.md>)：已初始化；部分取消路径已静态核验，未运行验证。 |
| Agent 循环与对话状态 | 执行循环中的上下文、状态、工具、移交、最终输出与轮数限制。 | [Chatwoot](Chatwoot/Agent循环与对话状态.md)：已初始化，待学习；源码与运行待验证。 |

## 旧专题入口

- [开源项目权限审批设计](../learning-notes/work-pool/W-2026-005-study-production-agent-permissions-and-approval-权限审批/开源项目权限审批设计/子项目.md)：原有项目候选和权限审批阅读路线，保留为历史来源；后续项目模块学习通过 Prompt 7 集中记录。

旧专题尚未迁移，其项目不计入上面的“已加入”索引。
