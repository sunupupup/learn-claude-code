# 工具事件流式展示与恢复验收

- 日期：2026-10-14
- Change：[C-2026-024](../changes/C-2026-024-tool-stream-demo.md)
- 实现入口：[README](../../practice/tool-stream-demo/README.md)
- 运行证据：[validation.json](../../practice/tool-stream-demo/validation.json)、[终端输出](../../practice/tool-stream-demo/demo-output.txt)

Python 标准库实现终端前端、独立后端、JSONL RPC、单会话单写入者锁、落盘前置发送和共享归约器。模型 SSE 与工具进度分别产生实时事件；持久化完整消息和工具开始/最终结果。恢复不执行已完成或结果未知的工具。

运行 `python check.py --live --report validation.json`：八个场景通过，包括真实 deepseek-flash 工具调用与最终总结，成功/失败/中断内容一致性、预期的落盘后未发送差异、部分尾行、重复 start 与锁所有权。Windows 已断开管道 flush/close 的 EINVAL 作为正常退出清理处理。

仅验证进程级故障，未验证断电或磁盘故障；没有严格一次、跨写入与发送事务、外部业务副作用或自动重试保证。未修改第三方 Pi、用户笔记、其他任务文件；未提交或 push。
