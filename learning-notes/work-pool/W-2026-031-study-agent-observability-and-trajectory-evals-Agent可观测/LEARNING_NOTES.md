# W-2026-031：Agent 可观测性与轨迹回归评测

> 学习状态：进行中，当前为概念入门。用户明确表示此前对本主题不熟悉；不把本次讲解、静态阅读或 Trace 中出现的字段记为已掌握或生产验证。

## 任务与学习入口

- 对应变更及当前任务范围：[C-2026-011](../../../specs/changes/C-2026-011-study-agent-observability-and-trajectory-evals.md)（原 W-2026-031 已按 Spec 流程迁入 Change）
- 知识地图：[Agent 可观测与轨迹评测知识图谱](./Agent可观测与轨迹评测知识图谱.md)
- 专业术语：[名词清单](./名词清单.md)——按知识块索引核心术语并提供简短解释
- 项目案例：[可观测与 PIR 评测](./可观测.md)——记录四个学习问题、项目文档中的质量门禁现状及证据边界；SDK 使用情况仍待查代码确认
- 关联本地基础：[`s01 Agent Loop`](../../../s01_agent_loop/LEARNING_NOTES.md)、[`s02 Tool Use`](../../../s02_tool_use/LEARNING_NOTES.md)、[`s03 Permission`](../../../s03_permission/LEARNING_NOTES.md)、[`s04 Hooks`](../../../s04_hooks/LEARNING_NOTES.md)、[`s06 Subagent`](../../../s06_subagent/LEARNING_NOTES.md)、[`s11 Error Recovery`](../../../s11_error_recovery/LEARNING_NOTES.md)
- 现有小样本：[`TraceCollector`](../../../projects/rag-agent-demo/rag_agent_demo/tracing.py)、[`Eval 说明`](../../../projects/rag-agent-demo/evals/README.md)

## 为什么学、学到哪里

一次 Agent 任务可能先后经过模型、权限判断、工具、文件系统和子 Agent。只看最后回答，无法知道中间是否越权、顺序是否错误、发生了哪些真实副作用。这个主题学习如何保留可关联的执行证据，并用可重复的轨迹断言发现行为回归。

主要位于 **Harness / Runtime 观测与验证层**：LLM 生成动作建议；Harness / Runtime 控制动作、状态和边界；OpenTelemetry 负责生成、传播及导出观测信号；Eval 检查结果与轨迹是否符合预期。OTLP 是其中的传输协议，不是安全授权规则。

原始理解 / 要求：用户表示“这部分我一点不懂”，希望先介绍核心概念。此为学习起点，不是对其理解状态的评价。

## 学习目的：能向别人解释这句话

用户进一步明确，学习的目标是：别人问到“建设 Agent 可观测与回归评测体系”时，自己能答上来，而不是默认要亲自搭建一整套生产观测平台。

最终需要能用自己的话说明：

- 为什么只看最终回答不够，需要观察模型、工具、工作区和子 Agent 的执行路径；
- Trace / Span / Event 如何表示这些步骤和事件，OTLP 在导出链路中负责什么；
- 为什么除了看最终答案，还要对工具权限、调用顺序、审批和副作用写轨迹评测与安全断言；
- 这套体系不能替代执行前授权，也不能证明没有被记录的副作用绝对没有发生。

后续源码与实验以提供可信例子、帮助解释机制为目的；不把搭建完整平台作为默认成果。掌握状态仍须通过用户复述或相应证据确认，目前未验收。

## 学习模式与节奏

- **模式：混合线**——概念模型 → 官方资料 / 固定版本源码 → 最小可重复实验 → 失败与恢复 → 生产取舍。
- **难度：D2→D3 的主题，入门解释按 D1 节奏。**每轮先讲清一个问题，再请用户用自己的话复述或做一个小判断。
- **第一小步：**使用已学过的 Tool 执行链引出 Trace、Span、Event；理解它们各自记录什么范围。
- **最终表达能力：**能面向别人讲清楚“问题 → 观测链路 → 轨迹评测 → 安全边界”，并用一个允许与拒绝的工具调用例子支撑说明。
- **本阶段不做：**不预先安装依赖、选择商业观测平台、调用付费模型或修改教学代码。

## 模块与掌握状态

| 模块 | 状态 | 入口 |
|---|---|---|
| Trace / Span / Event 入门与 Agent 执行链映射 | 🔴 待验证 | 计划作为第一模块，尚未验收 |
| Log / Metric / State / Audit / Policy 的边界 | 🔴 待验证 | 计划模块 |
| OTLP、Collector 与语义约定 | 🔴 待验证 | 计划模块；开始时核对当前官方版本 |
| 轨迹回归、确定性安全断言与失败恢复 | 🔴 待验证 | 计划模块 |
| 数据最小化、采样和观测失效策略 | 🔴 待验证 | 计划模块 |

## 术语速查

本章术语按知识块维护在[名词清单](./名词清单.md)。核心入门词是 Trace、Span、Span Event 和 OTLP；当前均待用户复述验证。

## 证据与来源

- OpenTelemetry 官方 [Traces 概念说明](https://opentelemetry.io/docs/concepts/signals/traces/)：说明 Trace / Span、父子结构、Event 与 Link 的基础概念；2026-09-23 查阅。
- OpenTelemetry 官方 [OTLP 规范](https://opentelemetry.io/docs/specs/otlp/)：说明 OTLP 在遥测源、Collector 和后端间承载编码与传输；当前页面标示 Trace、Metric、Log 信号为 Stable，2026-09-23 查阅。
- OpenTelemetry 官方 [GenAI 语义约定入口](https://opentelemetry.io/docs/specs/semconv/gen-ai/)：语义约定与版本状态在正式学习时重新核验；本阶段不声称某一 Agent 字段已经稳定。
- Context7 2026-09-23 查询 `/open-telemetry/opentelemetry.io` 的概念资料；未查 SDK 安装、语言配置或实际 Exporter 行为。
- 本地教学实现与实验事实尚未重新运行；静态代码不等于当前运行 Trace，更不代表生产验证。

## 未决问题与下一步

- 核心词汇是否能映射到熟悉的 Agent Loop，还需要用户复述后判断。
- 生产 Trace 中如何关联并行和异步 Subagent、重试与真实副作用，是后续主线问题。
- PIR 的 `popipo-quality` 文档展示了共享质量门禁基础；真实模型轨迹评测仍需结合 runner、源码和运行报告核实。
- 下一步只推进：用一个简单成功链和一个权限拒绝链识别哪些是 Span、哪些是 Event，为什么。
