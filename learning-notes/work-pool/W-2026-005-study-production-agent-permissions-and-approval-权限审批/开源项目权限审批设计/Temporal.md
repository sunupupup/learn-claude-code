# Temporal：长时间审批与持久工作流

- **官方仓库**：[temporalio/temporal](https://github.com/temporalio/temporal)；[Python SDK](https://github.com/temporalio/sdk-python)；[Workflow Architecture](https://docs.temporal.io/architecture)
- **用途/层次**：工作流编排基础设施，将长时间业务逻辑状态化、持久化；可承载 Agent 审批等待，不是 Agent 授权策略引擎。
- **相关机制**：Workflow 历史重放、Signal/Update、Timer、Activity 重试、取消与 Worker 恢复；Agent 官方集成示例证明可组合，不代表内置 Agent 权限平台。
- **具体入口**：官方 durable execution tutorial、Signals/Timers/Workflow lifecycle；OpenAI Agents SDK 的 Temporal integration 作为两层组合入口。
- **前置/难度/顺序**：异步/分布式系统、幂等；中高；仅当审批可能等待数小时或跨进程恢复时学习。
- **维护/许可证（2026-09-26）**：Temporal Server GitHub API 显示 MIT、最近推送 2026-09-25、latest server release `v1.32.0`（2026-09-11）；SDK 有独立仓库和版本，需按将用语言另核。Temporal Cloud 商业托管。
- **优点**：把暂停很久、Worker 崩溃、超时和重试从内存线程变成持久工作流；适合讨论恢复和事件历史。
- **局限/边界**：工作流重放要求确定性；Activity 至少一次执行意味着外部副作用还需幂等；Temporal 不认证审批者、不替代数据授权，也不保证业务补偿成功。
- **建议观察**：审批请求做 Signal 后如何关联审批者与 Run ID；Timer 过期后如何进入 `expired`；Activity 失败重试怎样与副作用幂等配合。



