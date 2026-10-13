# 工具流式事件与会话恢复教学项目

- 状态：done
- 日期：2026-10-14
- 用户授权：独立终端前端与后端、真实 DeepSeek、确定性故障验证；不提交或 push。

选择 Python 标准库与 stdin/stdout JSONL RPC，避免 HTTP 服务和框架遮蔽事件边界。前端启动后端子进程，工具产生多次进度；最终消息、工具开始/结束先落盘再发送；中间 delta/update 仅实时发送。共用状态归约器比较稳定字段，中断显示结果未知且不重试。

验收：成功、工具失败、进程中断、写入后未发送、部分 JSONL 尾行；完成后重启恢复不得执行工具；真实 deepseek-flash 工具调用与最终总结。设计、协议与操作主要来源：[项目 README](../../practice/tool-stream-demo/README.md)。

实际验证与边界：[I-2026-007](../implementation/I-2026-007-tool-stream-demo.md)。
