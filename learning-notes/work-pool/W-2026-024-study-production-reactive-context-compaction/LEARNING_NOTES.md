# W-2026-024：生产级 Reactive Context Compaction 学习

> 状态：已启动（2026-09-26）。当前完成任务迁移和学习入口初始化；项目源码尚未固定版本或核验。

## 任务与边界

- 任务范围与验收：[C-2026-014](../../../specs/changes/C-2026-014-study-production-reactive-context-compaction.md)
- 章节前置：[s08 Context Compact](../../../s08_context_compact/README.md)、[s11 Error Recovery](../../../s11_error_recovery/LEARNING_NOTES.md)
- 相关任务：[Tool Result 压缩与恢复 C-2026-012](../../../specs/changes/C-2026-012-study-tool-result-compaction-and-recovery.md)、[Agent Context 与 Prompt Cache W-2026-032](../W-2026-032-study-agent-context-organization-and-prompt-cache-Context缓存/LEARNING_NOTES.md)
- 学习模式：理论线 + 源码线 + 最小实验。先整理协议安全的压缩恢复模型，再核验开源项目调用链，最后用可控消息历史验证。
- 主问题：模型 API 拒绝当前输入太长时，Harness 怎样在有限预算内缩减活动上下文、保留任务状态和合法消息协议，并安全重试或明确停止？

## 学习入口

- [上下文压缩知识图谱](上下文压缩知识图谱.md)：从超限检测到安全恢复的机制地图。
- [名词清单](名词清单.md)：按知识块查阅关键术语。
- [开源项目上下文压缩设计索引](开源项目上下文压缩设计/那些子项目.md)：复用 W-2026-032 的六个开源项目，逐个核验其上下文压缩证据。

## 学习状态

| 知识块 | 状态 | 当前证据 |
| --- | --- | --- |
| 主动压缩与 Reactive Compact 的边界 | 🔴 待学习 | s08 已介绍教学机制；本任务尚未重新整理生产级边界 |
| Tool 消息配对与安全切点 | 🔴 待学习 | s11 暴露按最后五条截断的风险；待形成协议验证规则 |
| 摘要、结构化状态、Checkpoint 与 Artifact | 🔴 待学习 | 已建立知识图谱入口，尚无本任务证据 |
| 生产项目实现与恢复预算 | 🔴 待学习 | 六个项目调研页已初始化并做官方入口初筛；Pi 必看，OpenClaw 主样本候选，OpenHands SDK 深读对照，Codex CLI/Hermes Agent/CodeWhale 为补充；源码版本未固定 |
| 最小实验与故障恢复 | 🔴 待学习 | 尚未编写或运行实验 |

## 术语速查

首轮术语与系统层次见[名词清单](名词清单.md)。学习时需持续区分 Harness 的活动上下文、持久化 Transcript、运行状态 Checkpoint、业务系统权威状态和可回取 Artifact；保存了历史不等于模型当前仍能看到它。

## 当前进度与下一步

已完成：确认 s11 基础错误恢复验收完成；依 Spec 工作流将 W-2026-024 从 Work Pool 迁入 C-2026-014；建立知识图谱、名词清单和六个项目调研入口；初筛了官方压缩资料，按相关性区分主样本、对照和补充候选。

下一步先回答一个问题：Reactive Compact 与 proactive/auto/manual compaction 分别由什么事件触发，为什么需要独立的恢复预算？随后核验六个项目是否有可追踪的压缩实现，再选主样本与两个对照深入源码。
