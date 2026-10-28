# 第二阶段：从 Workshop 回到 Pir

> 本阶段用一条请求和一个失败场景切入，不通读全部 Rust/BFF/工具项目。最新版本、路径和符号以[本次源码核验报告](./Pir现状核验.md)为准；[旧 pir.md](../pir.md)只作历史补充，不混用两套目录。

本次源码基线：`D:/code/temp/d5/workspace-release/pir` @ `f72d2b164c26e855a012f896d2b5f1e471358b34`；BFF @ `2df13cdbe7e16a8de6902776559009ae5c13d9f7`。这是本地分别检出的版本，不是一起上线的证明。

## 为什么放在第二阶段

Workshop 的小循环把采集、评分、比较集中在少量文件；Pir 还涉及 BFF、Runtime、持久化、进程工具宿主和业务副作用。先理解闭环，再学习多层边界，复杂度才有落点。
不需要先熟练掌握 Rust；阅读时补 trait（接口契约）、enum（状态分支）、async（异步执行）等当步必需知识。

## 对照关系

| Workshop 中已学过的东西 | 到 Pir 后重点核对什么 |
|---|---|
| `runSupportConversation` 模型工具循环 | BFF/API 接入、策略检查、Runtime 的模型与工具循环 |
| SDK 的 Trace 和工具步骤 | 统一观测事件、sink 筛选、OTLP 导出、关联 ID |
| 完整消息作为评测输入 | Rust 内容摘要与 BFF 可选原文；是否有完整、可读、获准使用的证据 |
| 平台在线评委 | 配置、启用、触发规则和线上记录；没有证据就记待核验 |
| `run-dataset.ts` | `pir-eval` 的 case、runner、断言引擎与报告 |
| 修改提示词并对比实验 | 失败重放、基线报告、质量脚本、CI 接线与发布条件 |

## 按顺序阅读与验证

### B1：先画请求链

- 入口：报告中的 BFF stream handler → Pir turns handler → Runtime turn/model/tool。
- 问题：Session、用户交互轮次、Runtime turn、模型内部循环是否一一对应？谁创建与传播 ID？
- 产物：用一个只读或合成案例画时间线，标出请求、状态、工具结果和最终回复。
- 验收：能从最终回复倒查模型与工具；知道 SSE 只是向前端传流的协议，不是观测存储。

### B2：分清三条数据链

- 入口：ObservationEvent 与 observability sink；StreamEvent；history/store 的实现。
- 逐字段核对：谁产生、送给谁、原文还是摘要、何时截断、在哪里持久化、怎样关联。
- 特别检查：长度/hash 可辅助匹配与完整性检查，不能代替文本交给语义评委。
- 不把模型/工具 Span 的摘要策略推广到所有事件：`runtime.stream_event` 可能携带完整公共事件，须另查文件和 OTLP 日志中的敏感内容。
- 产物：一张“字段→来源→存储→用途→缺失边界”的小表。
- 验收：明确流事件、历史记录、Trace 各自能证明什么。

### B3：从发送到可见，核对观测与监控

- 入口：Langfuse sink/mapping/transport、Host 装配、BFF 原文采集与指标配置。
- 分开验证：源码支持、配置启用、记录产生、导出成功、平台可查五种状态。
- 最小练习：一条成功、一条失败/取消的请求；读取状态、耗时和终态，定位缺失记录。
- 验收：平台看不到记录时，能按采集→队列→网络→平台逐层定位；告警/面板是否部署单独取证。

### B4：从失败用例理解 Eval

- 起点优先选 `tool_failure_feedback`：工具失败时，Agent 是否错误声称业务已经完成；以本次报告确认的实际 case 为准。
- 顺序：case YAML → schema → runner target → assertions → report → main 退出码。
- 确认 `runtime` 与 `server` target 的边界、真实依赖与合成依赖差别。
- 产物：指出每条断言读取哪个字段、什么情况会误判；查看 `response/events/trace/transcript/report` 各自内容。
- 验收：能区分“工具被调用”“工具成功返回”“外部业务已完成”，不凭断言名称认定覆盖范围。

### B5：问题怎样进入重放与回归

- 入口：Debug 导出、fork、replay 模式与 BFF 权限校验；按报告定位真实文件。
- 对比 `turn_replay`、`full_replay`、`continue_next` 的起始上下文和执行范围。
- 明确：重跑 Agent 会重新作决策；读取历史不代表重新执行过工具。真实副作用、测试身份、幂等、外部状态必须隔离。
- 本次已发现 fork 继承源 `scope_id`、`continue_next` 复用源会话；先核对导出路由授权与独立测试 scope，不能拿生产 YAML 直接重跑。网关侧限制仍未核验。
- 产物：用合成或已脱敏数据准备一个可复现案例，保留取消、超时和结果未知状态。
- 验收：能解释“复现业务目标”与“逐步复制历史动作”的区别。

### B6：完成最小改进闭环

- 固定版本/模型/用例/环境/基线；先看原始失败证据，再提出一个明确原因与修改假设。
- 在独立实验范围定向改动 → 重跑原案例及相关回归 → 检查逐例差异和新失败。
- 对照质量配置、脚本与 CI，分别判断：支持运行、曾运行、失败能阻断、发布真实接入。
- 当前核验指出真实模型回归采用 observe 观察模式；需读清失败是否影响最终退出码，以及成本/延迟预算是否只是展示而非强制判定。
- 产物：一份改动前后报告，以及“已具备 / 配置依赖 / 尚未核验 / 需要补建”清单。
- 验收：没有运行的环节标待运行；不把计划、设计文档和测试源码当成线上效果。

## 实际源码入口

以下均来自本次核验；阅读时只跟当前步骤需要的符号，不要求提前通读。

| 步骤 | 优先入口 |
|---|---|
| B1 请求 | [BFF stream handler](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/handler/pir_stream.go) → [Runtime model](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-runtime/src/runtime/turn/model.rs) |
| B2 数据 | [ObservationEvent](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-observability/src/event.rs) → [EventRecorder](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-runtime/src/runtime/turn/events.rs) |
| B3 平台 | [Rust mapping](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/crates/pir-observability-langfuse/src/mapping.rs) ＋ [BFF recorder](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/handler/pir_langfuse.go) |
| B4 案例 | [tool_failure_feedback.yaml](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/cases/tool_failure_feedback.yaml) → [通用 runner](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/runner.rs) → [assertions](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/assertions.rs)；产品二进制是 `pir-popipo-eval` |
| B5 回放 | [pir_eval_export.go](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/handler/pir_eval_export.go) → [ForkSession](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/handler/pir.go) |
| B6 质量 | [report.rs](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/report.rs) → [quality/config.yaml](D:/code/temp/d5/workspace-release/pir/quality/config.yaml) → [release-promotion.py](D:/code/temp/d5/workspace-release/scripts/release-promotion.py) |

## 阶段出口与后续衔接

预计 6–8 次小课；每次只推进一个子问题。至少读懂一条真实源码链和一套可重复案例；运行资源未就绪时可先静态阅读，但不能通过运行验收。
之后进入[生产实践进阶](./03-生产实践进阶.md)：优先补当前切片暴露的数据缺口和评测缺口，再扩展告警、统计与发布治理。
