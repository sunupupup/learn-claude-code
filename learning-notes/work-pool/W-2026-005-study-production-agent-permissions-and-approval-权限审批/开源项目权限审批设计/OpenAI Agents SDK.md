# OpenAI Agents SDK：工具审批与 Run 恢复

- **官方仓库**：[openai/openai-agents-python](https://github.com/openai/openai-agents-python)；[Human-in-the-loop 官方指南](https://openai.github.io/openai-agents-python/human_in_the_loop/)；[server-side approval 示例](https://github.com/openai/openai-agents-python/blob/main/examples/agent_patterns/human_in_the_loop_server.py)
- **用途/层次**：开源 Agent Harness SDK，适合观察工具调用审批如何暂停 Agent Run 并由应用恢复。
- **相关机制**：`needs_approval`、`RunResult.interruptions`、`RunState.approve/reject`、序列化后恢复、嵌套 Agent 的审批冒泡。
- **具体入口**：文档 `human_in_the_loop.md`；源码 `src/agents/run_state.py`；示例 `examples/agent_patterns/human_in_the_loop.py` 与 `_server.py`。
- **前置/难度/顺序**：懂 Python 函数工具、异步与基本 Agent Loop；低中；本章默认主项目首选。
- **维护/许可证（2026-09-26）**：GitHub API 显示 MIT、最近推送 2026-09-25、latest release `v0.22.3`（2026-09-17）。固定 tag 时仍需核该 tag LICENSE 与 API 兼容版本。SDK 源码开放；OpenAI 托管模型和其他 API 服务不因 SDK 开源而免费或开源。
- **优点**：人类审批和状态恢复入口直接，能看到“只批准当前调用”与“Run 内同类调用继续批准”的区别；官方指南直接提醒快照的完整性和归属必须由服务端保证。
- **局限/边界**：SDK 提供流程原语，不替应用实现 reviewer 身份认证、所有权校验、租户隔离、审批界面、策略平台或外部副作用事务。静态文档不是生产可靠性证明。
- **建议观察**：审批状态是否绑定原始 tool call ID/参数；服务端如何存 RunState；暂停之后由谁决定恢复；嵌套委派怎样将权限请求暴露给顶层 Run。
- **核验补充**：Context7 解析 `/openai/openai-agents-python` 并查询官方 HITL 文档，2026-09-26。Context7 给出的接口/片段仅用于资料入口，源码学习时应固定版本。


