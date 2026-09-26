# CodeWhale

> 初步状态：已从官方资料找到与上下文压缩相关的调查入口（documented / source locator）；未固定 Commit，未确认完整调用链，也没有 observed-runtime 或 production-proven 证据。

## 为什么纳入

作为 W-2026-032 的缓存专项项目，补充观察 replacement compaction 与缓存前缀稳定性的取舍。

## 项目与源码入口

- 官方仓库：[源代码与版本](https://github.com/codrstudio/code-whale)
- 官方压缩文档/源码入口：[初步入口](https://github.com/codrstudio/code-whale/blob/main/docs/CONFIGURATION.md)
- 第二观察入口：[源码/配置](https://github.com/codrstudio/code-whale/blob/main/crates/tui/src/prompts.rs)
- W-2026-032 对应 Prompt/缓存笔记：[关联笔记](../../W-2026-032-study-agent-context-organization-and-prompt-cache-Context缓存/开源项目缓存设计/CodeWhale.md)
- 固定版本、Commit、许可证和核对日期：正式源码学习时登记；以上 main 链接只用于定位，不是固定证据。

## 正式学习要追的调用链

超限/阈值检测 → 压缩触发 → 安全切点或事件投影 → 摘要/结构化状态生成 → 消息协议验证 → Transcript/Checkpoint 持久化 → 重试、继续或停止 → Trace 与测试。

## 核心问题

1. 该实现是 proactive/auto/manual 还是 API 拒绝后的 Reactive Compact？它们的入口有何区别？
2. 多个 Tool Call、并行结果、部分失败或未完成调用怎样保持协议一致？
3. 用户原始指令、当前任务状态、最近尾部、工具结果和关键文件如何取舍？
4. 摘要无法生成、结果仍超限、并发状态改变或权限撤销时如何恢复或终止？
5. 可重复测试怎样证明协议有效、关键状态保留且不会重复副作用？

## 证据记录

- 官方文档结论：待按固定版本核对。
- 源码调用链：待追踪；记录文件、符号和 Commit。
- 运行时观察：未进行。
- 结论边界：不从产品文档直接推断生产可靠性、命中率或任务质量。

## 下一步

检查官方资料入口指向的压缩实现，再从触发点反向追到消息重建、持久化和测试；正式源码深读前先固定仓库 Commit 与许可证。
