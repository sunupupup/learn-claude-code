# Pir：可观测、轨迹评估与问题改进的完整链路

> 整理日期：2026-10-23。本文整理当前对话和本地源码核对结果；只新增本文件，不更新学习进度或其他笔记。
> 证据状态：🟢 静态源码已核对；🟡 设计文档与实现范围分别说明；🔴 未连接线上 dev、未检查真实 Langfuse trace、未执行真实模型评估，不等于运行验证或学习验收完成。

## 1. 先理解整个链路

Pir 的实现把三个问题分开处理：

1. **可观测**：这一次请求经过了哪些模型和工具、耗时多少、哪里失败？
2. **可评估**：这些动作和结果是否符合某个场景的预期？
3. **后续处理**：把问题变成可复现用例，修改实现或提示词后再跑，判断有没有修好或产生回归。

```text
用户 query
  ↓
BFF 接收请求、传播关联 ID
  ↓
Pir API → Runtime turn → 模型调用 → 工具调用 → 最终回复/失败/取消
  │                           │
  ├─ ObservationEvent：结构化执行事件
  │    ├─ 日志/文件/OTLP 等配置的 sink
  │    ├─ 派生计数、耗时、Token、成本等 metric
  │    └─ Langfuse sink：筛选四类执行 span
  │
  ├─ StreamEvent：向 BFF/前端发送回复、工具结果和生命周期事件
  │    └─ BFF 可选采集：聊天预览、工具参数/结果、用户交互
  │
  └─ 持久化会话/消息/工具记录：支持后续恢复、排查和重放

问题排查 / Debug 导出
  ↓
YAML 场景：准备上下文 → 重放指定 turn → 检查断言
  ↓
pir-eval 输出报告与执行证据
  ↓
人工分析失败分类 → 修改提示词/工具/状态处理 → 回归与基线比较
```

**重要边界**：最后的“人工分析 → 定向修改”是工程使用流程；没有证据表明 Pir 会根据 Langfuse 分数自动修改提示词、自动发布或自动回滚。

### 术语速查

| 术语 | 本文含义 |
|---|---|
| Trace，调用链 | 用同一关联 ID 串起一次请求涉及的多个步骤 |
| Span，步骤区间 | API、turn、模型、工具等操作的开始到结束，含状态与耗时 |
| Event，事件 | 某个时间点发生的事情，例如工具开始、输出片段、turn 结束 |
| Metric，指标 | 次数、耗时分布、Token 等用于聚合统计的数值 |
| Sink，输出目的地 | 接收观测事件的日志文件、远端追踪服务等 |
| OTLP | OpenTelemetry 的遥测传输协议；这里向 Langfuse 传 span |
| Trajectory，执行轨迹 | 一轮或多轮中模型、工具、结果与状态的先后过程 |
| Assertion，断言 | 根据明确规则判断预期是否成立，例如工具必须成功 |
| Judge，质量裁判 | 用规则之外的评审方法判断语义质量；可以是人工或外部模型 |
| Regression，回归 | 修改后原来通过的场景变差或失败 |

## 2. 本次源码基线与阅读边界

| 仓库 | 本地目录 | 本次 HEAD |
|---|---|---|
| Pir | `D:\code\temp\d5\pir` | `cef243ffde57d29194e2db784e9ace2828eaae99` |
| Popipo BFF | `D:\code\temp\d5\popipo-bff` | `622eac7d0d39aceaa1ce30011d3e5f02646f02f2` |

核对时上述两个源码仓库 `git status --short` 均无输出。这里固定的是本地阅读基线，不是线上 dev 镜像版本。

下面把三类结论分开：

- **源码已实现**：可定位到注册、采集、转换或断言代码。
- **文档约定**：项目规范声明应该怎么做，不能代替逐个路径的实现证明。
- **后续建议**：基于这些能力可以建立的工程流程，不能写成项目已自动完成。

## 3. Query 的开始、结束和关联关系

### 3.1 请求、会话、轮次不是同一个范围

- `request_id`：一次 HTTP/stream 请求。
- `session_id`：可跨多轮持续的对话会话。
- `turn_id`：一次用户输入触发的一轮 Agent 执行。
- `model_call_id` / `tool_call_id`：本轮内部的模型调用和工具调用。
- `trace_id` / `span_id` / `parent_span_id`：把这些执行步骤关联起来。

一个 query 的业务处理通常落到一个 turn；多轮会话包含多个 turn。异步媒体任务可能在 turn 结束后继续运行，不能把 turn 结束时间当成媒体任务完成时间。

API 从请求头读取或生成请求/trace 标识，并可接收 `x-user-id`、`x-user-name`、`x-project-id`。Runtime 再生成和传播 turn、模型及工具标识。有值才会带入相应记录，不表示每个 span 都必有所有字段。

### 3.2 时间和终态怎么记录

Pir 的 observation span 在开始时记录时间，在结束时记录终态和耗时；OTLP 映射生成 `start_time_unix_nano`、`end_time_unix_nano`、状态及 `pir.duration_ms`。

流式链路还会出现 `turn_started`、`tool_call_started`、`tool_call_finished`、`turn_finished` 等事件。二者用途不同：span 用于分析耗时和调用关系；流式事件用于呈现和重建执行过程。

终态需要区分成功、失败、取消、超时，不能只保留“正常完成”的时间。跨进程的时间分析还依赖实际时钟与传播链路，源码字段存在不代表已经验证所有部署的时间精度。

源码入口：

- [API 关联上下文](D:/code/temp/d5/pir/popipo/crates/pir-popipo-server/src/handlers/observation.rs)
- [Runtime turn 生命周期](D:/code/temp/d5/pir/crates/agent/pir-runtime/src/runtime/turn.rs)
- [事件数据结构](D:/code/temp/d5/pir/crates/observability/pir-observability/src/event.rs)
- [OTLP 的时间、状态与字段映射](D:/code/temp/d5/pir/crates/observability/pir-observability-otlp/src/mapping.rs)

## 4. Pir 内部收集什么

### 4.1 模型调用

`model.call` 采集：

- provider、model、provider request ID。
- `temperature`、`max_output_tokens`、请求的 model ID。
- 是否有系统提示词、system block 数、上下文条目数。
- 工具轮次、required tool names、tool choice 和工具集合策略。
- 输入和输出文本的摘要。
- 输入/输出 Token 估计、总 Token、`cost_micros`。
- 返回的工具调用数量和工具名称列表。
- 打开供应商 stream、首个模型事件、首段内容、首个工具调用片段的耗时。
- stream event、content delta、tool delta 数量。

**输入摘要不是完整模型请求归档。** 当前观测文本由 system blocks、context entries、messages 等拼接后计算摘要；不能拿摘要还原真实 provider payload，也不能用它检查完整工具 schema。

Token 字段名带 `estimate`，成本也取决于 provider 返回/适配结果；不直接当作最终供应商结算账单。

源码：[模型观测入口与观测文本构建](D:/code/temp/d5/pir/crates/agent/pir-runtime/src/runtime/turn/model.rs)。

### 4.2 工具调用与 tool result

`tool.call` 采集工具名、profile、plugin、handler、输入摘要、结果摘要、副作用数量、耗时和错误。

一个工具输出存在不同用途的部分：

| 部分 | 用途 | Pir 工具 span 的处理 |
|---|---|---|
| 工具 input | 模型发出的实际参数 | JSON 类型、大小与哈希 |
| `model_summary` | 提供给模型的结果文本 | 大小与哈希 |
| `ui_details` | 提供给前端的结果详情 | JSON 类型、大小与哈希 |
| `side_effects` | 业务/文件变更事件 | span 记录数量；事件另走执行链路 |
| `metadata` | 工具补充的业务信息 | 字段白名单过滤；复合值摘要化 |

允许的 metadata 包括 task/asset ID、状态、模型、backend、sandbox ID、退出码、workspace transaction ID、变更数量、子 Agent/异步任务信息、Skill 版本、用户交互数量等。并非工具返回的任意字段都直接进 span。

**为什么评估需要 tool result 正文？**

假设工具返回“资源不存在”，模型却回答“视频已经生成”。工具名和哈希只能证明发生过一次调用、内容有多大，不能让人工或语义 judge 看到它究竟失败在哪里。要判断结果理解、信息遗漏和虚假声明，需要模型实际可见的结果正文，并保留成功状态、错误码和 `tool_call_id`。

同时注意：工具 result、给 UI 的详情、供应商原始 HTTP 响应不是同一种数据。评估应明确使用哪一层，不必默认收集所有底层响应。

源码：[工具执行观测](D:/code/temp/d5/pir/crates/agent/pir-runtime/src/runtime/turn/tool.rs)、[metadata 筛选与摘要](D:/code/temp/d5/pir/crates/agent/pir-runtime/src/tool.rs)。

### 4.3 摘要化与明文边界

`summarize_text` 生成 `{size, sha256}`，`summarize_value` 另带 `json_type`。`size` 为字节数，不是模型 Token 数。

这是一种内容摘要处理，不是全系统统一脱敏。用户 ID、用户名、业务 ID、允许的字符串 metadata、错误消息等仍可能明文导出。不能仅因 prompt 被哈希，就声称整条链路完全不含原始内容。

源码：[摘要函数](D:/code/temp/d5/pir/crates/observability/pir-observability/src/summary.rs)。

## 5. 数据流到哪里：不要把所有观测都等同于 Langfuse

### 5.1 通用事件与指标

`ObservationEmitter` 把事件分发给已装配的 sink，并可派生 metric。Native adapter 支持 stdout、文件、近期缓冲、Webhook、OTLP 等配置。

已有指标包括 API/turn/model/tool 的次数与耗时、Token/成本，以及存储、workspace transaction、上下文、异步任务、子 Agent 等领域指标。实际发送到哪个后端由 Host 配置决定。

指标适合看聚合趋势，如错误率、P95 延迟；单次 trace 适合排查具体一次调用。用户/请求/trace 等高基数字段不应被理解成所有 metric 的默认 label。

源码：[事件分发与派生指标](D:/code/temp/d5/pir/crates/observability/pir-observability/src/emitter.rs)、[Native sink 配置](D:/code/temp/d5/pir/crates/observability/pir-observability-native/src/sinks.rs)。

### 5.2 Pir 自己的 Langfuse sink

该 sink 只接受四类事件：

| 事件 | 上报内容与 Langfuse 映射 |
|---|---|
| `api.request` | 方法、路由、HTTP/业务结束字段、时间和状态 |
| `runtime.turn` | profile/scope、用户输入摘要、超时、事件数、终态 |
| `model.call` | 模型调用信息；映射为 `generation`，补充模型和输入/输出 Token 字段 |
| `tool.call` | 工具调用信息；映射为 `tool` |

共同包含可用的 request/user/project/session/turn/model/tool 等 ID、错误、时间、状态和服务版本。`user_name` 还会映射到 Langfuse metadata。

开始事件用于缓存，结束事件用于组装 span；开始事件缺失时存在从终态事件构建的退化路径，不能保证这种情况下仍能恢复真实开始时间。

**没有直接导出所有内部事件**：例如 `sandbox.session`、存储和 Hook 事件不会仅因进入 emitter 就自动被这个 Langfuse sink 接收。沙箱的部分信息可以通过外层 `tool.call` metadata 间接出现。

这个 sink 明确不写 `langfuse.trace.input/output` 聊天预览，避免和 BFF 竞争同一 trace 的内容字段。

源码：[筛选与导出](D:/code/temp/d5/pir/popipo/crates/pir-observability-langfuse/src/sink.rs)、[Langfuse 映射](D:/code/temp/d5/pir/popipo/crates/pir-observability-langfuse/src/mapping.rs)。

### 5.3 BFF 的可选原始内容采集

开启 `LANGFUSE_RAW_CAPTURE_ENABLED` 且 exporter 启用后，BFF 可通过两条路径采集内容：

| 路径 | 采集内容 |
|---|---|
| Pir stream recorder | 用户问题、助手文本、工具参数和结果、用户输入事件、终态、错误及执行摘要 |
| LLM proxy capture | 经过 BFF 的模型请求中的 system/messages/tools/tool choice/参数，以及输出正文、可捕获的 reasoning content、tool calls 和 usage |

第一条提供聊天和执行预览；第二条提供模型实际请求/响应的内容证据。只有模型请求经过对应 BFF 路径时，第二条才可能覆盖它。

聊天预览的根输入选择了用户问题、引用数量、前端工具名、参数键名和任务更新数量，不是直接复制整个前端请求。模型请求采集也按字段选择，不能称为无条件的原始网络报文归档。

默认内容大小配置为 1 MiB；超限会截断。截断不是哈希脱敏。历史消息里包含的工具结果或文件内容也可能随 messages 被采集。

源码：[BFF stream recorder](D:/code/temp/d5/popipo-bff/backend/internal/handler/pir_langfuse.go)、[模型内容 capture](D:/code/temp/d5/popipo-bff/backend/internal/service/llm/langfuse.go)、[配置默认值](D:/code/temp/d5/popipo-bff/backend/internal/config/loader.go)。

### 5.4 送达、审计与存储的区别

- Pir Langfuse transport 使用后台线程，通过 HTTP/Protobuf 发往 `/api/public/otel/v1/traces`，默认超时 5 秒。
- 本次读取的 transport 未实现持久化重试队列；失败记录日志和 exporter failure metric。因此“业务完成”不等于“追踪已成功送达”。
- 通用 emitter 支持 best-effort/fail-closed 等策略，要求审计的事件有单独约束；当前 Langfuse sink 通过普通 `with_sink` 装配，不能当作所有业务副作用的强制审计门禁。
- 恢复会话依赖的 history/store 与追踪平台是不同职责；Langfuse 不应被当成 Pir 的业务数据库或唯一会话恢复来源。

源码：[Langfuse transport](D:/code/temp/d5/pir/popipo/crates/pir-observability-langfuse/src/transport.rs)、[Host 装配](D:/code/temp/d5/pir/popipo/crates/pir-popipo-server/src/assembly/mod.rs)。

## 6. 评估怎么执行：YAML 场景 → runner → 确定性断言

项目有独立 `pir-eval` crate，而不是把“看 Langfuse 页面”当成评估。

```text
case YAML
  ├─ target/profile/model 参数
  ├─ vars 与前一步返回值 capture
  ├─ trajectory：一轮或多轮、查询、异步等待等步骤
  └─ assertions：每一步必须满足什么
       ↓
runner 执行场景并收集响应和事件
       ↓
Rust assertion engine 判断通过/失败
       ↓
写 report、证据文件，并根据失败返回非零退出码
```

- `server` target：产品路径，连接或启动 `pir-popipo-server`，按 Host 配置使用 BFF/model/tool 链路。
- `runtime` target：进程内 Runtime 合约测试，适合历史恢复等；不能据此代替真实产品/供应商链路验证。

源码：[case 定义](D:/code/temp/d5/pir/eval/src/case.rs)、[执行器](D:/code/temp/d5/pir/eval/src/runner.rs)、[断言引擎](D:/code/temp/d5/pir/eval/src/assertions.rs)。

### 6.1 评估维度

| 维度 | 内置断言 | 能回答的问题 |
|---|---|---|
| 整轮状态 | `turn_status` | 是否正常完成 |
| 工具路由 | `tool_called`、`tool_not_called`、`tool_called_once` | 有没有选错、漏调或重复调用 |
| 工具执行 | `tool_succeeded` | 是否出现成功结果 |
| 调用顺序 | `tool_order` | 要求的工具是否按顺序出现 |
| 参数正确 | `tool_args_match` | 指定 JSON 路径的参数是否符合预期 |
| 副作用证据 | `side_effect_exists` | 事件里是否出现期望的提交变更 |
| 输出内容 | `output_contains`、`output_not_contains` | 是否包含/避开指定文本 |
| 真实性 | `no_claim_without_tool_result` | 没有成功结果时是否说出指定成功声明 |
| 历史使用 | `history_replayed` | 输出是否包含预期历史标记 |
| 生命周期 | `trace_has_terminal_span`、`event_sequence` | 是否有结束证据、事件顺序是否满足预期 |
| 返回数据 | `json_pointer_equals`、`json_pointer_contains` | 返回字段值是否正确 |
| 用例约束 | `user_message_is_chinese` | 用户场景文本是否符合中文要求 |

### 6.2 不要高估断言名称

- `tool_called` 只说明发起调用；供应商失败也可能满足它。
- `tool_succeeded` 说明工具成功返回；异步任务“提交成功”不等于最终产物成功。
- `no_claim_without_tool_result` 当前基于指定文本是否出现在输出、是否存在成功结果，不能覆盖所有同义表达，也不是完整的逐事件因果时序证明。
- `tool_order` 检查要求的工具按顺序出现，不等于完全匹配轨迹，也不自动排除中间额外工具。
- `history_replayed` 用输出标记作证据，不等于完整证明模型理解了所有历史。
- `side_effect_exists` 检查事件中的副作用证据，不自动等于重新查询外部业务系统确认最终状态。
- `trace_has_terminal_span` 实现检查终态事件/状态证据；不能证明 Langfuse 后端已收到 span。

### 6.3 当前真实用例

| 用例 | 场景与主要检查 |
|---|---|
| `tool_failure_feedback` | 使用不存在的图片生成视频；检查发起工具调用，不能无成功结果却声称“视频已经生成” |
| `workspace_write_read_trajectory` | 第一轮写固定文本，第二轮同会话读回；检查工具和读回内容 |
| `observability_terminal` | 简单中文回复；检查 done、终态和 `turn_started → turn_finished` |
| `image_to_video_chain` | 第一轮生图，下一轮做视频；检查对应工具成功 |
| `tool_history_replay` | 检查工具调用历史恢复合约 |
| `workspace_edit_conflict` | 文件修改冲突处理场景 |
| `skill_builder_draft` / `custom_tool_builder_draft` | Builder 草稿链路 |

用例可见 [eval/cases](D:/code/temp/d5/pir/eval/cases)。应阅读具体 assertions 后判断覆盖范围，不凭用例名称认定业务链路已经全部验证。

## 7. 报告、比较与 CI 门禁

输出目录形状：

```text
target/pir-eval/<run-id>/
  report.json
  cases/<case-id>/
    response.json
    events.json
    trace.json
    transcript.md
```

- `report.json`：模型/provider 维度、运行起止时间、用例通过失败、失败分类、可选 baseline 对比。
- `response.json`：各步骤执行响应。
- `events.json`：收集到的 stream events，工具调用证据从这里检查。
- `trace.json`：当前实现是 trace ID、turn ID 和终态事件摘要，**不是从 Langfuse 下载的完整 span 树**。
- `transcript.md`：按步骤整理的用户和助手文本；不是全部结构化工具证据的替代品。

失败分类包括工具路由、工具参数、副作用缺失、虚假声明、历史恢复、观测、provider failure、timeout、judge quality 和 case schema。分类存在不等于每类都有独立的高级评分器。

Runner 支持 `pr`、`nightly`、`release` suite。文档中的调用形式：

```bash
cargo run -p pir-eval -- --suite pr
cargo run -p pir-eval -- --case tool_failure_feedback
cargo run -p pir-eval -- --suite release --compare-to <基线报告路径>
```

这些是使用入口说明，本次没有执行。产品场景可能调用真实 provider，需要准备相应测试环境和身份。

比较报告记录通过/失败数量差异、失败分类差异、用例新增/缺失/状态变化及模型/provider 是否变化。release 未显式指定 baseline 时，可从输出目录选择最近的旧报告；严谨对比宜固定 baseline，避免把不同模型或测试条件混成代码效果。

Runner 写完报告后，如有失败会返回错误，主程序退出码为 1。这提供了 CI gate 的基础，但不能据此断言当前线上发布流水线一定已经接入并强制阻断。

源码：[报告结构与比较](D:/code/temp/d5/pir/eval/src/report.rs)、[退出码入口](D:/code/temp/d5/pir/eval/src/main.rs)。

## 8. 真实问题如何进入后续评估

### 8.1 已有的 Debug 导出与重放设计

评估规范明确写了 BFF Debug YAML Export：

1. 用户/开发者在 Loop debug 中导出 YAML，由 BFF 生成。
2. 默认 `turn_replay`：选中某条用户消息，先 fork 会话到该用户 turn 之前，再执行该条 query。
3. `full_replay`：将历史 user turns 转成多个步骤，从头重跑。
4. `continue_next`：基于现有完整 session 执行下一轮输入。
5. 使用独立 eval 身份和权限，不从 YAML 自动冒充原会话用户。

默认 turn replay 只把历史目标轮次中的业务副作用工具作为 required tools 和工具断言；读取、搜索、轮询类工具不强制复现，也不自动生成工具顺序断言。

**值得学习的取舍**：评估“是否得到正确业务结果”，不要求模型逐字重复旧轨迹。否则一次合理的检索路径变化也会被误判为回归。

这里重放的是会话与执行入口；不能直接推导出 workspace、供应商、外部数据库都回到了历史快照。外部数据变化和重复副作用必须在具体测试环境中另外控制。

证据：[评估规范的 Debug 导出段落](D:/code/temp/d5/pir/specs/features/0012-popipo-evaluation.md)。本次未实际操作 Loop 导出、fork 或重放。

### 8.2 异步任务的后续处理

Runner 支持产品异步轮询/子 Agent 等待。超时证据包括 timeout、轮询次数、最后状态和最后响应。

设置 `cancel_on_timeout` 后可以调用 BFF TaskManager cancel，并保存取消响应或错误。但项目文档明确区分：**TaskManager 产品状态取消，不保证 Pir 里运行的 child process 已停止**。评估超时清理不能被描述成外部副作用已经撤销。

### 8.3 从失败到改进：建议使用流程

下表属于基于现有能力的工程流程，不是已实现的自动优化系统。

| 发现的问题 | 用什么证据判断 | 后续修改方向 | 回归检查 |
|---|---|---|---|
| 工具失败却称成功 | query、tool input/result、助手文本、事件顺序 | 状态语义、结果反馈、提示词和终结逻辑 | 明确失败用例；检查成功声明及最终业务状态 |
| 选错工具/参数 | 实际工具 schema、调用参数、错误与上下文 | 工具描述、工具集合、参数校验 | 路由、参数、调用次数 |
| 写了文件但没有实际落地 | 工具结果、变更事件、必要时 BFF 读回 | 写回事务、版本冲突、存储映射 | 副作用事件 + 读回事实 |
| 一轮太慢 | API/turn/model/tool 的时间、首次输出时间 | 模型选择、上下文量、串并行和慢工具 | 固定场景的总耗时及分段耗时 |
| 历史丢失 | 持久化消息、tool-call block、实际模型输入 | 历史恢复与上下文构造 | 下一轮使用前轮结果的用例 |
| 追踪缺失 | 终态事件、exporter error、后端实际查询 | ID 传播、sink、送达与重试设计 | 本地终态检查 + 独立后端送达检查 |

注意：修正路由错误时应检查没有强制工具选择的自然请求。若 case 使用 `required_tool_names`，通过结果不能单独证明模型自主选工具的能力提高了。

## 9. 当前能力和仍需补充的部分

| 能力 | 当前核对结论 |
|---|---|
| 执行生命周期、模型/工具时间和状态 | 有采集与导出实现；线上完整性待验证 |
| Langfuse 结构化追踪 | 有四类事件导出实现 |
| 原始 tool result/模型上下文回放 | BFF 有可选内容采集；依赖开关、路径与大小限制 |
| YAML 轨迹回归与确定性断言 | 有 runner、断言、报告与用例 |
| Debug 导出和指定轮重放 | 当前规范有明确契约，runner 有 query/turn 等支持；本次未端到端运行 |
| 基线对比和失败退出码 | 有实现；CI 是否实际强制执行未验证 |
| 自动语义质量评分 | DeepEval 仅作为可选外部 judge adapter 的定位；不是主 gate |
| 性能质量门槛 | 有时间数据；当前断言列表未见专门的 P95/单轮耗时阈值检查 |
| 自动告警、聚类、提示词优化、发布/回滚 | 本次没有核验出完整自动闭环，不写成已有能力 |

**可观测数据不自动成为评估规则。** 有 tool result 和时间之后，还需要定义“正确结果是什么”“多慢算退化”“谁来处理失败”“用哪个场景防止再发生”。

## 10. 用一个例子串起来

用户：“把这张图片做成视频。”

1. BFF 接收 query，关联用户、项目和 request/trace。
2. Pir 开始 turn，模型调用 `generate_video`。
3. 工具返回资源不存在，产生失败结果；模型输出最终答复，turn 收尾。
4. Pir span 显示模型/工具的耗时、失败原因和输入输出摘要。
5. 若 BFF raw capture 开启，可查看具体 query、工具参数、失败结果、助手是否假称完成。
6. 将该轮导出为 case；在受控环境复现，写出“不存在成功结果时不能声称已生成”的预期。
7. 排查是工具错误反馈不清楚、模型误读，还是运行时错误收尾问题；据此修改。
8. 重跑失败 case 和相关正常 case，与固定 baseline 比较。
9. 除规则通过外，必要时检查视频任务/产物事实，以及追踪后端是否确实收到记录。

第 1～5 步回答“发生了什么”；第 6～8 步回答“能否稳定修好”；第 9 步防止把代理指标误当最终业务结果。

## 11. 阅读入口与复习问题

推荐顺序：

1. [观测设计契约](D:/code/temp/d5/pir/specs/features/0004-observability-first.md)：理解事件、指标、审计和正文边界。
2. `runtime/turn.rs`、`runtime/turn/model.rs`、`runtime/turn/tool.rs`：看实际采集位置。
3. `pir-observability-langfuse/src/sink.rs`、`mapping.rs`：看哪些事件真的被导出。
4. BFF 的 `pir_langfuse.go`、`llm/langfuse.go`：看正文证据如何补齐。
5. [评估设计契约](D:/code/temp/d5/pir/specs/features/0012-popipo-evaluation.md)、`eval/cases`、`eval/src/assertions.rs`：从一个失败场景理解断言。
6. `eval/src/runner.rs`、`report.rs`：看证据落盘、失败返回与 baseline 比较。

与本目录知识主线衔接：[业务改进闭环](./观测什么数据、观测之后怎么改进.md)、[知识图谱](./Agent可观测与轨迹评测知识图谱.md)、[术语清单](./名词清单.md)。本文件提供固定版本案例，不替代通用概念笔记。

复习问题：

1. 为什么 Langfuse 中可能看到 tool result 正文，但 Pir 的 `tool.call` 只记录结果哈希？
2. `turn_finished`、工具成功、媒体任务完成、Langfuse 已送达，各自需要什么证据？
3. 一个失败 case 用 `tool_called` 就能通过时，为什么它可能没有验证用户目标？
4. 重放某条 query 时，为什么复制 session 还不等于恢复整个历史业务环境？

## 反思

- **不确定或未充分验证的部分**：本文主要是静态核对。线上 dev 的镜像版本、开关、实际 span 完整性、原始内容覆盖、导出送达率、CI 接入和重放副作用均未运行验证；源码中的设计目标不能当作这些事实已经成立。
- **后续学习建议**：先选 `tool_failure_feedback`，手工列出 query、工具参数、成功/失败结果、最终回复、turn 起止与业务终态。再对照断言判断“它测到了什么、漏了什么”，之后才扩展到语义 judge、性能阈值与线上告警。
