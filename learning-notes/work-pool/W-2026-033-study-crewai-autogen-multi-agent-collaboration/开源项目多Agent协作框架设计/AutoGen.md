# AutoGen 项目学习入口

## 项目简介

AutoGen 是用于构建 Agent 应用的开源框架，官方资料将较高层的 AgentChat 描述为面向对话式单 Agent/多 Agent 应用的 API，并说明它建立在 Core 之上；Core 提供更底层、事件/消息驱动的编程模型。Context7 于 2026-09-27 查询到 AutoGen 官方仓库 README 标注项目处于 maintenance mode，并建议新项目关注 Microsoft Agent Framework。正式研究时需重新查证这些动态状态。

## 适合回答的学习问题

- AgentChat 中团队对话如何决定下一位 Agent 或终止运行？
- 轮流发言、选择发言者等策略改变了什么控制环节？
- AgentChat 隐藏了哪些 Core 运行机制？何时需要直接使用 Core？
- 消息是如何路由、关联和处理的？“会话历史”与“消息传递”有何区别？
- maintenance mode 对学习旧项目、新项目选型和版本升级分别意味着什么？

## 推荐观察重点

1. 从官方推荐的 AgentChat 入门示例开始，先理解一个多 Agent 对话循环。
2. 标出团队/发言者选择、消息传递、工具执行和 termination condition 所在层。
3. 选一个最小路径，观察 AgentChat API 调用怎样落到 Core 的事件/消息处理。
4. 核对运行结束、异常、取消和结果返回；不要把“对话终止”当成“任务已验收”。
5. 正式源码阅读时固定仓库版本和 Commit，并重查维护状态、迁移建议与许可证。

## 官方资料入口

- [AutoGen 官方文档](https://microsoft.github.io/autogen/stable/)
- [AutoGen GitHub 仓库](https://github.com/microsoft/autogen)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)：仅作为官方建议的后续方向背景，当前不列入同等深度主样本。

## 当前证据状态

- `documented`：Context7 于 2026-09-27 查询官方资料，核对 AgentChat/Core 分层和官方维护模式说明。
- `source-verified`：未进行。
- `observed-runtime`：未进行。
- 版本、Commit、许可证、源码入口和迁移结论：正式学习时重新核验。
