# Memory 开源方案调研与学习设计

调研日期：2026-09-19。本文是导师调研资料，不代表学习者已经掌握。学习进度与复述记录见 [LEARNING_NOTES.md](../LEARNING_NOTES.md)。

## 证据规则

- `source-verified`：已阅读指定 Commit 的相关源码，仅证明静态路径。
- `documented`：维护者文档描述，尚未运行验证。
- `proposed-experiment`：计划用实验回答，当前无运行结果。
- 不以 README、插件市场排名、测试文件存在或单次 Mock 成功证明生产可靠性。
- 本轮没有安装依赖、运行外部项目或调用付费模型；第三方源码没有放进本仓库。

## 1. 先把研究对象拆成四层

| 层次 | 负责的问题 | 阅读时找什么 |
| --- | --- | --- |
| 业务与事实来源 | 哪些内容值得记、属于谁、何时有效 | 用户输入、工具凭证、项目规则与元数据 |
| Harness / 接入层 | 何时读取、写入，怎样组成主模型请求 | Agent loop、事件订阅、工具注册、消息组装 |
| Memory 引擎 | 怎样提取、检索、去重、更新与整理 | add/search/update/delete 及内部调用链 |
| 存储与索引 | 正文、向量、历史、缓存如何落地与恢复 | 数据表/collection、事务边界、索引重建与删除 |

这四层是本次阅读框架，不要求每个项目都拆成四个独立服务。插件可以在 Harness 层调用外部引擎，也可以直接用文件完成所有记忆操作。

读取链路：用户问题与可信身份 → 限定作用域 → 构造查询 → 召回候选 → 筛选、去重、预算 → 组装当前模型输入 → 模型使用。

写入链路：原始事件 → 判断是否值得记忆 → 提取候选与来源 → 验证/冲突处理 → 保存正文及元数据 → 更新索引 → 后续可检索。

“查到了”“放进请求了”“模型使用了”“业务行为正确了”必须分别观测。保存到磁盘或向量库不会直接改变模型权重。

## 2. 接入方式与触发方式是两组独立选择

| 读取方式 | 工作方式 | 应观察的取舍 |
| --- | --- | --- |
| 常驻小摘要 | 每次请求带一份有限的用户/项目画像 | 稳定可见；占用固定预算；摘要可能过时 |
| 自动召回 | 程序在模型调用前检索并注入 | 不依赖模型主动想起；查询过宽会引入噪声 |
| 按需工具 | 模型调用记忆搜索/读取工具，结果进入后续请求 | 可逐步查证；存在漏调用、延迟和工具预算 |
| 混合方式 | 小摘要常驻，相关项自动召回，细节按需读取 | 可分层控制预算；需防止重复注入和相互冲突 |

上述是工程模式，不代表所有项目都实现了全部能力。工具访问协议本身不决定记忆如何存储，也不保证模型会调用工具。

| 写入时机 | 适用学习例子 | 必查问题 |
| --- | --- | --- |
| 用户明确要求时 | “记住这个项目使用 npm” | 是否已持久化再报告成功？scope 是否正确？ |
| 单轮完成后 | 提取本轮确认的新事实 | 是否重复提交旧历史？回复中的猜测会不会变事实？ |
| 空闲防抖后 | 多轮交流结束后再集中处理 | 新请求是否重置计时？进程关闭是否丢工作？ |
| 压缩前 | 重要原始信息即将被裁剪 | 是否重复处理？未完成工具结果会不会被当结论？ |
| 后台周期整理 | 合并重复、修正摘要、清理过期数据 | 并发、任务认领、失败重试、旧版可读性 |

“热路径（hot path）”是在当前请求处理路径中完成；“后台处理”可以降低当前请求等待，但会产生写入延迟与后台任务恢复问题。概念来源：[LangGraph Memory overview](https://docs.langchain.com/oss/python/concepts/memory)。

## 3. 学习“记什么”，再讨论文件还是向量库

| 信息 | 示例 | 学习目标 |
| --- | --- | --- |
| 语义记忆 Semantic memory | 用户偏好中文解释；项目使用 pnpm | 事实及偏好的来源、scope、生效范围 |
| 情景记忆 Episodic memory | 上次部署失败的现象、处理和证据 | 保存足够背景，避免将偶然成功泛化 |
| 程序性记忆 Procedural memory | 发布前先执行某组检查 | 经验成为规则前应如何评测和版本化 |
| 会话/任务状态 | 等待审批；任务执行到第 3 步 | 由明确状态管理承担，不依赖模糊自然语言召回 |
| 权威业务事实 | 订单是否已支付、生产权限 | 回到权威系统核验，不能用旧记忆替代 |

前三类是学习用分类，不是必须建立三个数据库。语义记忆也不等同于语义向量搜索。分类参考：[LangGraph 概念文档](https://docs.langchain.com/oss/python/concepts/memory)。

用户说“这些应该都是很重要的数据”：应进一步区分原始证据、提取后的事实、模型总结与推断。重要数据需要来源与可恢复性；推断结果仍需允许纠正与失效。

建议在源码中核对这些概念字段，而非假设项目都有：memory_id、用户/租户/项目、原始事件 ID、正文、来源类型、记录时间、生效时间、失效时间、被哪条新事实替代、版本、删除状态。

## 4. mem0 的版本陷阱

固定源码：[`a39a802bbc93e85b820078cd3c4dbaf53af25dbe`](https://github.com/mem0ai/mem0/tree/a39a802bbc93e85b820078cd3c4dbaf53af25dbe)，该快照 Python 包版本为 `2.1.0`，许可证见同一快照的 [LICENSE](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/LICENSE)。以下源码结论仅针对这个快照。

当前官方 [OSS v2→v3 算法迁移说明](https://docs.mem0.ai/migration/oss-v2-to-v3)描述自动 add 路径从新增/更新/删除决策转向追加新事实。算法名称不能直接当成 PyPI 软件包主版本。

需要分清四种变化：

1. 从新消息自动提取并追加事实；
2. 程序显式按 memory_id 修改或删除；
3. 后台把多个记录整理为摘要或手册；
4. 检索阶段判断哪些事实对当前问题仍有效。

新旧记录同时存在，并不自动证明回答会采用正确的现状；必须分别测试“现在是什么”和“以前是什么”。记录更晚也不必然更可信：可能只是后来转述的旧事件或不可信输入。

### 已阅读的源码入口

| 阅读位置 | source-verified 结论 | 对应学习问题 |
| --- | --- | --- |
| [README 接入示例](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/README.md#L209) | 外层调用 search、拼接 system prompt、调用主模型，再 add | 检索结果怎样进入主模型；示例中的 role 是实现选择，不是通用要求 |
| [add 提取路径](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/mem0/memory/main.py#L916) | 自动提取路径结合 scope 内近期消息和相关旧记忆，提取新事实、嵌入并批量写入 | 原始事件、提取 Prompt、记忆记录分别是什么 |
| [去重](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/mem0/memory/main.py#L1005) | 哈希去重针对当前批次及取回的旧记录 | 不是全库唯一性，也不是事件重放幂等证明 |
| [search 内部](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/mem0/memory/main.py#L1628)与[scoring.py](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/mem0/utils/scoring.py) | 语义搜索提供候选，BM25 与实体分数辅助排序；先按语义阈值过滤，再融合可用分数 | 召回候选与排序是两个阶段；关键词信号不是独立候选并集 |
| [显式 update](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/mem0/memory/main.py#L1815) | 按 ID 更新文本/元数据/到期日，更新向量并记录历史；身份字段受保护 | ADD-only 自动提取不等于不存在修改 API |
| [删除路径](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/mem0/memory/main.py#L2100) | 删除向量后把旧内容写入 SQLite DELETE 历史 | 不再召回与所有副本物理删除不同 |
| [storage.py](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/mem0/memory/storage.py#L102) | SQLite 还承担变更历史与近期消息存储 | 向量库不是唯一的数据落点 |
| [提取 Prompt](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/mem0/configs/prompts.py#L468) | 同时处理用户与助手文本，提示中要求区分用户事实与助手推荐 | 提示词意图是否真的实现，要用 E07 验证 |

### 不应从这些源码推导的结论

- `Memory`/`AsyncMemory` 是 OSS 引擎；`MemoryClient`/`AsyncMemoryClient` 是远程客户端。OSS 不等于自动离线，是否发到外部模型取决于配置。
- 当前 OSS [add 的 timestamp 检查](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/mem0/memory/main.py#L817)与 [search 的 reference_date 检查](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/mem0/memory/main.py#L1432)会拒绝这些参数。显式到期日是另一能力，不能概括成 OSS 自动理解所有时间关系。
- 当前实体索引不等于旧版知识图谱。迁移文档说明旧 OSS 图能力移出，不应拿旧示例展示新版能力。
- 多个写入位置存在，并不自动证明共同事务；必须实验验证向量、历史与实体索引部分失败后的状态。
- Context7 有资料声称 Platform 不支持 update；当前[客户端实现](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/mem0/client/main.py#L425)仍有该方法。这里只确认客户端请求路径，托管后端行为未实测。

## 5. 必做的小型实验集（均未运行）

统一素材：用户 Alice 默认 pnpm；项目 A 后来改成 npm；项目 B 保持 pnpm。用户 Bob 从未提供包管理器偏好。

| 编号 | 实验问题 | 需要保存的证据 |
| --- | --- | --- |
| E01 | 新会话是否能使用旧偏好？ | 写入记录、search 结果、最终模型请求、回答 |
| E02 | search 命中但故意不注入，会发生什么？ | 两组最终请求差异；不能只看偶然猜对的答案 |
| E03 | “添加依赖”能否找出“使用 pnpm”？ | 原查询、候选、分数、最终入选项；比较中文与改写 |
| E04 | 同一用户不同项目会不会互相覆盖？ | 用户/项目过滤条件、A/B 两个查询与全部候选 |
| E05 | 向 Bob 查询 Alice 的偏好会怎样？ | 可信身份来源、授权检查、是否有跨用户结果 |
| E06 | 自动追加更正与显式 update 有何差别？ | get/list/search/history 的前后对照 |
| E07 | 模型回复“应该部署好了”，没有工具成功证据，是否会记成事实？ | 原始消息角色、提取结果、来源丢失的位置 |
| E08 | 一轮事件重放两次会重复写吗？ | 事件 ID、去重键、记录数；区分文本相同与语义相同 |
| E09 | 后台写入未完成就开启新会话会怎样？ | 触发、排队、持久化、可检索的各时间点 |
| E10 | 写完正文但更新索引/任务状态前崩溃会怎样？ | 崩溃点、重启状态、重复/丢失与恢复步骤 |
| E11 | 删除后哪些副本仍有原文？ | 主存储、历史、摘要、缓存和备份的检查结果 |
| E12 | 没有答案、恶意记忆、超预算分别怎样处理？ | 空结果策略、输入边界、注入预算和工具行为 |

实验按学习进度逐个做，不一次搭建完整生产系统。先用可控替身检查编排与数据路径；需要验证 LLM 提取/向量语义效果时，再选择明确配置的模型并运行。Mock 结果不能代替语义质量证据。

## 6. 怎样衡量学会与系统有效

分别度量：提取的事实是否有依据、目标事实是否被召回、是否正确注入、最终回答/动作是否正确、过期或跨范围信息是否被误用。

对照至少包含：无跨会话记忆、固定小摘要、按需召回。同一组输入、模型、提示和预算下记录质量、注入 Token、模型/Embedding 调用数、写入延迟、回答延迟。主模型 Token 减少不必然代表总成本下降。

评测题型借鉴而非立即跑完整榜单：

- [LongMemEval](https://github.com/xiaowu0162/LongMemEval)：信息提取、多会话推理、知识更新、时间推理、无依据时不作答。
- [LongMemEval-V2](https://github.com/xiaowu0162/LongMemEval-V2)：进一步关注工作流知识、环境特有陷阱、状态变化、前提是否适用；适合后续从聊天偏好扩展到 Coding Agent 经验。

本次不引用不同厂商的准确率作排名：数据集版本、Reader 模型、检索预算、延迟口径和托管特性不同会让数字失去可比性。

## 7. 后续扩展的进入条件

| 方向 | 何时值得学习 | 当前安排 |
| --- | --- | --- |
| Letta 的常驻块与归档检索 | 想比较模型主动管理记忆、常驻与按需的区别 | 可选概念对照，尚未源码核验 |
| LangMem 的 Profile/Collection | 想比较单份用户画像与多个记忆条目的更新 | 可选资料阅读，当前不换主框架 |
| Hindsight 的证据与推断分层 | 当前系统难以追溯结论、时间关系或经验来源 | 进阶研究候选，当前不引入其完整系统 |
| 图谱/复杂时序索引 | 已通过实验发现简单召回无法回答关系问题 | 按需求进入，和 W-025 衔接 |

资料入口：[Letta archival memory](https://docs.letta.com/v1-sdk/memory/archival-memory/)、[LangMem conceptual guide](https://github.com/langchain-ai/langmem/blob/41a6c3b3/docs/docs/concepts/conceptual_guide.md)、[Hindsight 论文](https://arxiv.org/abs/2512.12818)。这些只是能力地图，不是要同时学习的项目清单。

## 8. DSH 插件对照与阅读入口

调研选择标准是：调用链能看清、和主线有不同机制、源码可固定，而不是星数或“几层记忆”的命名。这里的“官方 mem0 插件”指 mem0ai 仓库内维护的集成，不是 DeepSeek 官方维护声明。

| 实现与固定快照 | 已读源码的机制 | 在本次课程中的位置 |
| --- | --- | --- |
| [mem0 deepseek-plugin](https://github.com/mem0ai/mem0/tree/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/integrations/deepseek-plugin) | 请求组装时自动召回；完成回合后异步捕获；另有显式工具 | 主项目内的接入阅读；后端是 Platform，不执行它来证明 OSS 引擎行为 |
| [yan5236/dsh-memory](https://github.com/yan5236/dsh-memory/tree/a05ca71a1caa073d88aee55ec6be1e55a93eaa3e) | 会话增量提取 → 全局整理 → 摘要常驻及按需工具 | 唯一需要深入的外部窄对照，关注调度和文件一致性 |
| [NattoCB/dsh-plugin-memory](https://github.com/NattoCB/dsh-plugin-memory/tree/a83fccef21f74d5242df5df0ab5c0be7ae8ddf8b) | 首次索引注入、每步相关文件注入、idle 提取 | 可选对照片段；不读完整项目 |
| [orangeshinee/dsh-mem0](https://github.com/orangeshinee/dsh-mem0/tree/c18fdd8ae67c8a461a450b0c12f1b9a9a87f00c5) | 自托管 REST 工具；未见自动召回/捕获 hook | 仅说明工具接入与自动接入的区别 |

市场只作发现入口：[英文目录](https://dshmarket.com/browse/)、[用户提供的中文目录](https://dshmarket.com/zh/browse/#memory)。本次成功读取英文目录并确认 NattoCB、orangeshinee；不声称另外两项当前已上架。市场可访问性在工具间存在差异，不据此推断项目状态。

### mem0 插件：自动行为是由接入代码完成的

源码：[index.ts](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/integrations/deepseek-plugin/src/index.ts)、[共享 lifecycle.ts](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/integrations/agent-plugin-core/typescript/src/lifecycle.ts)。

- `apply()` 创建远程 `MemoryClient`。`host` 配置指 Platform 地址，不能理解成任意 OSS 服务可替换。
- `system-prompt/assemble` 取最新的真实用户消息作为 query，执行 search，再把结果加入 `assembly.contexts` 的 `mem0:recall`。
- `session/event` 收集真实 user 与 assistant 文本；只在 completed 回合调用 add。工具输出与插件注入消息不在自动捕获集合。
- 自动路径按配置的 userId 过滤，未附带仓库或 cwd 作用域；项目隔离不能凭插件名称推断。
- 共享逻辑对查询和注入字符数设预算，搜索等待默认约 2 秒；失败时可以不注入而继续主流程。`Promise.race` 超时不代表底层 HTTP 已取消。
- 每会话按已见 memory ID 去重。应补测 E13：相同 ID 更新内容后、压缩移除旧上下文后，相关内容是否重新出现。
- 捕获为不等待的异步调用，缓冲保存在内存 WeakMap；当前插件路径未见持久出箱或队列。这是崩溃实验的依据，不是“已证实一定丢数据”。

宿主概念来源：[DSH system-prompt 文档](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/system-prompt.md)、[session 文档](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/session.md)。当前文档区分 system `section` 与动态 `context` 快照；后者形成 user-role 消息，因此 hook 名称不是消息 role 的证明。这些是 master 文档；插件兼容的 DSH 版本仍须在运行前固定并核验，未作跨版本运行保证。

### yan5236：把提取与整理分成两阶段

| 入口 | source-verified 内容 |
| --- | --- |
| [index.ts](https://github.com/yan5236/dsh-memory/blob/a05ca71a1caa073d88aee55ec6be1e55a93eaa3e/src/index.ts) | turn-stopping 与根 session-start 触发；Phase1 → Phase2 → reload 注入缓存 → flush 状态 |
| [phase1.ts](https://github.com/yan5236/dsh-memory/blob/a05ca71a1caa073d88aee55ec6be1e55a93eaa3e/src/phase1.ts) | 按 lastSeq 读增量会话，生成来源回顾与 raw memory，记录处理位置 |
| [phase2.ts](https://github.com/yan5236/dsh-memory/blob/a05ca71a1caa073d88aee55ec6be1e55a93eaa3e/src/phase2.ts) | 汇总旧手册、旧摘要、raw、手动笔记与回顾索引，更新手册及注入摘要 |
| [inject.ts](https://github.com/yan5236/dsh-memory/blob/a05ca71a1caa073d88aee55ec6be1e55a93eaa3e/src/inject.ts) | 通过 systemPrompt.section 注入缓存摘要，区别于 mem0 的 contexts 路径 |
| [tools.ts](https://github.com/yan5236/dsh-memory/blob/a05ca71a1caa073d88aee55ec6be1e55a93eaa3e/src/tools.ts) | 读取/搜索文件；search 为忽略大小写的子串匹配，并非向量搜索 |
| [files.ts](https://github.com/yan5236/dsh-memory/blob/a05ca71a1caa073d88aee55ec6be1e55a93eaa3e/src/files.ts) | 单文件临时写入与 rename；批量处理跨多个文件及状态操作 |

由源码提出、尚未实测的反例：

1. 单文件原子替换不足以证明两个摘要文件、raw 归档与持久状态整体事务一致；在各步之间中断。
2. Phase1 增量不足阈值时仍可推进 watermark（已处理到的位置）；用“只补一句重要更正”测试是否被跳过。
3. 从事件中纳入插件消息时，标注来源与彻底排除不是同一保护；检查记忆反复回灌。
4. 全局目录和 cwd 标签不等于逐用户访问控制；作为单人案例阅读，不直接宣称可多租户部署。

### 两个可选对照片段

- NattoCB 的 [index.js](https://github.com/NattoCB/dsh-plugin-memory/blob/a83fccef21f74d5242df5df0ab5c0be7ae8ddf8b/src/index.js)：自动提取不覆盖已存在 topic，显式 write 才可覆盖；LLM 选择阶段给候选路径名，不给全文。所以“使用 LLM 选择”不等于模型已经阅读完整记忆。
- orangeshinee 的 [index.ts](https://github.com/orangeshinee/dsh-mem0/blob/c18fdd8ae67c8a461a450b0c12f1b9a9a87f00c5/src/index.ts)：注册 REST 工具和说明，没有自动 pre-step search/completed capture。只用它回答“装了工具是否就会自动记忆”。

## 9. 本轮调研限制

已通过 Context7 查询 mem0、DSH、LangGraph，并通过维护者源码/文档核验关键路径。Exa 三组有效搜索各返回最多 5 项，涵盖概念、评测和进阶架构；仅保留一手来源用于技术结论。

没有运行测试或实验。固定源码能解释代码打算怎么做，不能证明具体模型会正确提取中文偏好、解决冲突，也不能证明并发与崩溃场景稳定。源码学习时先固定宿主/插件/SDK 组合，再逐项验证。
