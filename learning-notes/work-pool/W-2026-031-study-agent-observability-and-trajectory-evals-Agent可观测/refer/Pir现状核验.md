# Pir 可观测、监控、评测与持续优化现状核验

> 核验日期：2026-10-28（Asia/Shanghai）。用途：为“Langfuse Workshop → 自己的 Pir 项目 → 生产实践进阶”学习路线提供项目事实。
> 本文件是本次专属产物；没有修改业务代码、配置、其他学习笔记或 Git 提交。文中的“已实现”指固定版本中的源码实现，不等于当前线上启用、测试已通过或学习者已掌握。

## 1. 先读结论

Pir 已有一套相当完整的**观测与确定性回归基础**：结构化事件、跨服务关联 ID、日志/指标/Trace 多出口、BFF 原文捕获、Langfuse 多目标导出、YAML 轨迹评测、会话导出、报告比较、Quality Spec 与发布证据校验。

但“采集 → 找问题 → 生成样本 → 隔离复现 → 评测 → 改进 → 发布”的全链路尚未自动贯通。当前更准确的描述是：**若干工程模块已经连接，问题归因、样本审查和改进仍需要人；安全的生产 Trace 重放、重复试验、语义评委和运营预算门禁还有缺口。**

最容易混淆的六点：

1. **Langfuse 里的内容不全来自 Rust sink。** Rust 的 model/tool span 通常存长度、类型和哈希；BFF 单独捕获用户输入、模型请求/输出、工具结果并发给 Langfuse。
2. **Rust 也不是“所有内容都只留哈希”。** `runtime.stream_event` 包含完整公共事件对象，文件和通用 OTLP 日志可能保留其文本/参数/结果。必须按事件和出口判断数据边界。
3. **Session 历史、执行事件、遥测 Trace 是不同存储。** Popipo BFF 后端没有持久化通用 Turn/EventStore；会话回放需要的历史与工具块另行持久化。
4. **`trace_has_terminal_span` 名字比实际能力强。** 当前断言检查本轮终态事件/状态，不验证 Langfuse 是否收到 span。
5. **存在 baseline 对比，但没有完整质量预算。** 当前报告主要比较通过/失败、失败分类和 case 变化，没有重复试验的分布、token/cost/延迟预算对比。
6. **Quality workflow 通过不等于所有 Agent eval 是硬门禁。** `eval-regression` 明确配置为 `enforcement: observation`，且 nightly/release 执行的命令仍是 `--suite pr`。

## 2. 核验版本、范围与证据等级

### 2.1 固定版本

| 对象 | 绝对路径 | 分支 / HEAD | 本次状态 |
|---|---|---|---|
| Pir 主样本 | `D:/code/temp/d5/workspace-release/pir` | `main` / `f72d2b164c26e855a012f896d2b5f1e471358b34` | 干净；最近提交 2026-10-27 |
| Go BFF | `D:/code/temp/d5/workspace-release/popipo-bff` | `main` / `2df13cdbe7e16a8de6902776559009ae5c13d9f7` | 干净 |
| 发布编排 | `D:/code/temp/d5/workspace-release` | `fix/video-upscale-mediakit-base-url` / `fc755df65930fa9c45dcc3d46bcdd74f02c03719` | 已有 `.gitignore`、markitdown 子模块和复盘文件等改动；未动 |
| 共享质量/监控补充样本 | `D:/code/temp/d5/workspace` | HEAD `ac460992dc478ec7b2a9daf0a5f16282869c789c` | 有既存配置、脚本和子模块改动；所引用质量源码、dashboard、monitor README 未出现本地 diff |
| 组件 Quality action 实际 pin | workspace 仓库历史对象 | `bf889327f1abcb53f25a89ff747993cf54dc1160` | 用只读 `git show` 核对 action 与 decision 逻辑 |

以前的 `D:/code/temp/d5/pir` 停在 `cef243f…`，本次没有将旧目录的行为当作当前结论。上一份简历调研主版本为 `bfe58adf…`，本次重新核对了更新后的 `f72d2b16…`。

这不是一个单仓库原子快照：相关组件分别有自己的 HEAD；本次没有刷新远端、检查服务器镜像或读取线上平台。不能推定以上版本恰好一起部署。

### 2.2 证据用语

| 标记 | 含义 | 本次是否有 |
|---|---|---|
| S：源码确认 | 阅读实现、配置、工作流，或做只读静态解析 | 有 |
| T：测试存在 | 阅读测试入口和断言，只证明设计了相应检验 | 有，不代表本次通过 |
| H：历史记录 | 仓库文档记录过运行/线上回查 | 有，未重新验证 |
| R：本次运行 | 本轮亲自执行被测系统并保存结果 | 仅静态计数/解析；无 Agent/Exporter/Eval 运行 |
| U：线上未知 | 实际部署、凭据、连通性、仪表盘、告警和结果 | 未验证 |

本机没有可用的 `cargo`、`rustc`、`go`；Pir 主样本没有 `target/` 或 `.quality/` 结果目录。本次没有安装依赖、启动服务、调用模型、访问生产日志或发送告警。

阅读范围覆盖 kernel observability/runtime、native/OTLP/Langfuse adapters、Popipo Host/BFF、generic/product eval、Quality config/CI、发布校验，以及共享仓库中能找到的 dashboard 和监控资产。不是对所有工具内部业务逻辑的安全审计。

## 3. 先建立数据流：请求、事件、事实和遥测分别去哪

### 3.1 一次产品请求

```text
产品调用方
  → Go BFF /api/v1/agent/stream
      鉴权/业务上下文，关联 request_id、trace_id，必要时预留 Langfuse root span
  → Rust Host /api/turns/stream
      接收 Trace/Parent headers，装配 Policy、Store、Provider、ToolHost
  → AgentRuntime
      历史重建/上下文 hooks → model.call → 工具执行 → ToolResult → 下一次模型调用
      → Message / ToolCallBlock 等事实写入 BFF
      → 公共 StreamEvent 持续发出
  → BFF 消费 Pir SSE，投影给前端；原文 recorder 观察同一条事件流
```

关键入口与符号：

- [BFF `PirStreamHandler` / `onPirEvent`](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/handler/pir_stream.go:1791)：原文 recorder 在前端投影之前观察 Pir 事件；校验事件 trace_id。
- [Rust `start_api_span` / `api_trace_context`](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/crates/pir-popipo-server/src/handlers/observation.rs:11)：解析 `x-request-id`、`x-trace-id`、`x-parent-span-id` 等；Trace ID 要求 32 位非零十六进制，span ID 16 位。
- [Runtime `EventRecorder::push_with_message_metadata`](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-runtime/src/runtime/turn/events.rs:115)：消息写入、event append、观测发射、调用方回调、内存收集。

### 3.2 四条数据通路

| 通路 | 数据 | 主要目的 | 关键区别 |
|---|---|---|---|
| 公共事件流 | 文本 delta、工具开始/参数/完成、用户输入、提交事实、turn 终态 | 驱动 UI 和调用方 | 事件抵达调用方不等于遥测后端已收妥 |
| 业务/会话事实 | Session、Message、ToolCallBlock、工作区版本、媒体任务等 | 下一轮上下文、产品历史、实际业务状态 | 事实源在 BFF/数据库，不是 Langfuse |
| 遥测事件/Trace/Log | ObservationEvent、父子 span、错误、耗时、上下文来源等 | 定位执行问题、关联多个服务 | 是否有原文由事件/出口共同决定 |
| 聚合指标 | 请求数、耗时分布、token/cost、工具/进程池/导出错误等 | 趋势、告警和容量观察 | 聚合指标不能替代单次轨迹与业务状态 |

Popipo 的 [HistoryStore 装配](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/crates/pir-popipo-bff/src/lib.rs:5637)为 Session、Message、ToolCallBlock 使用 BFF adapter，但通用 Event/Turn 使用 `NonDurableEventStore` / `NonDurableTurnStore`。因此 [facts HTTP handlers](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/crates/pir-popipo-server/src/handlers/facts.rs:13)会拒绝该后端的 durable turn/event 查询，引导使用观测查询。

**不能据“存在 `/api/turns/{id}/events`”推断生产保存了所有事件。** 要看具体 storage backend。

### 3.3 两种 Langfuse 写入路径

1. **Standalone Pir**：runtime observation → Rust `LangfuseTraceSink` → OTLP HTTP/protobuf → Langfuse。主要导出 `runtime.turn`、`model.call`、`tool.call`。
2. **BFF-root 产品请求**：BFF 预留 root `turn`，传递父关联；BFF 负责完整 root/model/tool observations。Rust mapper 识别整条 trace 的 BFF ownership，抑制自己的摘要副本，避免重复记录和 usage 双计。

[Rust sink 筛选](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/crates/pir-observability-langfuse/src/sink.rs:40)、[mapper 的 `on_started` / `on_terminal`](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/crates/pir-observability-langfuse/src/mapping.rs:48)、[BFF `BeginTrace` / `CompleteTrace`](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/observability/langfuse.go:259)共同决定最终树形。

BFF 会暂存子 spans，root 结束后把 root 放在批次首位一起发送。这意味着 Langfuse 中的 turn 记录不一定实时出现；`BeginTrace` 并不表示已提交到远端。进程崩溃仍可能丢失缓冲数据。

## 4. 实际采集字段与原文边界

### 4.1 通用事件和时间

[ObservationEvent](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-observability/src/event.rs:54)包含：

- 时间、level、target、event、status、duration_ms、error_code、error_message。
- trace/span/parent_span、request/user/project/scope/session/turn/message/model_call/tool_call/subagent/child_process/provider_request 等关联标识。
- `data_classification`：Operational、Audit、Debug、Billing；`attributes` 为事件专属载荷。
- `user_name` 带 `serde(skip)`，普通序列化不输出，但内存中的 Langfuse mapper 可以使用它。不能把跳过序列化理解为所有出口均不可见。

ObservationStatus 有 Started、Ok、Error、Cancelled、Timeout、Dropped。span 记录开始/结束、耗时；OTLP adapter 将其映射为 trace span。公共 `StreamEventPayload` 是另一套契约，当前 12 类：turn 开始/结束、消息、正文/推理 delta、工具开始/参数/完成、提交事实、运行状态、用户输入请求/解决。

### 4.2 按通路区分内容，不用“一律脱敏”概括

| 数据位置 | 实际内容 | 限制与风险边界 |
|---|---|---|
| Rust `model.call` | provider/model、轮次、工具数/名字、模型参数、usage、流式时序；输入/输出通过 `summarize_text` 记录 size/SHA256 | 摘要不是原文，也不是可直接用于语义评测的完整样本 |
| Rust `tool.call` | 工具、plugin、handler、执行结果、错误、metadata；参数/结果常经 `summarize_value` | metadata 并不保证只有哈希；要检查具体工具生产者 |
| Rust `runtime.stream_event` | `serde_json::to_value(event)`，包含完整公共事件 | 可能含文本 delta、工具 input/output、用户输入等；FileJsonl 和通用 OTLP Log 不能默认视为无正文 |
| BFF turn recorder | 用户问题、分段助手内容、tool args/result、用户输入 questions/answers、终态、摘要、错误、TTFT/最长工具等 | 仅 raw capture 开启才创建；多数大值受 capture 上限处理，但不是通用 PII 检测器 |
| BFF LLM capture | 实际请求中的 messages/system/tools、模型参数，响应 content/reasoning_content/tool_calls、provider usage/cache 统计 | 请求 body 做字段选择，不采集整个 HTTP headers；正文里本身含有秘密时，截断不能消除它 |
| BFF 历史/工具块 | 原始消息、模型回放 input/result、产品结果、摘要/metadata | 与遥测保留策略不同；模型回放不依赖 Langfuse 原文反查 |
| Eval artifacts | 响应、公共事件、transcript，可能还有 query_bff/query_trace 返回数据 | 写产物处未统一应用 BFF capture 上限或通用脱敏；样本与产物需要单独治理 |

源码入口：

- [哈希摘要函数](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-observability/src/summary.rs:4)：文本 size 是 UTF-8 字节数；Value 记录 JSON 类型、序列化字节数、SHA256。
- [model.call 埋点](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-runtime/src/runtime/turn/model.rs:310)。
- [完整 stream_event 的 observation 包装](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-runtime/src/runtime/turn/events.rs:290)。
- [BFF `newPirLangfuseTurnRecorder`](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/handler/pir_langfuse.go:61)、[`Observe`](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/handler/pir_langfuse.go:99)、[`boundedPirLangfuseValue`](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/handler/pir_langfuse.go:565)。
- [BFF `newLangfuseLLMCapture` / `observeSSELine`](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/service/llm/langfuse.go:34)。

### 4.3 截断的精确含义

- BFF `CaptureMaxBytes` 默认 **1 MiB（1,048,576 字节）**；大 JSON 值改成 `{truncated: true, preview: ...}`；content/reasoning builder 分别按字节截断。
- turn 摘要中的 user/assistant preview 为 240 个 rune，status message 的局部 helper 为 200 个 rune。这和大值的字节上限是两种口径。
- `traceInput()` 直接放入 `UserQuery`；代码并没有给所有 root input 统一套同一 bounding helper。因此不能宣布“任意 root/envelope 都严格不超过 1 MiB”。
- builder 的单值有界不等于所有中间集合、整条 turn 或所有并发 trace 的总内存有界。
- 哈希、字节截断、字段白名单是不同机制；均不自动构成业务正文的 PII（个人敏感信息）识别与删除。没有在这些出口上确认到统一的内容脱敏策略。
- Runtime 对 provider reasoning 仅发出显式公共推理事件，不把它当 assistant 正文写回模型历史；BFF 的 LLM capture 则可能单独捕获 `reasoning_content`。两处职责不同。

### 4.4 usage、token 和耗时

Rust `model.call` 记录 prompt/output token、total token、`cost_micros`，以及 stream open、first event、first content、first tool delta、事件计数。字段带 estimate 名称时，需要继续看 Provider：OpenAI adapter 可以映射上游 usage，缺失时不能自行宣称精确计费。

BFF LLM 捕获可映射 prompt/completion/total、cache read/write 等上游 usage；模型品牌和不同供应商字段兼容会影响完整性。Langfuse 的聚合成本显示、源码中的 cost_micros、真实计费账本不应直接等同。

## 5. 出口、监控与告警

### 5.1 实际采用的观测技术

| 部分 | 实际实现 |
|---|---|
| Rust instrumentation | 自定义 `ObservationEmitter` / `ObservationSpan`，不是依靠 OpenTelemetry SDK 自动完成采集 |
| Rust OTLP | 使用自有 protobuf 类型、`prost` 编码和 native HTTP transport，输出 traces/metrics/logs |
| BFF 指标 | 使用 Go OpenTelemetry metric SDK、PeriodicReader、OTLP/HTTP exporter |
| BFF Langfuse Trace | 构造 `LangfuseSpan`，使用 OTLP proto 编码并通过自有异步 exporter 发送 |
| Langfuse | 接收、存储和分析观测；不会因为接收到了 Trace 就代替本项目执行 Agent 或评测 |

证据：[Rust protobuf 定义](D:/code/temp/d5/workspace-release/pir/crates/capabilities/adapters/pir-observability-otlp/src/proto.rs:1)、[Go `NewProvider`](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/observability/otel.go:45)、[Go `LangfuseExporter`](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/observability/langfuse.go:145)。

### 5.2 Rust 支持的 sinks（数据接收出口）

[`ObservabilitySinkConfig`](D:/code/temp/d5/workspace-release/pir/crates/capabilities/adapters/pir-observability-native/src/sinks.rs:55)包含 StdoutJson、PrettyStdout、PrettyFile、RecentBuffer、FileJsonl、WebhookJson、OTLP。通用 OTLP 可以分别选择 traces/metrics/logs，支持指标标签白名单、聚合窗口和 exemplars（将指标样本关联到 trace）。

普通 `emit` 为 best effort；`emit_audit_required` 会要求可 fail-closed 的 sink，失败可阻止要求审计的路径。[Emitter 执行边界](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-observability/src/emitter.rs:99)。Langfuse 通过普通 `with_sink` 挂载，不能充当强制审计账本。配置了 `fail_closed=true` 的 file sink，也不表示所有普通诊断事件失败都会阻断业务。

通用 OTLP exporter 包含异步投递和指标聚合/熔断等机制；不要把 Langfuse exporter 的重试、队列参数推广到所有其他 sink。

### 5.3 Langfuse 多目标与启用条件

Rust 新形态需要 TOML 中的 `[observability.langfuse]` 和 `[[...targets]]` 声明，再由 `LANGFUSE_TARGETS` 显式选择，读取目标各自的凭据环境变量。未知目标、缺少值、新旧配置混用会返回配置错误；legacy 单目标只作为兼容路径保留。

BFF 新形态同样需要显式 `LANGFUSE_ENABLED`、目标 selector 和各目标配置；raw capture 还取决于 `LANGFUSE_RAW_CAPTURE_ENABLED`。OTLP 指标另有 `OTLP_ENABLED`，关闭时 meter provider 是 noop；Langfuse 出现数据不等于 metric 出口也启用了。

**当前检出的声明配置（S，不是线上状态）：**

- Pir `loop-host.toml` 和 `pir-prod.toml`：production=true、FileJsonl fail_closed、Langfuse enabled、queue=128、shutdown=20,000ms、max_attempts=3，声明 saas/self_host。
- `loop-host.local.toml`：FileJsonl＋通用 OTLP traces/metrics/logs，并配置 `local_otlp_stack` trace query；没有同样的显式 Langfuse targets 表。
- release-control 非秘密开关：test 选择 self_host；cn 选择 saas,self_host；BFF 两者 raw capture=true、capture_max_bytes=1048576。

配置入口：[生产 Host 配置](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/deploy/config/loop-host.toml:200)、[本地配置](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/deploy/config/loop-host.local.toml:196)、[Rust Langfuse 装配](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/crates/pir-observability-langfuse/src/assembly.rs:30)、[BFF 配置解析](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/config/loader.go:886)。没有在报告中复制凭据。

特别注意：这两份生产 Pir TOML **没有声明原生 OTLP metric sink**。Emitter 能生成指标，不代表这些指标会自动进入 Grafana/VictoriaMetrics；若没有其他装配或收集路径，生成的 MetricEvent 没有对应远端 metric 出口。BFF 的独立 OTel 指标与 Rust 的指标需要分别核验，不能用 dashboard 文件证明二者都已接通。

### 5.4 投递可靠性

Rust/BFF Langfuse 都有按目标分开的有界 worker/queue。相同 payload 独立投递；网络错误、408、429、5xx 有限重试，默认最多 3 次、初始 250ms、上限 2s；其他 4xx 不重试。运行失败不阻塞 Agent，退出限时排空。队列满、退出、崩溃、超过重试预算仍可能丢数据，没有确认到磁盘持久化遥测 outbox。

注意区分“配置默认 shutdown=5s”和“当前生产 TOML 指定 20s”。

证据：[Rust transport](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/crates/pir-observability-langfuse/src/transport.rs:29)、[BFF buffer/queue/retry](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/observability/langfuse.go:312)。

### 5.5 指标、dashboard 和告警做到哪

Rust 派生指标覆盖请求/turn/model/tool、上下文条目、store/workspace、subagent、async tool task、agent job、host capability、进程 worker/queue/drain/readiness/protocol、exporter failure。模型相关包括 token、cost、TTFT、流式事件计数和时序。[派生指标入口](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-observability/src/emitter.rs:236)。

BFF 有 provider 请求/耗时、Agent stream 阶段/总耗时、LLM stream TTFT/耗时和 worker 等指标。Langfuse exporter 自监控包括 `popipo_langfuse_export_total`、`popipo_langfuse_queue_dropped_total`、`popipo_langfuse_export_duration_ms`，带 destination/outcome/reason 标签。Rust 也记录目标投递和 drop 指标。

共享仓库有 [Grafana dashboard JSON](D:/code/temp/d5/workspace/deploy/grafana-cloud/dashboards/popipo-pir-observability-overview.json:1)与上传脚本，含 Provider error/p95、worker queue、Pir turn/model/tool/token/cost、exporter failure、日志查询等面板。**这证明面板配置存在，不证明指标已送达、查询兼容当前 backend 或面板无空值。**

[monitor README](D:/code/temp/d5/workspace/monitor/README.md:1)列出 auth 巡检和 Splunk error/warn → 飞书监控包；[脚本入口](D:/code/temp/d5/workspace/monitor/splunk_error_log/popipo_log_alert.py:174)可发通知，本次未执行。未在所读维护资产中确认到完整的 Agent 质量、token/cost、TTFT、trace 缺失等 SLO 告警规则及线上启用证据。工作流定时触发、操作手册中的频率不等于当前有活跃调度器。

### 5.6 Trace 查询不是 Langfuse Trace-to-eval

Native `TraceQueryClient` 的实现后端是 `LocalOtlpStack`：查询 Jaeger spans 和 VictoriaLogs 的 stream-event logs，合并为结果。[查询实现](D:/code/temp/d5/workspace-release/pir/crates/capabilities/adapters/pir-observability-native/src/query.rs:106)。它不是 Langfuse trace resolver。

Eval 的 `query_trace` 只是按 YAML endpoint 查询 JSON，可用 `PIR_EVAL_TRACE_URL` 切换 base URL；它不自动把 Langfuse Trace 转为可执行用例。

## 6. pir-eval 的架构与真实执行

### 6.1 两层引擎

| 模块 | 职责 |
|---|---|
| `crates/harness/pir-eval` | 通用 library：YAML case、模板/capture、runner、断言、产物、比较 |
| `crates/harness/popipo/eval` | `pir-popipo-eval` 二进制：产品 hooks、BFF 操作、产品 fixtures |
| `ProductEvalHooks` | 产品扩展边界：validate、执行扩展 step、特殊 runtime case、注册工具、准备 Host 配置 |

入口：[产品 main](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/src/main.rs:8)、[`ProductEvalHooks`](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/hooks.rs:16)、[`runner::run`](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/runner.rs:207)。

一次运行：加载并校验 case → 选择 suite/case → 准备环境/必要时启动 Host → **每个 case 执行一次** → 执行步骤/capture → 确定性断言 → 写 case artifacts → 汇总 report/可选 baseline comparison → 失败返回非零。

`--validate-only` 在创建输出目录、解析 case 和产品校验后返回，不连接 server；不能把它当作完成了行为评测。`load_dir` 只读取指定目录的直接 `.yaml` 文件，不递归；默认目录下 `popipo-debug/` 的两个导出例子不会自动进入 bundled suite。

### 6.2 Server target 与 Runtime target

- **Server**：HTTP 调 `/api/turns`，可连接现有 Host 或通过 command 启动 Host；可能调用真实 BFF/模型/媒体服务。是否调用真实模型取决于 Host 配置，不能从 `target: server` 单独判断。
- **Runtime**：进程内创建 runtime，使用 `EvalRuntimeModelProvider`（echo 式可观察模型，不是真实 LLM），可 seed 历史/工具块，适合框架协议检查。
- **特殊 Runtime fixture**：通过产品 hook 运行 capability-v2 Python sidecar、fake capability/model、协议身份/多路复用等。这检验桥接机制，不证明真实媒体理解质量或生产 artifact pair 可用。

入口：[runtime 路径](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/runner.rs:441)、[echo provider](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/runner.rs:1012)、[产品 fixture 分派](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/src/popipo_hooks.rs:409)。

### 6.3 YAML 轨迹与 fixtures

`EvalCase` 具有 version/id/suite/quality_keys/target/profile/workspace/model_params/vars/runtime/history 开关/trajectory/assertions。嵌套 DTO 使用 `deny_unknown_fields`，不存在的字段不是悄悄忽略。工具的 `input` 和通用 JSON 字段本身仍是开放 Value，不能把 schema 校验说成完整业务参数校验。

通用 step：`turn`、`tool_turn`、`query_trace`。Popipo 扩展：`query_bff`、`poll_tool`、`wait_subagent`。可从 JSON Pointer 或成功工具结果捕获标量，用 `{{step.capture}}` 传给下一步。`requested_tool` 绕过“让模型自己选工具”的环节，适合工具合同；不能证明模型会正确路由。

Runtime seed 支持 session/messages/tool_call_blocks、`seed_by_turns`、workspace assets 和 process-tool fixtures。Server 不能直接使用 seed_store；只有 runner 自己启动且有 `PIR_CONFIG_PATH` 时，才支持为工具历史生成 profile overlay，连接现成 server 时仍 fail-fast。

异步产品等待走 BFF 的单请求 wait 合同；超时可附最后状态和 cancel 响应。对 mirrored async task 的产品取消，不保证 Host 内子进程已停止，也不保证外部副作用撤销。[产品 lifecycle step](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/src/popipo_hooks.rs:491)。

### 6.4 当前样本规模（本次静态复核）

顶层 **28** 个 case：**21 server / 7 runtime**；suite 字面值为 **24 pr / 1 ppml / 3 production-compat**；另有子目录中的 2 个 debug export YAML。当前测试断言同样固定 28/21/7，见 [bundled case test](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/src/tests/mod.rs:26)。

`nightly` / `release` 的 `matches_suite` 返回所有 case，不是只匹配同名标签。**CLI suite=release 和 Quality workflow mode=release 又是不同参数；后者当前 runner command 仍为 suite=pr。**

代表性样本：

- [observability_terminal](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/cases/observability_terminal.yaml:1)：turn 终态与事件序列，不验证远端 Langfuse 到达。
- [tool_history_replay](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/cases/tool_history_replay.yaml:1)：seed 工具结果 marker，检查模型上下文重建；不是旧轨迹执行点恢复。
- [workspace_write_read_trajectory](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/cases/workspace_write_read_trajectory.yaml:1)：文件工具轨迹和结果。
- [media_no_false_claim](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/cases/media_no_false_claim.yaml:1)：禁止媒体工具并检查 URL 文本等；当前断言不能全面判断所有自然语言“虚假完成声明”。
- [capability_v2_status_multiplex_four_parents](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/cases/capability_v2_status_multiplex_four_parents.yaml:1)：受控 fixture 的并发/协议事实。

### 6.5 19 类确定性断言及其能力边界

[`AssertionKind`](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/case.rs:765)：

| 类别 | 具体断言 | 实际判断依据 |
|---|---|---|
| 终态/文本 | turn_status、output_contains、output_not_contains、user_message_is_chinese | 字段或子串；Chinese 判断仅检查包含汉字 |
| 工具轨迹 | tool_called、tool_not_called、tool_called_once、tool_succeeded、tool_order | 公共事件与工具结果；order 为有序子序列，不必相邻 |
| 工具参数/结果 | tool_args_match、tool_result_match | JSON Pointer、相等或 contains；主要查看匹配到的首个 input/成功结果 |
| 副作用/声明 | side_effect_exists、no_claim_without_tool_result | 提交事件；指定 claim 子串是否出现且有成功工具结果 |
| 回放/观测 | history_replayed、trace_has_terminal_span | marker 出现在输出；终态 turn 事件或状态 |
| 事件/JSON | event_sequence、event_exists、json_pointer_equals、json_pointer_contains | 有序事件、条件事件、响应字段 |

几个不能省略的限制：

- [`NoClaimWithoutToolResult`](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/assertions.rs:256)是指定子串检查，不是通用语义因果评委。
- [`TraceHasTerminalSpan`](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/assertions.rs:281)调用 `has_terminal_event`，不是远端 exporter ACK 验证。
- `side_effect_exists` 依赖被采集到的事件；证明真实最终业务状态时还需要 query_bff 或直接状态 oracle（判定依据）。
- 断言发现的是观测范围内的不符；未记录到事件不自动证明“绝无副作用”。

失败分类枚举有 10 类，包括 tool routing/args、side effect、causal claim、history replay、observability、provider、timeout、judge quality、case schema。`JudgeQuality` 这个分类名**不代表已经实现 LLM judge**。

## 7. 回放、产物与 baseline

### 7.1 “回放”至少有三种含义

| 名称 | 当前实现 | 不保证什么 |
|---|---|---|
| 上下文历史回放 | 将持久化消息/完整 terminal 工具块重建到下一次模型请求 | 不重新执行旧工具，不保证重启恢复任意执行点 |
| BFF Session → Eval YAML | 从历史消息和工具块提取轨迹、用户输入和工具断言 | 不代表已复制全部工作区/模型环境，不是 Langfuse Trace 导出 |
| Eval 重新执行 | 对新 runtime 或 server 发起请求，重新生成结果 | 不是逐字确定性录像；可能产生新写入或媒体成本 |

### 7.2 BFF 三种导出模式

[`DownloadSessionEvalYAML` / `exportSessionEvalYAML`](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/handler/pir_eval_export.go:80)直接查询 Session、Messages、ToolCallBlocks，各列表上限 5000。没有分页完整性证明时，不宜称任意超长会话完整导出。

- `full_replay`：把用户 turns 生成新会话的多步请求；添加历史观察到的工具调用/成功/顺序断言。
- `turn_replay`：先调用 fork，拷贝目标 message 之前的上下文，再执行指定用户轮；断言过滤使用工具名 read/list/get/query/search/check/poll 前缀启发式。它不是可信 capability effect 声明，人工审查不可省。
- `continue_next`：直接复用源 session，继续下一轮；不是隔离重放。

重要安全缺口：当前 [debug YAML 路由](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/server/router.go:453)位于普通 Auth group 之前，handler 本身未执行等效的 tenant/owner 校验。这里只能确认路由实现，不知道生产网关是否另有阻断；不能因为知道 session_id 就视为授权。

[`ForkSession`](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/handler/pir.go:492)会继承源 `scope_id`。更换 user 或生成新 session 不等于复制出隔离工作区；不能直接在生产源项目执行导出 YAML。本报告不执行这些路径。

### 7.3 本次运行应生成什么

当前实现的默认目录为 `target/pir-eval/<run_id>/`：

```text
report.json
cases/<case_id>/response.json
cases/<case_id>/events.json
cases/<case_id>/trace.json
cases/<case_id>/transcript.md
```

[`write_case_artifacts` / `trace_summary`](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/runner.rs:1318)中的 `trace.json` **只汇总 trace_ids、turn_ids、terminal_events**，不是从 Langfuse 下载的完整 span tree。若步骤显式 query_trace，其响应另在 response.json 中。

报告记录 run/suite/model/provider/时间、case 成败、失败类型、artifact path、quality_keys 和可选 comparison。没有结构化保存所有源码/Prompt/工具/schema/数据集版本，也没有每 trial 延迟/TTFT/token/cache/cost 汇总。目录名或日志中出现版本，不能代替报告的可追溯字段。

### 7.4 baseline 已有，但不是完整门禁

- `--compare-to` / `PIR_EVAL_COMPARE_TO` 可以指定旧 report。
- CLI suite=release 未指定时，从同一输出目录按文件修改时间选择最近一个旧 report。
- comparison 记录 model/provider 变化、pass/fail 数差异、失败分类变化、New/Missing/StatusChanged 等 case 变化。
- 不会自动保证两次环境/用例/fixture/Prompt/工具版本一致；没有旧报告时可无 comparison。
- runner 最终失败条件是本轮有失败 case，**不是通用 baseline 性能退化阈值**。

入口：[baseline 选择](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/runner.rs:1428)、[比较模型](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/report.rs:54)。

## 8. 回归、Quality Spec 与发布怎样连接

### 8.1 组件代码 CI

[Pir CI](D:/code/temp/d5/workspace-release/pir/.github/workflows/ci.yml:1)执行依赖 gate、[check-code.sh](D:/code/temp/d5/workspace-release/pir/scripts/check-code.sh:1)、BFF 导出 YAML 解析合同与 mock e2e。check-code 包含架构检查、fmt、clippy、指定核心 crate WASM 编译与 workspace tests。

这主要证明编译、合同、mock 集成，不是每个 PR 调真实模型跑完整生产行为 suite。

### 8.2 Quality Spec → 测试绑定 → 证据

Quality Spec 是业务行为与通过条件；Rust 测试通过 `[Q:spec/scenario/assertion]` 注释绑定，eval YAML 通过 `quality_keys` 关联。[component config](D:/code/temp/d5/workspace-release/pir/quality/config.yaml:1)定义：

- rustfmt：static，PR/nightly/release 必跑。
- eval-contract：`cargo test ... -p pir-eval -p pir-popipo-eval`，各模式必跑。
- eval-regression：nightly/release，命令 `cargo run ... --suite pr`；`enforcement: observation`；要求 report 文件存在。

**观察模式结果会被记录，但失败不按 required runner 一样阻断。** 共享框架把绑定测试所在 runner 的整体结果映射到 assertion，不能仅凭绑定存在就证明每个测试确实独立验证了那句业务预期。必须阅读断言有效性。

例如 Core Spec 的“禁止虚假完成声明”比 `media_no_false_claim` 中当前可执行的禁工具/禁 URL 断言更宽；需要专门评估是否遗漏不带 URL 的虚假自然语言声明。

[Quality workflow](D:/code/temp/d5/workspace-release/pir/.github/workflows/quality.yml:1)有定时及手动 nightly/release；实际 action pin 为 `bf889327…`，报告带 framework SHA。源码还出现 `QUALITY_WORKSPACE_SHA=9083fd34…`，应核对实际 action/框架输出，不能把两个 pin 当成同一版本。

共享框架核验入口：[executor](D:/code/temp/d5/workspace/quality/src/popipo_quality/executor.py:112)、[decision](D:/code/temp/d5/workspace/quality/src/popipo_quality/decision.py:46)。对应 action/decision 的关键行为还通过只读历史对象核对到组件所 pin 的 commit；没有执行该框架或查看 GitHub Actions 历史。

### 8.3 发布证据

release-control 的 [pir-release workflow](D:/code/temp/d5/workspace-release/.github/workflows/pir-release.yml:156)默认要求 release quality evidence；test 发布记录精确组件 SHA、镜像 digest 和质量证据，cn promotion 校验已测镜像与证据。

[`release-promotion.py::load_quality_evidence`](D:/code/temp/d5/workspace-release/scripts/release-promotion.py:73)检查 ready/ready_with_waiver、release mode、framework/spec hash、组件 revisions 等。工作流也有显式 `bypass_quality_gate` 路径，因此不能称所有发布绝无绕过；也没有证明当前某个镜像已按该流程完成。

**发布绑定了质量结论，不表示质量结论覆盖了所有 Agent 指标。** 当前 observation-mode eval、单次执行和不完整 oracle 的局限仍然存在。

## 9. 从生产问题到持续优化：已连接与缺口

| 环节 | 当前已实现 | 还缺什么 / 证据边界 |
|---|---|---|
| 采集执行 | runtime 事件、BFF 原文、指标、trace 关联与 exporter 自监控 | 不同路径覆盖不同；未验证线上送达率/丢失率/保留期 |
| 发现问题 | Langfuse 结构化字段、Grafana 配置、日志巡检包 | 未确认 Agent 质量/预算 SLO、告警路由和在线评委启用 |
| 归因 | request/turn/model/tool/任务 ID，可关联工具结果和业务状态 | 还需实际代表性 Trace；遥测不能代替业务事实 |
| 形成样本 | BFF session YAML；3 个生产行为派生合成 case | 缺安全 Langfuse trace resolver、不可变 source snapshot/provenance |
| 复现 | runtime seeds、server case、session fork | 缺每 trial 的隔离工作区/历史物化、cleanup handles；fork 仍继承 source scope |
| 评价行为 | 19 类确定性断言、合同/集成测试 | 缺完整语义质量 evaluator、评委校准和更强业务状态 oracle |
| 比较改动 | 固定 YAML、report comparison、quality linkage | 缺 repeated trials、flaky 分类、分位数与 token/cost/latency 预算 |
| 审核样本 | 目前人工编写/审查和仓库版本控制 | 缺 candidate→triage→promote/quarantine/retire 的可执行生命周期 |
| 发布 | 组件质量、聚合证据、SHA/hash/digest promotion | 未确认 Agent eval 已从 observation 提升为硬门禁；无自动质量回滚证据 |
| 回流 | 文档/手工调试可以把修复转为测试 | 未发现当前 runner 把 score/run/case 自动回写 Langfuse Dataset/Score 的完整链路 |

### 9.1 已有真实生产来源的先例，须区分历史记录

[PRODUCTION-DERIVED.md](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/cases/PRODUCTION-DERIVED.md:1)记录：对 2026-07-11 至 2026-08-10 的生产工具 observations 做聚合，从 5,195 条 root traces 抽取 648 条顺序样本，仅保留聚合和人工改写的合成输入，形成媒体、工作区、记忆三个 case。

这属于 **H：仓库记载的历史研究**；本次没有重新访问数据确认。它证明曾有人用生产观察选择覆盖重点，不代表自动 trace replay、成功率门槛或当前样本分布。

[0177 实现记录](D:/code/temp/d5/workspace-release/pir/docs/implementation/0177-production-derived-popipo-eval-coverage.md:1)记载过 3/3 黑盒对照通过；[0186 实现记录](D:/code/temp/d5/workspace-release/pir/docs/implementation/0186-langfuse-multi-target-export.md:1)记载过真实 SaaS/self-host 回查。都应保留日期和历史性质，不能在报告中改写为“本次验证通过”。

### 9.2 尚未实现的能力，不用目录名代替

`quality/harness/graders`、`rubrics`、`golden`、`reference` 当前主要是职责 README。没有在 generic/product eval 中确认到 LLM judge adapter、版本化 rubric 执行、人工 golden 校准、Langfuse Dataset Experiment runner、Prompt Registry 版本 A/B 或在线 feedback→score→case 自动闭环。

Quality Spec 里有 trials 配置，不代表 pir-eval 已按该值展开重复运行；当前 case 主循环只执行一次。存在 JudgeQuality 失败分类，也不等于语义评委存在。

源码与待办交叉依据：[eval follow-ups](D:/code/temp/d5/workspace-release/pir/docs/work-pool/0003-popipo-eval-followups.md:1)、[evaluation review](D:/code/temp/d5/workspace-release/pir/docs/review-pool/0002-popipo-evaluation-review.md:1)。待办是意图和边界说明，只有代码存在的部分才记为实现。

### 9.3 需要纠正的历史文档漂移

- `0005-langfuse-chat-preview-raw-text-source.md` 部分基线仍写“运行失败不重试”；当前 transport 和 0186 的 9 月 21 日修订已有限重试。以代码为准。
- 0177 文档记录当时 27 个 bundled cases；当前源码和测试是 28 个，不直接搬历史数字。
- 旧学习材料基于独立 `d5/pir` 版本，本文件按 workspace-release 重查，避免拿旧目录缺能力解释新版本。
- 旧笼统表述“Pir observation 不保留原文”应缩小为“部分 model/tool span 使用摘要”；stream_event 需要单独说明。

## 10. 从 Langfuse Workshop 回到 Pir 的初学者路线

这里仅提供 **Pir 源码阅读顺序**；主学习路线由学习对话维护，不在本文件开始部署或实现。

Workshop 官方入口：[langfuse/langfuse-workshop](https://github.com/langfuse/langfuse-workshop)。它的 tracing、prompt management、monitoring、datasets、experiments 等主题用于建立闭环心智模型；不要直接假设 Pir 已采用其 SDK、Prompt Registry 或 Experiment API。

| 顺序 | 接住 Workshop 的概念 | Pir 先看什么 | 这一轮只回答什么 |
|---|---|---|---|
| 1 | 一次 Agent 请求/工具步骤 | BFF `onPirEvent` → Host `stream_turn` → runtime `complete_model` | 谁执行，谁记录，谁保存事实？ |
| 2 | Trace/Observation 的关联 | `ObservationEvent`、`TraceContext`、`EventRecorder` | 一轮请求如何连到 model/tool/child？公共事件与 span 有何区别？ |
| 3 | 在平台查看 input/output | `summarize_text/value` → `stream_event_input` → BFF recorder / LLM capture | 平台看到的正文从哪来？何时只剩哈希？ |
| 4 | 数据如何送到平台 | `build_popipo_observation_emitter` → `LangfuseTraceSink` → `OtlpTransport` | 开关、筛选、重试、丢弃、trace ownership 在哪里？ |
| 5 | 从监控发现失败 | emitter 派生 metrics → dashboard；再看一条失败 Trace 与业务状态 | 指标只能提示什么？下一步怎样定位真实失败？ |
| 6 | 固定 Dataset / Case | `tool_history_replay.yaml` 和 `observability_terminal.yaml` → `EvalCase` | 输入、fixture、期望分别是什么？哪些不需要真实模型？ |
| 7 | Experiment / evaluator | `runner::run_case` → `evaluate_assertions` → `report.rs` | 谁重跑 Agent？谁判定？“有工具结果”与“任务已完成”是否等价？ |
| 8 | 改一个因素再比较 | `RunComparison` → quality/config → release-promotion | 哪些比较已经有，哪些仍是人工判断或未实现预算？ |
| 9 | 生产 Trace 加入 Dataset | `pir_eval_export.go` → `ForkSession` → follow-ups 0003 | 为什么导出不是安全复现，历史轨迹也不是标准答案？ |

每次学习只拿一个小样本贯穿：例如“读取文件后编辑，编辑发生冲突”。先讲请求和事实，再看 Trace，最后用工具顺序、参数、冲突状态、文件正文未被错误覆盖来形成断言。不先钻全部 exporter 或并发 worker 实现。

### 10.1 关键文件/符号速查

| 目的 | 文件与符号 |
|---|---|
| 看公共事件如何变成观测 | [events.rs](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-runtime/src/runtime/turn/events.rs:108)：`EventRecorder::push`、`stream_event_input` |
| 看模型观测字段 | [model.rs](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-runtime/src/runtime/turn/model.rs:310)：`complete_model` 内 model.call 埋点 |
| 看数据摘要 | [summary.rs](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-observability/src/summary.rs:4)：`summarize_value` / `summarize_text` |
| 看审计/普通观测区别 | [emitter.rs](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-observability/src/emitter.rs:99)：`emit` / `emit_audit_required` |
| 看真实产品 Chat Preview | [pir_langfuse.go](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/handler/pir_langfuse.go:99)：`Observe`、`finishTool`、`finishRoot` |
| 看模型原文/usage 捕获 | [llm/langfuse.go](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/service/llm/langfuse.go:34)：`newLangfuseLLMCapture`、`observeSSELine` |
| 看多目标重试 | [transport.rs](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/crates/pir-observability-langfuse/src/transport.rs:29)：`OtlpTransport`、`post_langfuse_with_retry` |
| 看 YAML 契约 | [case.rs](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/case.rs:109)：`EvalCase`、`TrajectoryStep`、`AssertionKind` |
| 看一次评测 | [runner.rs](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/runner.rs:312)：`run_case`、`run_server_case`、`run_runtime_case` |
| 看判断标准 | [assertions.rs](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/assertions.rs:63)：`evaluate_assertion` |
| 看报告比较 | [report.rs](D:/code/temp/d5/workspace-release/pir/crates/harness/pir-eval/src/report.rs:161)：`RunComparison::from_reports` |
| 看产品扩展 | [popipo_hooks.rs](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/src/popipo_hooks.rs:236)：`PopipoEvalHooks` |
| 看会话导出边界 | [pir_eval_export.go](D:/code/temp/d5/workspace-release/popipo-bff/backend/internal/handler/pir_eval_export.go:121)：`exportSessionEvalYAML` |
| 看什么还没做 | [0003 follow-ups](D:/code/temp/d5/workspace-release/pir/docs/work-pool/0003-popipo-eval-followups.md:35) |

### 10.2 学完 Pir 后适合补的生产议题

按当前缺口顺序学习，不把它们直接记为项目已有能力：

1. 观测契约和数据治理：稳定语义、敏感信息、采样、保留期、遥测丢失与审计不可丢的差别。
2. 真实业务 oracle：工具返回成功、事件成功、资产可用、账本一致、用户真正完成任务分别如何验证。
3. 失败样本工程：来源快照、去重/分层、人工审查、权限隔离、fixture、清理与 case 生命周期。
4. 评测有效性：确定性断言的漏检、语义评委校准、人工 golden、模型波动与重复试验。
5. 决策与发布：可比 baseline、质量/成本/延迟取舍、观察模式转硬门禁、灰度和回滚证据。

## 11. 本次验证记录与待核实清单

本次实际完成：

- 重新记录主样本与相关仓库 HEAD/status，检查 applicable AGENTS 和已有学习任务边界。
- 逐段阅读上述调用链、字段生产者、出口筛选/映射、runner、断言、replay/export、Quality 和发布逻辑。
- 用只读 Python 文本解析核对 28 个顶层 YAML、21/7 target、suite 口径、19 类断言和 debug 子目录；没有把静态解析称为 Rust schema/runtime 测试。
- 解析 Host TOML，仅提取非秘密开关；没有输出或复制 key/token。
- 核对组件 pin 的 Quality action/decision 历史对象，未运行它们。

阅读到的代表性测试：Langfuse targets/config/transport/mapping；case 未知字段拒绝；BFF 导出 YAML shape；echo runtime history replay；报告 baseline 对比；fixture 协议身份和多路复用。入口见 [eval tests](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/eval/src/tests/mod.rs:184)、[Langfuse transport tests](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/crates/pir-observability-langfuse/src/tests/transport_tests.rs:23)。本轮均未执行。

后续需要运行或线上证据才能回答：

- 哪个部署版本/目标实际启用哪些 sinks；Trace 是否缺失/重复/孤立；缓冲丢失率与保留期。
- Grafana 查询是否有数据，告警是否配置并能正确送达，谁负责处理。
- 当前质量 CI 是否成功、是否拿到真实模型/媒体服务、哪份 baseline 被固定。
- eval 产物对源用户、工作区和媒体资源是否充分隔离与清理。
- 某次改动是否真的提高业务成功率，并同时满足延迟、成本、安全和质量约束。

## 反思

1. **调查与决策中仍不确定什么？** 源码、配置声明、历史记录和线上事实不能混用。本次已纠正旧目录、旧 case 数量、“不重试”和“全部只存哈希”等容易误导学习路线的表述；没有运行工具链和线上查询，仍无法判断当前覆盖/送达/质量效果。共享质量仓库与组件 action pin 也需要按确切版本理解，不能把任意本地最新代码当 CI 运行版本。
2. **学习中容易遗漏什么？** 最容易把平台界面当作整个体系，把“记录到的成功”当作真实任务成功，把重放当作无副作用录像。建议每一阶段都回答五件事：输入来自哪、谁执行、谁判断、事实放哪、下一步怎样使用。先用一个受控 case 贯穿 Workshop 与 Pir，再扩展到安全样本、重复试验和发布预算，避免一开始被 exporter/并发细节打断主线。
