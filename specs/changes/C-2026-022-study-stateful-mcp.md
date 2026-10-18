# C-2026-022：有状态 MCP 专题

- Status: active
- Area: MCP / Harness / 应用状态 / 幂等
- Source Work Pool: W-2026-035（用户直接要求开专题，直接建立 Change，不保留待启动卡）
- Discovered From: 2026-10-08 本次对话：MCP 状态、Harness 保存 Notion Page ID、服务端幂等记录。
- Learning Notes: [专题入口](../../learning-notes/work-pool/W-2026-035-study-stateful-mcp/LEARNING_NOTES.md)

## Objective

理解协议会话、业务对象、任务进度和操作执行记录的区别；以 Notion 编辑为主例，判断状态由 Harness、MCP Server 或下游系统管理时的价值与边界。

## Work

1. 整理本次已有调研与讨论，逐字保留用户理解并附批注。
2. 建立知识图谱，关联旧版 Streamable HTTP 会话、显式句柄、Durable Objects、Tasks 与 MRTR。
3. 单独解释基于执行记录的幂等为何属于服务端应用状态。
4. 后续按用户节奏选一个小问题继续；源码和实验另行启动。

## Expected Output

专题总览、知识图谱，以及保存原话、批注、技术来源和 Notion 例子的模块笔记。

## Success Criteria

- 必学：能区分协议无状态与应用有状态，解释模型上下文和程序状态的区别。
- 必学：能以 Notion 为例解释 Page ID、编辑基线、待应用修改、执行记录的职责。
- 必学：能解释“写入成功但响应丢失”为什么需要结果核对，不能把超时直接当失败。
- 选学：固定版本源码、持久化与多实例实验、并发冲突和崩溃恢复；本轮不要求完成。
- 文档归档完成不等于整个专题已经掌握。

## Boundaries

本轮仅整理已发生的讨论和已读取的官方资料，不实现服务，不写入真实 Notion，不安装依赖。Notion 案例是设计示例，未验证其当前接口能力。未改动已有未提交文件。

## Progress

- 2026-10-08：初始化专题与笔记；证据为本次对话中的官方文档核验及用户复述，无运行实验。

## Related

- [学习流程](../../PROMPT_4_WORK_POOL_LEARN.md)
- [s19 MCP 教学入口](../../s19_mcp_plugin/README.md)
- [完整 MCP 服务专题](C-2026-017-build-useful-mcp-server.md)：本专题聚焦状态，服务实现仍由原专题负责。
