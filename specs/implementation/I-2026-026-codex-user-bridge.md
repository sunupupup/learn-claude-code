# Codex 本地用户通信插件实现

- 日期：2026-10-20
- 对应变更：[C-2026-027](../changes/C-2026-027-codex-user-bridge.md)
- 实现入口、调用链与运行方法：[项目 README](../../practice/codex-user-bridge/README.md)
- 验证与未验证边界：[阶段验收](../../practice/codex-user-bridge/docs/validation.md)
- 结果：10 项检查通过；默认 5555 服务与真实 MCP 客户端闭环通过；隔离 Codex 插件安装、技能与两个工具发现通过。
- 补充：用户明确要求后，真实 Codex CLI 发送 1 次、查询 2 次，pending → pending → answered；工具事件与数据库交叉核对通过，使用现有账号额度。
- 后续：长期 Goal 调度验收；真实渠道由用户明确启动后再接入。
