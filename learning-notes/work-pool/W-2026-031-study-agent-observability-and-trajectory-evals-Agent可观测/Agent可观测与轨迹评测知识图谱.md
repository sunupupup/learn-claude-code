# Agent 可观测与轨迹评测知识图谱

> 本图谱是初版。概念层级先依据 OpenTelemetry 官方概念资料和本仓库教学链路建立；Agent 语义字段、具体 SDK 行为和实验结果仍待学习时核验。

## 1. 完整技术链路

```text
用户请求
  ↓
Agent Run（Harness / Runtime 控制一次任务）
  ├─ Model Call：输入上下文 → 模型返回文本或 Tool Call 请求
  ├─ Tool Call：参数校验 → Policy / AuthZ → 允许、拒绝或审批
  │     └─ Tool 执行 → 外部服务 / 文件系统真实副作用 → Tool Result
  ├─ Workspace Change：读写文件、补丁或其他工作区变化
  ├─ Subagent Run：父级委派 → 子级执行 → 结果与证据返回 → 父级验收
  └─ Run 结束：完成、拒绝、失败、部分完成或未知结果
        ↓
  Trace / Span / Event 关联执行证据
        ↓
  OpenTelemetry API / SDK 生成与处理遥测数据
        ↓
  OTLP 导出 → Collector / 接收端 → 观测后端
        ↓
  查询、故障诊断、指标分析
        ↓
  固定任务集 + 轨迹断言 + 人工/模型辅助评审 → 回归结论
```

**观测是记录和传输证据，Eval 是依据预先定义的标准判断行为。两者都不能代替执行前的授权和防护。**

## 2. 问题与扩展方案

| 面对的问题 | 改变哪个环节、怎么改 | 对应概念或方案 | 深入入口 |
|---|---|---|---|
| 只看到最终回答，不知道 Agent 经过了什么 | 把一次任务及其阶段用稳定关联 ID 串起来 | Trace 与 Span | [OpenTelemetry Traces](https://opentelemetry.io/docs/concepts/signals/traces/)；本地 `projects/rag-agent-demo/rag_agent_demo/tracing.py` |
| 不知道“某时刻”发生了什么 | 在进行中的操作记录带时间点的结构化事件 | Span Event | 同上；后续区分 Event、Log 与 Attribute |
| 跨服务 / 子进程后因果关系断开 | 传播 Trace Context，异步任务可按因果关系关联 | Context Propagation、Span Link | 官方 Trace 概念页；后续研究 Subagent / 队列例子 |
| 不同组件字段和命名各说各话 | 使用共同字段约定，同时记录其稳定状态和版本 | Semantic Conventions | [GenAI 语义约定入口](https://opentelemetry.io/docs/specs/semconv/gen-ai/)；版本待启动时复核 |
| 数据无法送到后端或绑定某厂商格式 | 按中立协议编码并传输 Trace / Metric / Log 数据 | OTLP | [OTLP 规范](https://opentelemetry.io/docs/specs/otlp/)；此协议不定义业务评判标准 |
| 轨迹发生危险调用但最终回答看起来正确 | 冻结任务，并对工具权限、先后顺序、审批和副作用写断言 | Trajectory Eval、确定性 Grader | 本地 [Eval 说明](../../../projects/rag-agent-demo/evals/README.md)；后续加入拒绝与失败用例 |
| 观测包含敏感上下文或漏掉故障 | 记录最少必要属性，设计脱敏、采样、访问与保留策略 | Data Minimization、Sampling、Retention | W-2026-012 相关边界；正式学习时查官方与项目策略 |

## 3. 概念之间的关系

```text
一次用户任务 / Agent Run
└─ Trace：跨步骤聚合的关联路径
   ├─ Span：一次有开始与结束的操作（可形成父子结构）
   │  ├─ Attributes：描述操作的键值属性
   │  ├─ Events：Span 内有意义的时间点
   │  └─ Status：该操作层面的结果状态
   └─ Links：当异步或并行因果关系不适合简单父子嵌套时建立关联

Telemetry（遥测数据）
├─ API / SDK：创建、管理、处理信号
├─ Semantic Conventions：约定常见操作如何命名与描述
├─ OTLP：编码与传输协议
└─ Collector / Backend：接收、处理、存储、查询与可视化

Evaluation（评测）
├─ Eval Set：固定输入与场景
├─ Oracle / Grader：判定预期行为的规则、模型或人工
└─ Regression Gate：比较版本变化是否引入回归
```

- Trace / Span 是观测数据模型；OTLP 是传输；Semantic Conventions 是命名与字段含义约定。三者分属不同环节。
- Span Event 像操作过程内的一次有时间点的记号；Log 是独立事件记录形式，两者可关联但不能简单视为同一对象。
- Trace 能证明“系统记录了哪些事件”；Eval 依据用例判断“记录到的行为是否符合要求”；AuthZ / Policy 在动作发生前决定“是否允许”。
- Trace 中出现 `tool_call` 字段，不证明 Tool 获得授权、真实执行成功或所有副作用均已记录。
- 子 Agent 的执行常跨异步边界；仅按时间戳排序不能可靠表达因果，可能需要传播 Trace Context 或 Link。

## 4. 主线与选学扩展

### 必学主线

1. Agent Run、Trace、Span 和 Event 的直觉及其映射；
2. Model / Tool / Workspace / Subagent 之间的因果关联；
3. OTLP、语义约定和观测后端各自负责什么；
4. 以固定轨迹验证工具权限、执行顺序、审批及副作用；
5. 一种失败或重试场景，以及敏感数据最小化边界。

### 选学扩展

- 具体供应商后端、采样算法、高基数指标和大规模 Collector 拓扑；
- 多区域分布式追踪、尾采样与长任务跨 Trace 关联；
- 在线评测、LLM-as-a-Judge 校准、SLO 与告警策略。

这些扩展不阻塞基础学习；遇到实际 SDK、部署或流量问题时再查当前官方资料。

## 5. 子笔记、Demo 与资料索引

### 已有本地入口

- 总览与学习状态：[`LEARNING_NOTES.md`](./LEARNING_NOTES.md)
- 术语导航：[`名词清单.md`](./名词清单.md)
- PIR 项目案例与评测证据边界：[`可观测.md`](./可观测.md)
- 任务范围和验收：[`C-2026-011`](../../../specs/changes/C-2026-011-study-agent-observability-and-trajectory-evals.md)
- 教学 Trace 收集器：[`tracing.py`](../../../projects/rag-agent-demo/rag_agent_demo/tracing.py)（进程内事件列表，不是 OTLP 导出实现）
- 冻结 Eval 的基础说明：[`evals/README.md`](../../../projects/rag-agent-demo/evals/README.md)
- 权限与 Tool 基础：[`s02`](../../../s02_tool_use/LEARNING_NOTES.md)、[`s03`](../../../s03_permission/LEARNING_NOTES.md)、[`s04`](../../../s04_hooks/LEARNING_NOTES.md)
- Subagent / 故障恢复基础：[`s06`](../../../s06_subagent/LEARNING_NOTES.md)、[`s11`](../../../s11_error_recovery/LEARNING_NOTES.md)

### 官方资料入口（2026-09-23 查阅）

- [OpenTelemetry Traces](https://opentelemetry.io/docs/concepts/signals/traces/)：Trace、Span、Event、Link、Context 的基础概念。
- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)：遥测数据协议的编码、传输和导出边界。
- [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)：GenAI 语义字段入口；具体稳定等级和版本需后续复核。

### 计划但尚不存在

- 中文模块笔记和小型轨迹回归实验：待用户逐小节学习后按需建立；当前没有已运行的 OTLP Collector / Exporter Demo。
