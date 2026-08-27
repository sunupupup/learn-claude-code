# W-2026-001：调研小型 Agent 项目的 Hook 生产实践

- Status: ready
- Area: Agent / Hook / Middleware
- Discovered From: `s04_hooks` 学习过程
- Owner: personal
- Priority: medium

## Work

选择一个规模较小、代码可运行、具有真实 Agent Loop 或 Runtime 的开源 Agent 项目，沿一次完整任务调用链研究其 Hook、Callback 或 Middleware 设计。

重点回答：

- 项目定义了哪些生命周期事件，它们分别属于 Session、Turn、Model Call、Tool Call 还是其他作用域？
- Hook 在哪里注册、由谁触发，业务代码是否需要感知触发点？
- Node-style 与 Wrap-style 扩展如何映射到实际控制流？
- Hook 的输入、输出、状态和 Runtime 参数采用什么契约？
- 多个 Hook 如何排序、串行、并行、短路或合并结果？
- Hook 超时、异常和非法输出如何处理，采用 fail-open 还是 fail-closed？
- 权限 Hook 与服务端授权、沙箱、人工审批之间如何分层？
- 日志、Trace、指标和审计如何关联一次 Run、Model Call 与 Tool Call？
- Hook 如何测试，是否覆盖拒绝、失败、重试和重复副作用？

## Reason Deferred

`s04_hooks` 已完成 D1 核心理论与代码阅读验收。当前继续推进后续基础章节；生产项目调研保留在 Work Pool，避免过早进入框架源码而把注意力从通用机制转移到具体 API。

## Start Trigger

满足以下条件后即可开始：

- 已完成 `s04_hooks` 的核心学习，能够画出当前代码的生命周期调用链；
- 能独立解释 Callback、Hook、Middleware，以及 Node-style 与 Wrap-style 的区别；
- 能解释执行模式、决策合并、失败策略和运行时结果四类 Hook 契约。

LangChain 最小运行实验可以作为本任务的第一个动手步骤，不再作为启动前置条件。

## Preferred Order

1. 建立候选项目筛选标准：代码规模、活跃度、可运行性、Hook 覆盖和文档质量。
2. 选择一个主项目，必要时选择一个框架作为对照，不同时深挖多个项目。
3. 画出一次成功 Run 与一次拒绝或失败 Run 的生命周期。
4. 从注册点追到 Runtime 分发点，再追到结果如何影响控制流。
5. 运行或编写最小实验，验证顺序、短路、异常和权限边界。
6. 把项目事实与通用 Agent 原理分开记录，并输出一份阶段性学习总结。

## Expected Output

- 一张 Hook 生命周期与调用链图；
- 一张 Hook 契约表，覆盖输入、输出、调度、合并和失败策略；
- 至少一个权限失败场景和一个 Hook 自身失败场景；
- 对教学版 `s04_hooks` 的差异清单；
- 是否值得将该项目作为后续 Agent 工程学习样本的结论。
