# C-2026-011：Agent 可观测性与轨迹回归评测学习

- Status: active
- Area: Agent Harness / Runtime / Observability / Eval / Security
- Difficulty: D2 → D3；入门讲解从 D1 概念开始
- Started: 2026-09-23
- Source Task: W-2026-031-study-agent-observability-and-trajectory-evals (原任务卡已迁入本 Change)
- 学习入口：[总览](../../learning-notes/work-pool/W-2026-031-study-agent-observability-and-trajectory-evals-Agent可观测/LEARNING_NOTES.md)、[知识图谱](../../learning-notes/work-pool/W-2026-031-study-agent-observability-and-trajectory-evals-Agent可观测/Agent可观测与轨迹评测知识图谱.md)
- Start Trigger: 用户同意混合学习模式，并明确表示目前对该主题不熟悉、要求先介绍核心概念；因此先做概念入门，不直接安装或实现观测 SDK。

## 本次学习范围

按原任务卡 W-2026-031 的目标学习通用 Agent Harness / Runtime 的执行可观测性、OTLP 导出和轨迹级安全回归。原卡的 Objective、Work、Expected Output、Success Criteria 与 Boundaries 已在本 Change 中转化为上述范围、第一小步和结束验收要求。必学主线覆盖：

1. Trace、Span、Span Event、Log、Metric、State、Audit、Policy 与 Eval 的基本概念和边界；
2. 从 Model Call、Tool Call、Workspace Change 到 Subagent 的因果关联；
3. OTLP 在采集与传输链路中的作用，与语义约定、Collector、后端和评测的区别；
4. 通过固定任务、确定性断言和失败场景验证权限、顺序、审批、工作区和副作用边界；
5. 敏感数据最小化、观测缺失和“记录到轨迹”不等于“行为安全”的证据边界。

初学阶段先用仓库现有 Agent Loop、工具、权限与 Subagent 例子建立心智模型，再按混合线检查官方资料和一个窄范围实现；暂不安装观测后端或修改教学代码。SDK 选型、配置和代码实验留待术语与数据流理解后再决定。

## 学习目标校准

用户明确本次学习的实际目标是：别人提出“建设 Agent 可观测与回归评测体系”时，能够用自己的话讲清楚需求在解决什么问题、一般怎样组成、关键术语如何分层，并能用一个例子解释工具权限、执行顺序和副作用边界怎样被验证。

因此，以可复述的概念模型、清晰的数据流、常见方案取舍和证据边界作为首要验收；源码阅读和最小实验用于建立可信例子，不默认交付完整观测平台或生产部署。原任务卡要求的 Trace 契约、轨迹断言和失败场景仍用于支撑解释能力，但实验范围取最小可说明机制的切片。

## 初始检查与依据

- 前置基础：s01 的 Agent Loop、s02 的工具请求/执行/结果回传、s03 的执行前权限检查、s04 的生命周期 Hook、s06 的 Subagent 上下文与共享工作区边界、s11 的失败和重试边界均有学习笔记。它们提供链路组件，但不表示用户已掌握 Trace / Span / OTLP。
- 现有本地样本：[RAG Agent TraceCollector](../../projects/rag-agent-demo/rag_agent_demo/tracing.py) 是进程内结构化事件列表，不是 OTLP exporter；[Eval 说明](../../projects/rag-agent-demo/evals/README.md)已有 fake model 下的工具、ACL、拒答与来源断言，可作为后续轨迹评测基线。
- 直接关联：W-2026-012 研究 Skill 生命周期的 Trace / Eval；W-2026-005 / 006 定义权限与副作用机制；W-2026-015 / 020 研究 Subagent 生命周期及团队状态。这些任务分别保留其主题边界，本 Change 只复用和验证，不复制其全部范围。
- 当前没有 `specs/current/` 或 `specs/decisions/` 中相关的额外约束；现存 Changes 中 C-2026-009 与多 Agent 协作相关，可供后续查阅，但本次不改变其范围。
- 启动时 `git status --short` 显示用户已有 `C-2026-010-study-agent-sandbox.md` 和 W-2026-030 学习目录；本次未修改它们。
- 2026-09-23 已查阅 OpenTelemetry 官方 Trace 概念页、OTLP 规范页与 Context7 的 OpenTelemetry 文档。官方资料将 Span 定义为一次有开始/结束的工作单元，将 Span Event 作为 Span 生命周期中的时间点；OTLP 负责遥测数据的编码和传输。具体 Agent/GenAI 语义约定可能演进，后续正式学习时重新核对版本和稳定性。

## 第一小步

从一条已熟悉的链开始：用户请求 → 模型提出 Tool Call → Harness 检查权限 → 工具执行 → 结果回给模型。先解释为什么“最后答案”不足以还原中间发生了什么，再引入 Trace、Span 和 Event。第一小步验收方式是用户能用自己的话描述这三个概念各自承载的范围，并把它们放到这条链上；当前没有掌握结论，也没有运行或生产验证证据。

## 后续记录

具体学习过程、用户原始理解、来源、验证状态和未决问题记录在学习入口，不在 Change 中重复维护。结束时按原任务卡 Success Criteria 验收；如产生实现或长期约束，再按 `specs/README.md` 更新 Implementation、Current 或 Decision。未产生代码时不创建空 Implementation。
