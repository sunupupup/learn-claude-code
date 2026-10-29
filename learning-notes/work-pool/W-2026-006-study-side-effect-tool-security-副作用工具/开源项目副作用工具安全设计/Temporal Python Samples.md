# Temporal Python SDK Samples

- 样例仓库：[temporalio/samples-python](https://github.com/temporalio/samples-python)
- SDK 仓库：[temporalio/sdk-python](https://github.com/temporalio/sdk-python)
- 官方文档：[Python Application Development Guide](https://docs.temporal.io/develop/python)、[Error handling / retries](https://docs.temporal.io/develop/python/failure-detection)、[Samples README](https://github.com/temporalio/samples-python#readme)
- Context7：ID `/temporalio/documentation`；已核对 Activity retry、幂等键和外部副作用语义。
- 本次查验：2026-09-26；Samples pyproject 声明 MIT，SDK 当前样例依赖范围显示 temporalio 1.32+；官方 samples 页面近期更新。固定版本前重新核对。
- 开源分类：MIT 开源样例和 SDK；Temporal Cloud 是商业托管产品，和开源源码分开。
- 难度/顺序：D2-D3，推荐第 4 个；部署面较大，先读样例代码，不急于启动服务。

## 适合回答的问题

后台 Activity 调外部业务 API 后发生超时/Worker 崩溃，持久工作流怎样记录进度、重试和查询？为什么 Activity 仍需业务幂等？

## 建议阅读入口

先读 `hello_activity_retry`、`hello_cancellation`、`polling`、`openai_agents` 和 `replay` 样例；之后按官方 Python 文档核对 Workflow/Activity、RetryPolicy、Timeout、Signal/Query。Context7 文档指出 Activity 重试时可用稳定的 Workflow Run ID + Activity ID 形成传给下游的幂等键，并提醒无限 retry 是可能的默认行为之一，实际业务必须设置合适边界。

## 前置、优势与局限

- 前置：异步 Python、HTTP/API 调用、重试、后台任务概念；D3 再看事件历史重放和 worker 版本治理。
- 优势：可靠执行、长时间等待和故障恢复是核心主题；官方样例覆盖 retry、取消、polling、replay 和 Agent SDK 组合。
- 局限：服务编排不会让第三方 HTTP、支付或通知天然幂等；Worker 可能重做 Activity；Temporal 也不替代授权/审批系统。
- 推荐对照：DBOS（应用库 + Postgres）或 Restate（Runtime 许可需单独看）二选一，不用同时部署多个引擎。

## 证据边界

官方文档描述的可靠执行机制经 Context7 核验；本章未运行 server/worker 或模拟外部系统，因此没有 observed-runtime 证据，也没有生产验证结论。
