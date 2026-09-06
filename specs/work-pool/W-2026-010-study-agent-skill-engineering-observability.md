# W-2026-010：Agent Skill 工程化与调用链可观测性学习

- Status: ready
- Area: Agent Skill / Context Engineering / Observability / Reliability / Security / Eval
- Difficulty: D2 → D3
- Discovered From: 用户截图“精通 Agent Skill 工程化与可观测性”“Skill 的调用链路怎么监控和追踪？”
- Owner: personal
- Priority: high
- Related: [W-2026-005：生产级 Skill 加载、资源与治理学习](./W-2026-005-study-production-skill-loading-and-governance.md)

## 原始简版学习点（来自截图）

### 精通 Agent Skill 工程化与可观测性

Skill 不只是一个 Markdown 文件，而是一个需要被发现、选择、加载、注入、执行、评估和治理的运行时能力。生产环境必须知道：

- 哪个 Skill 被发现了；
- 为什么选择或没有选择它；
- 哪个版本、哪个来源被加载；
- 它什么时候进入了 Context；
- 它是否真的改变了模型决策；
- 它后续触发了哪些 Tool、Subagent 和外部副作用；
- 失败、超时、重试和回滚发生在哪里。

### Skill 的调用链路怎么监控和追踪？

不能只记录一次 Agent Run 的开始和结束。至少要能串起：

```text
用户请求
  → Skill discovery
  → Skill matching / routing
  → Skill loading
  → resource loading
  → context injection
  → model generation
  → tool call / handoff
  → result
  → evaluation / feedback
```

核心是用稳定的 Trace、Span、Skill version、Tool call id 和因果关系回答：

> 这次 Agent 为什么调用了这个 Skill？这个 Skill 是否影响了这次模型调用？模型的哪次决策又触发了哪个工具动作？

## Objective

从文件型或程序化 Skill 出发，建立一套生产级 Skill 生命周期和可观测性模型，重点研究“Skill 被加载”与“Skill 对行为产生了可验证影响”之间的差别。

本任务不以选择某个观测平台为目标，而是先建立跨平台的事件和 Trace 契约，再比较不同开源项目如何实现：

```text
Catalog / Registry
  → Discovery
  → Matching / Routing
  → Version Resolution
  → Loading / Validation
  → Resource Read
  → Context Injection
  → Model Generation
  → Tool / Handoff / Subagent
  → Outcome / Eval / Feedback
```

## 生产环境会遇到的问题

### 1. Skill 发现和调用不稳定

- 关键字触发过宽，导致不相关 Skill 被误加载；
- 触发过窄，导致需要的 Skill 没有进入 Context；
- 同名 Skill 来自 user、project、organization、public 等不同来源，优先级不清楚；
- Skill 目录索引与实际文件版本不一致；
- Skill 在 UI 目录中可见，但真正的 Agent Run 没有加载它；
- 多个 Skill 同时匹配，选择顺序依赖模型随机性；
- Skill 只在第一轮加载，后续 tool result 或 subagent 执行时丢失上下文。

需要分别测量 discovery、matching、loading 和 activation，不能只用“最终回答是否正确”判断 Skill 系统正常。

### 2. Context 注入可能变成隐形成本

- 每次都注入完整 `SKILL.md`，导致 Token、延迟和成本快速增长；
- Skill 的 reference、script、asset 被递归加载，形成不可见的 Context 膨胀；
- 多个 Skill 重复提供相似规则，模型在冲突时无法判断优先级；
- Skill 内容更新后，缓存仍使用旧版本；
- 压缩、重试、恢复或交接给 Subagent 时，Skill 内容被重复注入或被意外丢弃；
- 只追踪总 Prompt Token，却不知道是哪个 Skill 贡献了 Context 增量。

生产上需要记录 `skill.content_hash`、版本、加载方式、注入位置、Token 增量和缓存命中情况。

### 3. “调用了 Skill”不等于“Skill 生效了”

一个 Skill 可能：

- 被发现但没有被选择；
- 被选择但加载失败；
- 被加载但没有注入模型 Context；
- 已注入但模型没有遵循；
- 影响了模型计划，但最终 Tool 被 Harness 拒绝；
- 影响了 Tool 参数，但业务服务又改变或拒绝了执行结果。

因此要区分至少五个状态：

```text
discovered → selected → loaded → injected → behavior-linked
```

最后一个 `behavior-linked` 不能只靠模型自述，需要结合模型输入、Tool call、策略决策和确定性业务结果判断。

### 4. 调用链容易断裂

真实 Agent 往往跨越：Web API、Agent Runtime、模型供应商、Skill Loader、MCP Server、Tool Gateway、业务服务、队列和异步 Worker。

常见问题：

- HTTP Trace ID 没有传播到模型调用和工具服务；
- Async Task、线程池、Subagent 或进程边界丢失当前 Span；
- Tool call 只有时间戳，没有关联触发它的那次 model generation；
- 重试创建新的 Trace，导致一次用户请求看起来执行了多次；
- 流式响应只记录最终文本，没有记录中间 tool call 和 Skill 事件；
- 远程 MCP Tool 返回结果后无法回到原始 Agent Run。

OpenTelemetry GenAI 语义约定目前仍在发展中，相关讨论也指出“哪次模型推理触发了哪次 Tool 执行”的因果关联不一定能从简单的父子 Span 结构中恢复。因此本任务要显式设计 `tool_call_id`、`generation_id`、`skill_activation_id` 和 `parent_run_id`，不能只依赖时间顺序。

### 5. 版本、来源和权限经常被混为一谈

- `skill_name` 相同，但内容、来源、Git ref 或配置已经变化；
- Trace 只记录名称，没有记录具体版本和内容 Hash；
- Skill 声明了 `allowed-tools`，但该声明到底是提示、授权请求还是 Harness 强制策略不清楚；
- 从公共仓库加载 Skill 后，Skill 正文、脚本和 MCP 配置的信任级别没有拆开；
- 项目 Skill 通过 Prompt 注入了“可以执行某动作”，但真正的工具权限没有重新检查；
- Skill 能读取敏感数据，Trace 又把原始 Prompt、Tool 参数和结果完整保存，造成二次泄露。

必须区分：

```text
Skill instruction  ≠  permission
Skill selection    ≠  authorization
Trace visibility   ≠  data access entitlement
```

### 6. 失败恢复会产生重复副作用

- Skill 加载超时后自动重试，重复执行动态脚本；
- Agent 恢复时重新注入 Skill，导致相同 Tool call 被再次提出；
- Tool 调用成功但响应丢失，Agent 依据不完整 Trace 再次执行；
- Skill 版本在 Run 中途更新，前后两轮使用了不同规则；
- 异步 Skill 或 Subagent 结束后，主 Agent 没有收到完整状态；
- 观测系统不可用时，业务执行是否继续没有明确策略。

Skill Trace 必须与幂等键、审批状态、业务 operation id 和恢复 checkpoint 关联，而不是只记录自然语言日志。

### 7. 观测数据本身会带来生产问题

- 完整 Prompt、Skill 正文、Tool 参数和 Tool result 可能包含凭据、个人信息或商业数据；
- 将请求 ID、用户 ID、Skill 名称、版本、错误文本全部作为高基数标签，会导致指标系统成本和查询性能恶化；
- 记录完整模型输出可能包含敏感推理内容或不应长期保存的上下文；
- 采样策略可能恰好丢掉失败请求、长尾请求和权限拒绝请求；
- 多租户环境下，观测平台查询权限可能高于业务用户权限；
- Trace retention、删除权、脱敏、加密和审计常常没有和业务数据生命周期对齐。

应将低基数属性用于 Metrics，将详细内容放在受控 Trace 存储，并提供字段级脱敏、采样、保留期限和访问审计。

## Recommended Trace Model

### 建议的 Span 层级

```text
request / session
└── agent_run
    ├── skill_discovery
    ├── skill_activation
    │   ├── skill_load
    │   ├── skill_resource_read
    │   └── context_injection
    ├── turn
    │   ├── generation
    │   ├── tool_call
    │   │   └── downstream service / cli / mcp
    │   └── handoff / subagent_run
    └── evaluation / feedback
```

### Skill Activation 最小字段

| 字段 | 作用 |
| --- | --- |
| `skill.name` | 稳定逻辑名称，不包含每次 Run 的随机值 |
| `skill.version` | 发布版本、Git ref 或其他可解析版本 |
| `skill.source` | project、user、org、public、plugin 等来源 |
| `skill.content_hash` | 判断实际加载内容是否变化 |
| `skill.activation_id` | 一次激活的稳定关联 ID |
| `skill.activation_reason` | keyword、router、explicit、policy、always 等 |
| `skill.match_score` | 若存在模型/规则评分，记录其版本和分数 |
| `skill.load_status` | discovered、selected、loaded、failed、injected、skipped |
| `skill.resource_count` | 加载了多少 reference、script、asset 或其他资源 |
| `skill.context_tokens` | 对当前 Model Context 的增量贡献 |
| `skill.policy_decision` | 是否允许加载、执行或访问资源 |
| `trace_id` / `parent_span_id` | 与一次 Agent Run 和父步骤关联 |

不要把 `skill.content`、完整 Prompt 或 Tool result 默认塞进 Metrics 标签；它们应进入受控事件或脱敏后的 Trace 字段。

### 关键指标

- Skill discovery 命中率、误命中率、漏命中率；
- selected → loaded → injected 的漏斗转化率；
- 各 Skill 的加载延迟、资源读取失败率和缓存命中率；
- Skill 注入带来的输入 Token、成本和上下文占比；
- Skill 版本之间的任务成功率、Tool 参数错误率和拒绝率；
- 每次 model generation 触发的 Tool call 数量和失败率；
- 由 Skill 触发的审批、权限拒绝、重试、回滚和副作用次数；
- Trace 完整率、Span 丢失率、异步关联失败率和采样覆盖率；
- 带 Skill 与不带 Skill 的离线 Eval 差异。

## Reference Projects and Study Value

正式开始时重新固定版本、Commit、许可证和文档状态。以下项目是学习样本，不等于直接推荐生产采用。

### 1. OpenHands Software Agent SDK：主线样本

- [Skills and Context](https://docs.openhands.dev/sdk/guides/skill)
- [Observability & Tracing](https://docs.openhands.dev/sdk/guides/observability)
- [Software Agent SDK](https://github.com/OpenHands/software-agent-sdk)
- [Skills and Plugins example](https://github.com/OpenHands/software-agent-sdk/tree/main/examples/05_skills_and_plugins)

学习价值：

- Skill 支持文件型 `SKILL.md`、程序化 Skill、关键词触发和 progressive disclosure；
- SDK 还涉及 public、user、organization、project 多来源合并和优先级；
- 官方文档说明 SDK 使用 Laminar 作为 OpenTelemetry instrumentation layer，并追踪 `agent.step`、Tool、LLM、Conversation 等操作；
- 可以直接研究“Skill loader 的事件”与“Agent execution 的 Span”是否真正连在一起。

重点追踪：`AgentContext`、Skill loading、message suffix、plugin loading、conversation lifecycle、`agent.step` 和 Tool span。

### 2. OpenAI Agents SDK：标准化 Agent Run / Turn / Tool Trace

- [OpenAI Agents SDK tracing guide](https://openai.github.io/openai-agents-js/guides/tracing/)
- [OpenAI Agents SDK tracing module](https://openai.github.io/openai-agents-python/ref/tracing/)

学习价值：默认提供 Trace、Task、Agent、Turn、Generation、Function、Guardrail 和 Handoff 等层次，并支持自定义 Span 和敏感数据控制。

它不是一个完整的文件型 Skill 工程系统，因此正好适合作为对照实验：手动增加 `skill_discovery`、`skill_load` 和 `context_injection` Span，观察怎样把 Skill 生命周期接入现有 Agent Trace。

### 3. OpenTelemetry GenAI Semantic Conventions：跨平台契约样本

- [GenAI agent and framework spans](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)
- [GenAI attributes and tool data](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/registry/attributes/gen-ai.md)

学习价值：提供 `invoke_agent`、workflow、plan、`execute_tool` 等 Agent/Tool Span 的统一讨论入口，也明确提醒 Prompt、Tool arguments 和 Tool result 可能包含敏感数据。

要特别学习它的未完成部分：标准化不代表因果链已经自动解决。Skill activation 如何表达、Skill 与 generation 的关系如何表示、一次 inference 如何关联后续 tool call，仍需要应用层补充稳定关联字段。

### 4. Langfuse：Trace 数据模型、Prompt/Skill 版本和评估

- [Observation types](https://langfuse.com/docs/observability/features/observation-types)
- [What does a good trace look like?](https://langfuse.com/docs/observability/best-practices)
- [Trace IDs and distributed tracing](https://langfuse.com/docs/observability/features/trace-ids-and-distributed-tracing)

学习价值：把 Agent、Generation、Tool、Chain、Retriever、Evaluator 和 Guardrail 作为不同 Observation 类型，并强调 Tool 应嵌套在负责编排的 Agent/Span 下，同时与触发它的 Generation 保持清晰关系。

重点研究：如何给 Skill 自定义 Observation type 或 Span；如何把 prompt/skill version 关联到 generation；如何在多轮会话和跨服务调用中传播 Trace ID；如何把 Eval 结果回写到具体 Skill 版本。

### 5. Phoenix / OpenInference：开源观测与评估样本

- [Phoenix tracing tutorial](https://arize.com/docs/phoenix/tracing)
- [Phoenix first traces](https://arize.com/docs/phoenix/tracing/tutorial/your-first-traces)
- [Phoenix project](https://github.com/Arize-ai/phoenix)

学习价值：开源 Phoenix 基于 OpenTelemetry/OpenInference，示例覆盖 Agent、LLM、Tool、RAG、Session、人工反馈和评估。适合做本地实验，验证一个 Skill Trace 是否能被可视化、检索和批量评估。

重点研究：父 Span 如何聚合一次请求；Skill 注入作为 Chain、Agent 还是自定义 Span；敏感输入输出如何脱敏；Trace 如何连接离线 Dataset 和在线反馈。

### 6. LangGraph / LangSmith：图工作流与恢复对照

- [LangSmith tracing quickstart](https://docs.langchain.com/langsmith/observability-quickstart)
- [LangSmith observability concepts](https://docs.langchain.com/langsmith/observability-concepts)

学习价值：适合观察 Skill 被放入节点、路由、Subgraph 或 checkpoint 后，如何在图执行中传播 Run、Thread、Metadata 和反馈。

重点研究：Skill 版本更新时 checkpoint 是否固定旧版本；恢复和重放是否重复注入或重复 Tool；一个 Skill 节点失败时，Trace、State 和业务副作用如何分别恢复。

## Suggested Study Order

1. 先读 OpenHands Skill 与 Observability 文档，建立“Skill loader + execution trace”的主线。
2. 阅读 OpenAI Agents SDK tracing，补齐 Agent / Turn / Generation / Function / Handoff 的基本 Span 层级。
3. 阅读 OpenTelemetry GenAI 语义约定，整理跨项目的字段、Span 类型和当前缺口。
4. 选择 Phoenix 或 Langfuse 做本地观测后端，不同时安装多个平台。
5. 用 LangGraph/LangSmith 做恢复、重放和图工作流对照。
6. 回到本仓库 `s07_skill_loading`，为教学版 Skill loader 加入最小 Trace schema 和确定性测试。

## Minimal Experiments

### 实验 A：Skill 激活漏斗

准备 5 个 Skill 和 20 条任务，记录：发现、匹配、选择、加载、注入、模型使用和最终结果。至少包含误触发、漏触发、同名覆盖和缺失资源。

### 实验 B：调用链因果关联

构造一次“Skill → generation → tool call → downstream service”的链路，要求通过 `skill_activation_id`、`generation_id`、`tool_call_id` 和 `trace_id` 还原因果顺序，而不是依赖时间戳猜测。

### 实验 C：成本和 Context 影响

比较无 Skill、只注入摘要、完整 Skill、按需加载 reference 四种模式，记录 Token、延迟、成本、选择准确率和最终任务成功率。

### 实验 D：版本漂移

在一次 Run 中更新 Skill 内容，测试固定版本、热刷新和恢复重放三种策略。确认同一次 Run 是否允许前后轮使用不同的 Skill content hash。

### 实验 E：失败与重复副作用

注入 Skill loader 超时、资源读取失败、模型响应丢失、Tool 超时、Worker 重启和观测后端不可用，验证：

- 是否会重复注入 Skill；
- 是否会重复提出或执行 Tool call；
- 是否保留原始 `operation_id` 和幂等键；
- 观测失败时业务执行是否按风险等级 fail-open 或 fail-closed。

### 实验 F：隐私与采样

在 Skill、Prompt、Tool 参数和结果中放入模拟敏感字段，验证脱敏、采样、访问控制、删除和 Trace 关联是否同时成立。

## Expected Output

- 一张 Skill 生命周期与 Agent 执行链路图；
- 一份 Skill Trace / Span / Event 字段契约；
- 一张 discovery → selection → loading → injection → behavior-linked 状态机；
- 一张生产问题与观测信号对照表；
- 一个项目对比表，覆盖 Skill loading、版本、Trace、Tool、Eval、恢复和隐私；
- 至少 6 个可复现故障注入实验；
- 一组 Skill 级指标和 Agent Run 级指标；
- 至少一个 Skill 被拒绝、跳过或回滚的案例；
- 一份“被加载”与“实际影响行为”的证据边界说明。

## Acceptance Criteria

完成后应能够：

1. 解释 Skill discovery、routing、loading、injection、execution 和 evaluation 的边界；
2. 画出一次从用户请求到 Skill、模型、Tool、业务服务的可追踪链路；
3. 说明为什么只记录 Agent 总耗时无法定位 Skill、模型、Tool 或下游服务的问题；
4. 为 Skill 设计版本、来源、Hash、激活原因、Context 增量和策略决策字段；
5. 解释父子 Span 为什么不一定足够表达“哪次模型决策触发了哪个 Tool”；
6. 用确定性实验区分 Skill 被加载、被注入、被遵循和真正改变业务结果；
7. 处理多租户、敏感上下文、采样、高基数标签和 Trace retention 风险；
8. 比较 OpenHands、OpenAI Agents SDK、OpenTelemetry、Langfuse、Phoenix 和 LangSmith 的适用边界；
9. 能为本仓库教学版 Skill loader 提出最小但可验证的可观测性改进。

## Boundaries

- 当前只进入 Work Pool，不立即安装或运行上述外部项目，不修改教学代码。
- 参考项目只用于学习机制和边界，不默认其生产安全、可用性或观测完整性。
- 不把 Trace 当成授权系统；Trace 记录 Tool 不等于 Tool 被允许执行。
- 不默认保存完整 Prompt、Skill 正文、Tool 参数、Tool result 或模型内部推理内容。
- 不把 LLM 自评“我使用了某 Skill”当作 Skill 生效证据。
- 正式开始时重新核对版本、Commit、许可证、文档状态和观测数据处理政策。

## Start Trigger

满足以下条件后再启动：

- 已完成 `s07_skill_loading` 基础学习，能够说明 Skill 发现、加载和资源读取流程；
- 已能区分 Trace、Log、Metric、Event、State、Policy 和 Audit；
- 选择 OpenHands 作为主样本，并选择 Phoenix 或 Langfuse 作为一个观测后端；
- 启动时按规范将本文件转为 `specs/changes/C-YYYY-NNN-*.md`，并从 Work Pool 移除。

## Non-goals

- 不构建完整商业级 LLM Observability 平台；
- 不同时深入所有 Agent Framework；
- 不把 Skill 的自动选择优化成只追求命中率而忽略安全和成本；
- 不通过采集完整 Prompt 和 Tool 数据换取“看起来完整”的 Trace；
- 不将任何一个参考项目确定为唯一正确的 Skill 架构。
