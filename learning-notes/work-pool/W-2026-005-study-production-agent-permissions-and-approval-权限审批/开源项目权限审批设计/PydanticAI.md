# PydanticAI：Deferred Tool 审批

- **官方仓库**：[pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai)；[Deferred tools / approval 文档](https://ai.pydantic.dev/deferred-tools/)
- **用途/层次**：Python Agent 框架，用于研究工具审批作为延后执行/外部结果的一种实现。
- **相关机制**：`requires_approval=True`、运行时 `ApprovalRequired`、deferred tool call、`tool_call_approved`；也明确指出客户端 history 不可信时，审批不等于授权。
- **具体入口**：文档 Deferred Tools、Adapters trust model、tool call approval 示例；从 deferred result 的 request ID 追到工具执行。
- **前置/难度/顺序**：Python async、模型工具调用；低中；可作为 OpenAI Agents SDK 之后的短对照。
- **维护/许可证（2026-09-26）**：GitHub API 显示 MIT、最近推送 2026-09-26、latest release `v2.51.0`（2026-09-25）；官方版本政策记录 V2 已于 2026-06-23 stable。托管服务/附加产品的许可和收费应单独核对。
- **优点**：把审批当作 Deferred Tool 语义，能看见“工具未执行，需要外部解决”与“Run 中途 UI 确认”的关联；官方文档特别强调 adapter 鉴权和工具内授权不可省略。
- **局限/边界**：Realtime 会话与普通 run 的暂停/恢复机制不同；客户端提交的历史或 approval 状态若不可信，不能作为授权依据。SDK API 能力不等同部署层安全。
- **建议观察**：审批结果如何映射回 tool_call_id；哪些数据由客户端带回；工具函数执行前是否再次校验可信服务端授权。



