# W-2026-016：Chat2DB 生产级 Agent + 数据库工具学习

- Status: ready
- Area: Agent Harness / Text2SQL / Tool Calling / Database / Security / MCP / Reliability / Eval
- Difficulty: D2 → D4
- Discovered From: 图片中的 Chat2DB 项目，以及当前仓库 s01-s09 学习主线
- Owner: personal
- Priority: high
- Related: [`s01-s20`](../../README-zh.md)、[`W-2026-001`](./W-2026-001-study-agent-hook-production-practices.md)、[`W-2026-003`](./W-2026-003-study-strict-json-output-post-training.md)、[`W-2026-005`](./W-2026-005-study-production-skill-loading-and-governance.md)、[`W-2026-006`](./W-2026-006-study-tool-result-compaction-and-recovery.md)、[`W-2026-007`](./W-2026-007-study-side-effect-tool-security.md)、[`W-2026-008`](./W-2026-008-study-memory-production-practices.md)

## Project Identity And Version Boundary

图片中的仓库链接疑似是 `github.com/chat2db/Chat2DB`（图片分辨率和文字覆盖使 owner 部分存在不确定性）。截至 2026-09-06，该地址已重定向到 [`OtterMind/Chat2DB`](https://github.com/OtterMind/Chat2DB)。因此本任务采用“项目族 + 版本边界”的研究方式：

1. 以当前 [`OtterMind/Chat2DB`](https://github.com/OtterMind/Chat2DB) 作为主样本，固定具体 commit/tag 后再追代码。
2. 把截图时期的历史代码线（曾出现过 `alibaba/Chat2DB`、`CodePhiliaX/Chat2DB`、`ali-dbhub` 等名称）作为兼容性和架构演进对照，不把历史宣传、旧端口、旧许可证或旧目录结构直接套到当前版本。
3. 特别区分 Community、Pro、Enterprise 和 Local 的能力边界。当前 Community 是单用户、本机优先产品，不提供多用户账号、租户隔离或多用户授权边界；商业版能力不能反推 Community 已经具备同等治理能力。

版本、许可证、仓库归属、功能和安全结论在正式启动时重新核对；本 Work Pool 不把易变化的 API 或目录当作长期事实。

## Why This Project Is Worth Studying

Chat2DB 的学习价值不在于“让 LLM 生成一条 SQL”这个 Demo，而在于它把一个不可靠的模型输出接入了真实的数据系统和产品运行时：

```text
自然语言意图
    ↓
数据源 / 环境 / 数据库 / Schema 选择
    ↓
元数据与方言上下文构造
    ↓
Text2SQL / SQL 解释 / SQL 优化
    ↓
SQL 解析、格式化、方言校验与风险判断
    ↓
工具 / JDBC / 数据库插件 / SSH 通道
    ↓
超时、取消、分页、结果限制与错误恢复
    ↓
结果展示、图表、历史、审计、反馈和下一轮推理
```

这条链同时覆盖当前课程里的 Loop、Tool、Permission、Hook、Plan、Context、Memory 和 MCP，也暴露了课程 Demo 有意简化的生产问题：数据库是有真实副作用的外部系统，Schema 和查询结果可能包含不可信指令，SQL 方言和驱动具有强烈的领域差异，长结果和慢查询会直接造成可靠性问题。

上面的链是本任务的研究假设，不代表 Chat2DB 当前每一层都已经按此方式实现；启动后必须用源码、测试、运行 Trace 和官方文档逐项验证，明确区分“已证实事实、合理推断、宣传描述和未知”。

## Core Learning Objective

建立一套可以迁移到其他 Agent 产品的“自然语言 → 受控数据库动作”生产级心智模型，并回答：

1. Text2SQL 的输入、输出和上下文契约到底是什么：Schema、方言、环境、数据样例、业务术语、历史查询和用户权限分别怎样进入模型上下文？
2. 模型生成 SQL 后，谁负责解析、校验、限流、授权、审批、执行、取消和结果过滤？
3. 多数据库支持为什么需要 SPI、插件、方言、驱动、元数据和能力声明，而不是只替换一个 Prompt？
4. Community 的本机优先边界，如何转换成 Web、Docker、桌面、CLI 和 MCP 的不同信任边界？
5. SQL 结果、数据库内容、AI 响应和自定义 JDBC Driver 为什么都要被视为不同类型的不可信输入？
6. 如何用确定性 Eval 证明“执行正确、业务正确且安全”，而不是只看 SQL 能否解析或最终回答是否流畅？
7. 哪些机制值得补回当前的教学 Harness，哪些只是 Chat2DB 的产品特定实现，哪些当前仍需要证据？

## Stable Mental Model

```text
Model：提出意图、SQL 候选、解释或下一步工具调用
  ↓
Harness：组装上下文、限制工具、校验参数、执行预算、暂停/审批、记录 Trace
  ↓
SQL/Tool Adapter：解析语句、绑定数据源/方言、过滤结果、映射错误
  ↓
Plugin/Driver：提供数据库特定的元数据、SQL、类型和连接能力
  ↓
Database：以自己的账号、权限、事务、锁和约束做最终执行
  ↓
Result/State：返回分页结果、操作状态、错误、引用和审计证据
```

必须保持以下边界：

- 模型生成 SQL 不等于 SQL 合法；SQL 合法不等于业务语义正确；业务语义正确不等于允许执行。
- Harness 允许调用不等于数据库必须执行；数据库服务仍需用真实身份、账号权限和业务约束做最终防护。
- Schema、表名、列名、注释、查询结果和数据库文本是数据，不是系统指令；它们可能携带 Prompt Injection。
- 本机优先降低网络暴露面，但不自动提供多用户授权、最小权限、数据脱敏或安全的第三方驱动隔离。
- 查询结果的大小和业务重要性是两个维度；分页、外置、摘要和恢复策略不能只按字符串长度统一处理。

## Mapping To The Current Learning Path

| Chat2DB 观察面 | 对应当前章节 | 重点学习问题 |
| --- | --- | --- |
| `text2sql`、`execute_sql`、元数据查询 | s01 Agent Loop、s02 Tool Use | 一次 AI 请求如何变成多个工具调用；工具声明、参数 Schema、结果回传和多工具配对在哪里发生 |
| 数据源、环境、账号、只读/写入边界 | s03 Permission、W-2026-007 | 模型建议、Harness 允许、数据库最终授权三者怎样分层；环境标签能否真正影响执行 |
| SQL 解析、格式化、错误修复、执行前后处理 | s04 Hooks、W-2026-001 | 哪些是生命周期扩展点，哪些其实是业务 Workflow；失败 Hook 是否阻断执行，如何审计拒绝 |
| AI Copilot、SQL 优化、查询诊断 | s05 TodoWrite、s10 System Prompt、s11 Error Recovery | 多步计划、运行时 Prompt 组装、错误反馈和重试是否由模型决定，哪些必须由 Harness 强制 |
| SQL 生成、解释、报表和数据分析的上下文隔离 | s06 Subagent、W-2026-004 | 是否真的需要子 Agent；怎样隔离 Schema、结果、凭证和副作用；Summary 是否有真实证据 |
| 插件、Driver 配置、CLI Skill、MCP Resource | s07 Skill Loading、s19 MCP Plugin、W-2026-005 | 能力发现、按需加载、版本、来源、权限和第三方可执行扩展的治理 |
| 大 Schema、长 SQL、分页结果、流式响应 | s08 Context Compact、W-2026-006 | 什么可以压缩或外置；压缩后如何保留状态、结果引用和恢复策略 |
| SQL 历史、保存查询、反馈、AI Dataset | s09 Memory、W-2026-008 | 哪些是历史记录、Run State、Memory 或 Knowledge Base；怎样避免把错误 SQL 和敏感数据长期记住 |
| 慢查询、数据迁移、导入导出、报表任务 | s12 Task System、s13 Background Tasks、s14 Cron Scheduler | 长任务的状态、取消、重启恢复、定时触发、幂等和部分成功 |
| 团队数据源、审批、共享资源 | s15-s18、W-2026-007 | 当前 Community 与商业版治理边界；多 Agent 或多用户场景是否真的有身份和资源隔离 |
| CLI JSON、MCP endpoint、Agent Skill | s19 MCP Plugin、s20 Comprehensive Agent | 协议工具、连接认证、能力发现、版本兼容、回环监听和失败关闭 |

## Preferred Incremental Learning Plan

本任务按小切片推进，不要求一开始读完整仓库。

### Phase 0：冻结样本和产品边界

- 固定 Chat2DB 主仓库的 commit/tag、社区版本、许可证、运行模式和对应文档。
- 记录历史截图版本与当前版本的差异：仓库归属、目录、端口、部署方式、AI 能力、MCP、加密和多用户边界。
- 建立“产品描述 → 源码/测试证据 → 结论”的核验表。
- 不因 Star 数、宣传页或二手文章推断生产能力。

### Phase 1：只读主链路

只研究一个最小、可安全复现的流程：

```text
选择本地测试数据源
  → 列出 database/schema/table
  → 获取表结构
  → 调用 text2sql
  → 解析和校验 SQL
  → 以只读账号执行单条 SELECT
  → 分页返回结果
  → 展示 SQL、结果、耗时和错误
```

需要从 UI、后端 Controller/Service、AI 适配器、数据库 SPI/插件、存储和返回协议一路追踪；CLI 与 MCP 作为第二入口对照，不默认它们复用完全相同的权限和上下文。

### Phase 2：Text2SQL 质量闭环

研究并用本地固定数据集验证：

- Schema 选择：全量 Schema、选中表、检索出的相关表、AI Dataset 和业务术语分别有什么影响；
- 方言适配：MySQL、PostgreSQL、SQLite 等语法差异如何进入 Prompt、解析器和执行器；
- 生成结果：纯 SQL、带解释文本、结构化对象、流式响应分别如何处理；
- 校验层次：JSON/协议合法、SQL 可解析、只读策略通过、执行成功、业务语义正确；
- 反馈闭环：语法错误、列不存在、权限不足、超时和空结果分别是否触发修正、澄清、重试或停止；
- 人机协作：用户是否能看见最终 SQL、数据源、环境、账号和影响范围后再执行。

### Phase 3：Tool、Permission 和数据库安全

对 `get_tables_schema`、`text2sql`、`execute_sql` 和潜在 DDL/DML 工具建立契约矩阵：

| 维度 | 必须回答的问题 |
| --- | --- |
| Side effect | 只读、可逆写入、不可逆写入还是未知？ |
| Identity | 最终用户、Agent、Chat2DB Runtime、数据库账号和审批人如何区分？ |
| Scope | 数据源、环境、数据库、Schema、表、行列和时间范围如何限制？ |
| Validation | 如何拒绝多语句、危险语句、无界查询、跨库访问和参数注入？ |
| Approval | 哪些操作自动执行、需要预览确认、需要强审批或永久禁止？ |
| Reliability | 超时、取消、连接断开和执行成功但响应丢失时如何处理？ |
| Result | 是否有分页、行数/字节上限、敏感字段过滤和稳定结果引用？ |
| Audit | 能否关联 Run、Tool Call、SQL Hash、数据源、账号、决策和业务结果？ |

重点验证“AI 输出不可信”“MCP Token 不等于数据库授权”“`source: agent` 不能成为授权依据”“只读 UI 不能替代后端/数据库限制”。

### Phase 4：多数据库插件与模块化

从一个数据库（优先 SQLite、H2 或 MySQL 测试环境）追踪到插件边界，再对比第二个方言：

- 数据源连接、驱动下载/加载、SSH 通道和连接池在哪里管理；
- SPI 如何抽象元数据、类型、SQL Builder、格式化、补全、解析和执行；
- 数据库特有 SQL 是否保持在所属插件中；
- 添加一个数据库是否真能只改配置，哪些能力仍需要代码或测试；
- 插件失败、驱动缺失、版本不兼容和恶意自定义 Driver 怎样表达与阻断；
- Community、CLI、MCP 和桌面运行时是否共享同一份核心能力，哪些只是外层适配器。

### Phase 5：MCP、CLI 和 Agent 接入

以官方 [`Chat2DB-CLI`](https://github.com/OtterMind/Chat2DB-CLI) 和 Chat2DB MCP 文档为主样本，研究：

- CLI 为什么需要 `--json`、状态查询、版本/能力检查和明确的 edition；
- MCP 工具如何发现、配置、认证、调用和禁用；
- 本地端口、Token、HTTP Header、Owner-only 连接和回环监听如何形成信任边界；
- Tool Schema 是否暴露了不该由模型控制的确认字段或凭证；
- 兼容版本不满足时是否失败关闭，而不是静默切换到其他 edition 或权限；
- Agent Skill 的安装、更新、覆盖和来源如何审计。

### Phase 6：可靠性、结果和长期运行

把现有 Work Pool 的主题接到真实数据工具上：

- 大结果集分页、截断、外置和重新查询；
- 查询超时、取消、连接池耗尽、数据库重启和模型服务不可用；
- 写操作的幂等键、未知结果、状态查询、补偿和审批后参数变化；
- SQL 历史、保存查询、反馈、AI Dataset 与 Memory 的边界；
- 导入导出、迁移、Dashboard 刷新和定时任务的后台状态；
- Trace、操作日志、审计和普通应用日志的敏感数据最小化。

### Phase 7：Eval 和部署运维

建立一套小而可重复的本地评测，不以“模型说成功了”作为 Oracle。至少覆盖：

1. 简单单表查询、连接、聚合、日期和空结果；
2. 不同 SQL 方言和同名字段；
3. Schema 不完整、问题含糊和用户没有权限；
4. SQL 语法错误、列不存在、权限错误、超时和连接断开；
5. 生成 `INSERT`/`UPDATE`/`DELETE`/`DROP` 或多语句时被拦截；
6. 表注释、字段值或查询结果带 Prompt Injection 时不能越权；
7. 结果过大时分页或外置，且 SQL、状态和结果引用仍能对应；
8. 相同写请求重复、响应丢失、Worker 重启时不产生额外副作用；
9. MCP Token、数据库密码、AI Key、JDBC URL 和敏感列不进入普通日志或模型上下文；
10. Web/Docker/桌面/CLI 使用错误 edition、端口或缺失密钥时失败关闭。

指标至少包括：SQL parse rate、执行成功率、业务语义正确率、安全拒绝率、unsafe acceptance、澄清率、平均/尾延迟、返回行数/字节数、模型 Token、数据库耗时、重试次数、取消成功率和成本。

部署研究覆盖：loopback 绑定、Docker host publish、密钥初始化与备份、数据库账号最小权限、驱动供应链、数据迁移、版本升级、许可证和可复现构建。只在本地命名测试数据库中运行；不连接真实生产库。

## Production-Grade Checklist To Learn

### 1. Correctness

- 把语法正确、Schema 正确、可执行、业务语义正确和结果可解释分开评测；
- 保存用户问题、使用的 Schema 版本、方言、生成 SQL、修改记录、最终 SQL 和执行结果引用；
- 对“没有足够信息”支持澄清或拒绝，不用模型猜测表和列；
- SQL 优化建议必须区分建议、模拟验证和真实执行，不把模型意见当成性能事实。

### 2. Security

- 所有 AI 响应、数据库内容、导入文件、SQL 文件、压缩包和自定义 Driver 默认不可信；
- 用数据库账号、数据源、环境、Schema、表/列权限限制真实能力；
- 只读工作流使用只读账号、单语句限制、超时、行/字节上限和结果过滤；
- 高风险 SQL 需要展示最终数据源、环境、账号、SQL 和影响范围后再审批；
- 数据源密码和 AI API Key 使用受控密钥加密；密钥丢失、非法、权限过宽和备份恢复都要有明确行为；
- Community HTTP 服务的回环绑定不能被“隐藏前端按钮”替代；
- Prompt Injection 防护不能只写进 Prompt，必须由 Tool Gateway、解析器、权限和数据库账号共同兜底。

### 3. Reliability

- 连接、查询、模型调用、插件和 MCP 都有超时、取消、错误分类和有限重试；
- 读操作和写操作使用不同的重试/恢复策略；
- “数据库已执行但响应丢失”只能先查状态或对账，不能盲目重做；
- 查询结果有分页/流式/外置策略，压缩不丢失执行状态和因果 ID；
- 后台任务、数据迁移和报表刷新有持久状态、取消、重启恢复和部分成功语义。

### 4. Extensibility

- 数据库特有能力留在插件，通用 Runtime 不复制方言分支；
- 插件、驱动、AI Provider、MCP Server 和 Skill 都有版本、来源、能力和兼容性信息；
- 读取资源、调用工具和执行第三方代码是三个不同权限；
- 前端、HTTP、JCEF、CLI、MCP 复用核心契约，不通过隐藏 UI 实现安全隔离。

### 5. Observability And Governance

- Trace 能关联 Run、Model Call、Tool Call、SQL Hash、数据源、审批、数据库操作和最终结果；
- 普通日志不记录密码、Token、完整 JDBC URL、敏感查询结果或不必要的原始数据；
- 评测数据、查询历史和 Memory 有保留、删除、脱敏、租户/用户隔离和访问审计；
- 版本升级、存储迁移、加密密钥轮换和驱动更新有回滚/恢复方案；
- 文档、测试、构建和发布流程能证明实际支持的部署边界，不把 Demo 或产品宣传当成安全证明。

## Minimal Safe Experiment

在本仓库专用实验目录中构造本地 SQLite/H2 数据库和少量测试数据，不下载或运行未知 Agent 代码，不接生产数据库：

```text
list_tables → get_schema → text2sql → validate_read_only_sql
           → execute_read_only_sql → page_result → record_trace
```

实验至少包含：

- 一个允许的只读查询；
- 一个语法错误和一个语义错误；
- 一个包含恶意指令的表注释/字段值；
- 一个危险写语句和一个多语句请求；
- 一个超大结果集；
- 一次执行超时或响应丢失模拟；
- 一个不存在或权限不足的数据源；
- 一次模型返回额外解释文本、非法结构或不支持方言。

所有断言优先检查数据库行数、查询副作用次数、状态机、SQL AST/策略结果、分页边界、Trace 关联和敏感信息泄漏；自然语言质量只作为辅助指标。

## Relationship To Existing Work Pool

- `W-2026-001`：研究 Chat2DB 的 SQL/Tool 生命周期和观测扩展，但不重复泛化 Hook 理论；
- `W-2026-003`：研究 Text2SQL/MCP 的结构化输入输出与运行时校验，但不把 JSON 合法当作 SQL 安全；
- `W-2026-004`：只在 Chat2DB 的多步分析、报表或长任务确有委派证据时研究 Subagent，不预设必须使用；
- `W-2026-005`：研究 Chat2DB CLI Skill、驱动/插件和 MCP 资源的发现、版本和执行权限；
- `W-2026-006`：研究查询结果、错误信息和写操作结果的压缩、外置与恢复；
- `W-2026-007`：把 `execute_sql`、数据源权限、只读账号、审批、幂等和未知结果作为业务 Tool 安全案例；
- `W-2026-008`：区分查询历史、保存 SQL、反馈、AI Dataset、Memory 和权威数据库事实。

本任务不修改上述条目；启动后如出现需要独立追踪的实现工作，按 `specs/README.md` 从本 Work Pool 条目创建新的 Change。

## Primary Sources

正式启动时重新核对版本和可访问性：

- [Chat2DB 当前仓库](https://github.com/OtterMind/Chat2DB)
- [Chat2DB 原入口（当前重定向目标需核对）](https://github.com/chat2db/Chat2DB)
- [Chat2DB README](https://github.com/OtterMind/Chat2DB/blob/main/README.md)
- [Chat2DB AGENTS.md：模块边界、运行模式和验证约束](https://github.com/OtterMind/Chat2DB/blob/main/AGENTS.md)
- [Chat2DB Security Policy](https://github.com/OtterMind/Chat2DB/blob/main/SECURITY.md)
- [Chat2DB Text2SQL 文档](https://chat2db.ai/resources/docs/ai-chat/text2sql)
- [Chat2DB Datasources and SQL 文档](https://chat2db.ai/resources/docs/cli/database)
- [Chat2DB MCP and Agent Integration 文档](https://chat2db.ai/resources/docs/cli/mcp-agent)
- [Chat2DB Data Security 文档](https://chat2db.ai/resources/docs/connection/data-security)
- [Chat2DB CLI 官方仓库](https://github.com/OtterMind/Chat2DB-CLI)
- [Chat2DB Releases](https://github.com/OtterMind/Chat2DB/releases)

历史资料（只用于演进对照，不作为当前行为证据）：

- [旧版 `alibaba/Chat2DB` 入口（已迁移）](https://github.com/alibaba/Chat2DB)
- [旧版 `CodePhiliaX/Chat2DB` 入口](https://github.com/CodePhiliaX/Chat2DB)

## Boundaries

- Always：固定 commit/tag；优先读取源码、测试和安全策略；使用本地命名测试数据库；把模型输出当不可信；记录 SQL、Schema、数据源、权限、Trace 和结果状态的关联；用确定性断言验证安全与副作用。
- Ask first：下载大型仓库或模型；安装新依赖、JDBC Driver、Skill、MCP Server 或外部插件；启动外部服务；连接任何非本地测试数据库；执行会改变数据、产生费用或发送外部请求的 SQL。
- Never：把截图中的 Star 数当成质量证明；把 Community 的本机优先当成多用户安全；把 Prompt、前端隐藏、`source: agent` 或一个 `allow=true` 当成最终授权；让生成 SQL 直接写生产库；把 `success: true` 或模型自评当成数据库执行证据；把未知第三方 Driver 当作普通配置文件。

## Start Trigger

本条目当前只进入 Work Pool，不自动下载、安装、运行或修改 Chat2DB。建议：

1. 完成 s10 System Prompt 基础后，先启动 Phase 0-2 的只读源码追踪；
2. 完成 s11 Error Recovery，并结合 `W-2026-007` 后，再启动 Phase 3 的 Tool/Permission/数据库安全实验；
3. 完成 s19 MCP Plugin 基础后，再启动 Phase 5 的 CLI/MCP 对照；
4. 完成 s12-s14 基础后，再研究迁移、报表、后台和定时任务；
5. 完成 s20 Comprehensive Agent 后，输出最终的跨章节迁移清单。

启动时需建立对应的 `specs/changes/C-YYYY-NNN-*.md`，并按规范从本文件移除或标记已转入 Change。

## Expected Output

- 一张 Chat2DB 当前版本的产品/模块/部署边界图；
- 一张从 UI、CLI、MCP 到 Text2SQL、SQL 校验、插件、数据库和结果返回的成功调用链；
- 一张包含 SQL 错误、权限拒绝、超时、响应丢失和 Prompt Injection 的失败/恢复链；
- 一份 Text2SQL、`get_tables_schema`、`execute_sql` 的输入/输出/权限/可靠性/审计契约表；
- 一份 Community/Pro/Enterprise/Local 与历史版本的事实、证据和未知项对照表；
- 一份多数据库插件与 Driver 的扩展边界、供应链和兼容性说明；
- 一套 15-25 条本地冻结 Eval 与确定性结果，覆盖质量、安全、成本、延迟和恢复；
- 一份“Chat2DB 机制 → 当前 s01-s20 / Work Pool → 可迁移学习点”的映射；
- 一份生产级检查清单和仍需进一步验证的风险，不直接把 Chat2DB 结论升格为通用最佳实践。

## Acceptance Criteria

完成后应能够：

1. 用自己的话解释 Chat2DB 为什么是一个比简单 Text2SQL Demo 更好的 Agent Harness/真实业务系统样本；
2. 从一个固定版本的源码或测试追踪只读主链路，并指出每层的责任边界；
3. 为一个 `execute_sql` 工具设计最小权限、SQL 校验、超时、分页、结果引用、审计和恢复契约；
4. 证明模型生成 SQL、Harness 放行和数据库最终执行是三个不同决策；
5. 解释多数据库插件、方言和 Driver 为什么不能只靠 Prompt 解决；
6. 用故障注入证明恶意数据库文本不能越权、危险 SQL 不会被直接执行、结果过大不会破坏上下文、响应丢失不会盲目重做副作用；
7. 用 Eval 区分 SQL 可解析率、执行正确率、业务正确率、安全拒绝率、unsafe acceptance、延迟、成本和恢复成功率；
8. 清楚标注当前版本事实、历史版本差异、项目选择、个人推断和未验证假设；
9. 能说明哪些结论应回写到 s01-s20 的学习笔记，哪些应继续留在本 Work Pool 或转为独立 Change。

## Non-goals

- 不在本 Work Pool 阶段把 Chat2DB 集成进当前教学项目；
- 不训练 Text2SQL 模型，不追求榜单成绩，不把一个模型的效果当作产品质量；
- 不连接、读取或修改真实生产数据库，不处理真实用户凭证和敏感业务数据；
- 不把 Community、Pro、Enterprise、Local 或历史版本的能力混为一谈；
- 不因为 Chat2DB 使用了某种框架、协议或插件，就把它认定为唯一正确架构；
- 不把可运行 Demo、产品文档、Issue、Star 数或模型自评单独当作生产安全证明。
