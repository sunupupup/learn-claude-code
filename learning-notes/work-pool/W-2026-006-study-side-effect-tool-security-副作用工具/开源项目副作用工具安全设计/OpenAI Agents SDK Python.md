# OpenAI Agents SDK for Python

- 仓库：[openai/openai-agents-python](https://github.com/openai/openai-agents-python)
- 官方文档：[Human in the loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)、[Run State API](https://openai.github.io/openai-agents-python/ref/run_state/)、[Guardrails](https://openai.github.io/openai-agents-python/guardrails/)
- Context7：ID `/openai/openai-agents-python`；已核对官方 HITL、RunState 恢复与快照安全说明。
- 本次查验：2026-09-26；当前 pyproject 显示版本 0.22.3、MIT，近期发布/代码活动可见。真正学习时须重新固定 tag/commit。
- 开源分类：MIT 开源 SDK。
- 难度/顺序：D1-D2，推荐第 2 个，适合作为本章 Agent 执行主样本。

## 适合回答的问题

Agent Tool Call 怎样在 Harness 层变成“待审批”，批准/拒绝后如何恢复原 Run？运行快照能保存什么，应用还必须负责什么？

## 建议阅读入口

1. 官方 HITL guide：`needs_approval`、interruptions、`RunState` 保存/恢复；
2. `examples/agent_patterns/human_in_the_loop.py`：最小暂停—批准/拒绝—恢复；
3. `examples/agent_patterns/human_in_the_loop_server.py`：server-owned snapshot、owner check 和 single-use approval；
4. 源码追踪候选：`src/agents/run_state.py`、tool execution pipeline、approval item 的创建和恢复路径（正式读源码时固定版本再找行号）。

## 前置、优势与局限

- 前置：Python 函数/异步函数和基本 Agent Tool 概念；D2 时再理解序列化快照和会话一致性。
- 优势：审批 API 路径较清晰；官方文档明确提示 serialized RunState 不负责认证审批人，必须由应用保存可信状态、认证/授权审批人并防止并发/重放审批。
- 局限：SDK 不是业务授权服务器、事务协调器或幂等订单系统；`needs_approval` 不代替业务服务授权。模型提供的参数仍需在执行前后做可信校验。
- 推荐搭配：用 OpenAI 客服 Demo 提供场景，再用 LangGraph 或 Temporal 做恢复模型窄对照。

## 证据边界

Context7 与官方文档核验了文档化的 API 和重要安全边界；不代表本章已经运行了 SDK，也不代表任何生产应用按要求验证了审批身份或单次消费。
