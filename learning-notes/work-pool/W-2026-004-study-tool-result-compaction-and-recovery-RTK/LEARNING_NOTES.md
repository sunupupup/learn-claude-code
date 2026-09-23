# RTK：工具输出压缩学习

## 任务范围与状态

- 开始日期：2026-09-23；当前为 D1 概念入门，后续按理解进度读源码与做实验。
- 任务：[C-2026-012](../../../specs/changes/C-2026-012-study-tool-result-compaction-and-recovery.md)。本轮仅学习 RTK，其他候选与完整业务恢复课题暂缓。
- 已固定只读源码样本：v0.49.0，Commit `b1c0dc00649c50fbe8930f849c800d4d6ca12091`（master 查询返回的版本）。尚未安装或运行 RTK；静态阅读不代表本机行为已验证。

## 为什么学习它与学习模式

衔接 s08_context_compact 的上下文压缩和 s13_background_tasks 的输出前缀截断：研究如何在工具结果进入模型前减少噪声，同时保留诊断信息。采用概念 → 一条命令的源码链 → 冻结输出实验的混合方式。

## 术语速查

| 术语 | 含义与层次 | 边界 |
| --- | --- | --- |
| CLI proxy / 命令行代理 | 工具执行层，代理运行实际命令并处理输出 | 不是模型本身 |
| Hook / 钩子 | Agent 执行框架在特定时机调用的程序 | 执行前改写命令与执行后过滤是两个步骤 |
| Filter / 过滤器 | RTK 内部按规则保留、分组、去重或省略内容的逻辑 | 不应把有损省略理解成 gzip 式无损压缩 |
| stdout / stderr | 操作系统进程的标准输出与标准错误流 | stderr 有内容不必然表示失败，退出码也要核对 |
| exit code / 退出码 | 进程结束状态，通常 0 表示成功 | 短摘要不能代替退出状态 |
| Tee recovery / 原文留存与回取 | 保存原始输出并提供读取入口 | 读取已保存结果与重新执行命令不同 |

## 我的原始理解

用户选择“就学这个”（RTK），随后提出“可以看成 tool call 的一个 hook”“类似于 AfterToolCall”。🟡 部分正确：过滤确实发生在底层命令执行之后，但自动接入实际使用执行前 Hook 改写命令；过滤仍在外层 Bash 工具返回之前发生。

## 校准后的结论与数据流

🟢 文档已核验：RTK 提供命令代理与过滤器；自动改写 Hook 是接入方式，手动调用也能进入过滤路径。

概念链（不是固定版本的函数调用栈）：

```text
模型提出命令请求
  → Agent 执行框架处理调用，适用时由 Hook 改写为 RTK 命令
  → RTK 执行底层命令
  → 过滤器精简输出
  → 工具结果返回模型
```

🟢 文档已核验：Tee 支持失败原文留存及路径提示，可避免为取回日志而重新执行命令；具体覆盖范围、配置、大小和轮转限制仍须在固定版本验证。

🟢 范围边界：Bash Hook 不自动覆盖 Claude Code 的内置 Read/Grep/Glob；压缩命令输出与整理历史消息属于不同位置的上下文管理。

## 来源与证据

- [项目 README](https://github.com/rtk-ai/rtk)：上一轮调研的输出过滤及接入边界依据。
- 本轮 Context7：先 resolve 获得 `/rtk-ai/rtk`，再 query 核对执行链、Hook 与 Tee；返回来源位于可变的 `develop` 分支。
- [TECHNICAL.md](https://github.com/rtk-ai/rtk/blob/develop/docs/contributing/TECHNICAL.md)：命令分发与恢复机制。
- [ARCHITECTURE.md](https://github.com/rtk-ai/rtk/blob/develop/docs/contributing/ARCHITECTURE.md)：Hook 改写与提示策略。
- [配置说明](https://github.com/rtk-ai/rtk/blob/develop/docs/guide/getting-started/configuration.md)：Tee 日志引用示例。

## 扩展理解：通用 Tool Result 压缩方式

用户提出：“大 result 持久化用占位符代替、直接裁剪、模型总结”。🟢 已验证的分类方向：三者分别属于外置、截断和语义摘要；这些机制可跨工具复用，但信息保留规则仍与具体任务有关。

以下是早期扩展讨论；其中业务字段筛选和聚合超出了用户随后明确的基础工具范围。最终范围与接入心智模型见下一节。

早期讨论涉及：

| 方法 | 例子 | 边界 |
| --- | --- | --- |
| 源头过滤、字段投影 | 订单工具只返回未支付订单的编号、金额、状态 | 需要工具接口支持；不能误删后续操作所需 ID |
| 代码聚合 | 对全部记录计算总数、总额和异常项，返回统计结果 | 应标明统计范围；抽样不等于完整统计 |
| 外置加按需读取 | 返回状态、预览、result_ref，再按行范围或关键词读取 | 纯占位符不足以指导回取；引用可能过期或无权限 |
| 分块检索 | 大日志建索引，只返回与当前错误相关的片段 | 检索不到不代表不存在，必须保留扩大检索入口 |
| 分层与分页 | 先看目录/概要，再查某个 ID 详情或下一页 | 分页本身不保证总 token 下降，全部读完仍可能很贵 |
| 去重与增量 | 相同报错加次数，轮询仅返回变化项 | 需保留基线版本；基线离开上下文后应能恢复快照 |
| 任务导向模型摘要 | 针对当前问题提取长报告的结论及证据位置 | 模型可能漏信息；计入摘要调用成本，保留原始证据 |

推荐起步组合（工程建议，未在本项目实现）：源头少取 → 确定性字段提取/聚合 → 大结果外置并给检索入口 → 按需模型摘要 → 带省略标记的最终长度上限。小结果直接保留。

🟢 官方资料核验：Anthropic 的工具设计文章讨论分页、范围选择、过滤及截断；代码执行文章说明中间结果在执行环境内过滤和聚合后再返回模型。Deep Agents 文档展示大结果外置后返回文件引用与预览，支持后续读取和搜索。

- [Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Deep Agents context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)

可靠性边界：压缩写操作结果时保留成功/失败/未知状态、资源或操作 ID 与恢复入口，不能因原文不在上下文中就重跑写操作。外置保护的是主模型上下文，并非全系统零成本；子 Agent 或摘要模型读取原文仍会消耗 token。

## 最终范围校准：Bash / Read File 基础工具

用户明确指出：“我说的是 bash、read file 等那些最通用的 tool”。本次学习重点是基础工具的统一结果处理层，不是订单等业务工具的字段筛选。

| 通用策略 | 实现要点 | 边界 |
| --- | --- | --- |
| 首尾截断 | 保留开头与结尾，标明中间省略 | 中间仍可能有关键错误 |
| 外置与按需读取 | 保存原文，返回预览、大小、引用，提供按行读取和搜索 | 引用需有效且可访问 |
| 去噪去重 | 去颜色控制码、进度条、重复行，保留重复次数 | 无需业务知识，但压缩能力有限 |
| 相关片段提取 | 按当前问题或关键词选择原文片段 | 漏检时允许扩大范围或读取原文 |
| 模型摘要 | 用模型读取大结果并总结，附证据位置 | 额外成本和延迟，也可能失真 |
| 历史结果淘汰 | 较旧的大结果换成引用，最近结果保留 | 处理的是多轮累积，不仅是单次结果大小 |

这些策略可以放在结果进入 messages 之前的统一处理层。Read File 可引用现有文件，但文件变化后需要快照或版本才能准确恢复；Bash 临时输出通常需另行保存。

### RTK 放在 Agent Loop 的哪里

用户的核心理解是：“封装好的能力，接进来调用；对很多常见命令已有一套结果优化策略。”🟢 就已读命令路径而言成立。CLI/SDK 的形式差异不影响这个接入心智模型。

```text
模型请求 run_bash("pytest")
  → run_bash 执行前把 pytest 改为 rtk pytest
  → RTK 执行真正的 pytest 并按专用规则过滤输出
  → run_bash 获得精简结果和退出码
  → Agent Loop 将工具结果追加到 messages
  → 下一轮模型读取精简结果
```

教学示例只需几行改写逻辑，是因为复杂过滤逻辑已封装在 RTK 中；不意味着能对任意复合 Bash 命令机械加前缀。实际 Hook 负责自动改写，RTK 内部负责执行及过滤。

RTK 已读的 pytest 路径是“认识命令格式的规则解析”，没有小模型摘要调用；不扩展为整个 RTK 所有功能都不用模型。外置、截断和模型摘要则可以作为未知格式结果的通用处理手段。

## 实验状态

尚未实验。后续先冻结一份成功和一份失败的测试输出，观察省略内容、错误定位、退出码与原文回取；不以重复运行有副作用命令来恢复日志。

## 生产级边界

- 压缩率与任务正确率分别衡量；短输出可能遗漏关键失败或警告。
- 完整输出落盘仍需考虑敏感信息、访问权限、清理策略及引用失效。
- Windows 自动改写支持有版本差异；旧 README 与 develop 文档不能混成同一已验证版本。
- 接入后仍需验证命令参数、退出码及权限检查的语义，过滤器不替代授权。

## 掌握状态与下一步

- 已完成：选定 RTK、关联已有任务、核对入门机制。
- 已完成：固定版本的 pytest 调用链静态阅读，见下文。
- 待验证：本机运行、失败恢复和压缩前后诊断信息完整性。
- 下一小步：按需要选择一份失败输出，逐行走过滤状态机。

## 源码初读：pytest 纵向链路（2026-09-23）

本节均对应上面的固定 Commit；通过 GitHub 读取源码，没有克隆、构建或执行项目。

1. [hook_cmd.rs:600](https://github.com/rtk-ai/rtk/blob/b1c0dc00649c50fbe8930f849c800d4d6ca12091/src/hooks/hook_cmd.rs#L600)：读取 `tool_input.command`，经过改写与权限决策后保留其他输入字段、替换 command，返回 PreToolUse 的 `updatedInput`。它处理的是命令输入，并不在此解析测试输出。
2. [main.rs:2699](https://github.com/rtk-ai/rtk/blob/b1c0dc00649c50fbe8930f849c800d4d6ca12091/src/main.rs#L2699)：Pytest 分支交给 `pytest_cmd::run`。
3. [pytest_cmd.rs:20](https://github.com/rtk-ai/rtk/blob/b1c0dc00649c50fbe8930f849c800d4d6ca12091/src/cmds/python/pytest_cmd.rs#L20)：选择 pytest 或 python -m pytest；未指定对应选项时加入 `--tb=short`、`-q`、`-rxX`，先让源命令少输出并显示预期失败/意外通过。再调用 `run_filtered_with_exit`。
4. [runner.rs:94](https://github.com/rtk-ai/rtk/blob/b1c0dc00649c50fbe8930f849c800d4d6ca12091/src/core/runner.rs#L94)：共享执行骨架捕获输出和退出码，调用过滤函数、生成恢复提示、输出结果并记录统计，返回退出码。pytest 选择 stdout_only；不据此声称所有命令都采用同样的 stderr 策略。
5. [pytest_cmd.rs:75](https://github.com/rtk-ai/rtk/blob/b1c0dc00649c50fbe8930f849c800d4d6ca12091/src/cmds/python/pytest_cmd.rs#L75)：逐行扫描，以 Header / TestProgress / Failures / Summary 四种状态区分输出区域，收集失败块和汇总计数。状态机（state machine）在这里就是“记住正在读哪一段，再按该段规则处理下一行”。
6. [pytest_cmd.rs:180](https://github.com/rtk-ai/rtk/blob/b1c0dc00649c50fbe8930f849c800d4d6ca12091/src/cmds/python/pytest_cmd.rs#L180)：构造短结果。纯通过可变成 `Pytest: N passed`；失败块通过 `>`、`E`、assert、error、`.py:` 等特征挑选关键行，每块最多三条相关行，并限制条目数及行长。这条路径是确定性规则，没有 LLM 摘要调用。
7. [tee.rs:31](https://github.com/rtk-ai/rtk/blob/b1c0dc00649c50fbe8930f849c800d4d6ca12091/src/core/tee.rs#L31)：恢复功能按配置分 Disabled / Tee / Sqlite；Sqlite 提示可为 `rtk recall <hash>`，还受输出大小、失败状态和存储可用性等条件影响。不是所有输出都必然保存。

重要校准：保存的“原文”是 RTK 实际执行命令后捕获的输出。如果已经给 pytest 加上 `--tb=short`，原文也不是未缩短堆栈的完整 traceback；回取只能恢复已捕获的数据。

边界处理：pytest 非零退出、且不是“无测试”的退出码 5，却被解析成“无测试”时，代码回退到限长原始文本，避免吞掉启动或配置错误。文件内包含纯通过、失败、quiet 模式、xfail/xpass 等测试，但本轮未运行这些测试。
