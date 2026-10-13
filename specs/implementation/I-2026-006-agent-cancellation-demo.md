# Agent 取消 Demo 实现与验证

- 日期：2026-10-13
- Change：[C-2026-023](../changes/C-2026-023-agent-cancellation-demo.md)
- 行为、代码导航和验收场景：[项目 README](../../practice/agent-cancellation-demo/README.md)。

新增错误示例与基本预约 Agent，更新 practice 索引。完整版本默认调用真实 DeepSeek，在 `run_agent()` 中完成工具选择、执行、结果回传与下一轮模型请求。在 loop、Hook、共同补偿、恢复与重试入口添加中文注释；通过代码赋值控制故障注入。两方持久状态分别保存在临时 SQLite 文件中。

验证环境：Python 3.12.10。以下命令均退出 0：

```powershell
python -X utf8 practice/agent-cancellation-demo/demo_01_wrong.py
python -X utf8 practice/agent-cancellation-demo/demo_02_complete.py all
python -X utf8 practice/agent-cancellation-demo/demo_02_complete.py all --offline
```

错误示例确认“界面已取消但预约仍有效”。完整示例 7 个场景断言通过，包含关闭连接、重新加载数据库后的恢复，以及重复调用副作用计数检查。

真实模型验证：完整 7 个场景全部通过。普通预约执行 3 轮真实模型请求（查询工具、创建工具、最终回答）；取消场景在创建工具内设置停止标记，完成 Hook 后不再请求下一轮模型。恢复场景在 Hook 前退出 loop，重开数据库后补偿成功。

未验证真实进程崩溃、真实预约外部 API、并发工作者或定时调度；其余教学边界以项目 README 为准。
