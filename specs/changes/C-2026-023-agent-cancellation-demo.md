# Agent 取消与业务补偿最小实战

- 状态：done
- 日期：2026-10-13
- 用户已确认：两个 Demo；Hook 补偿、恢复与重试合为一个完整 Demo，打断直接赋值模拟；关键代码须有可搜索中文注释。
- 设计与运行唯一入口：[项目 README](../../practice/agent-cancellation-demo/README.md)。

Python 标准库实现错误对照与基本预约 Agent；完整版本默认接真实 DeepSeek，在 `run_agent()` 中执行模型—工具循环，并用独立 SQLite 数据库区分工作流记录与模拟外部预约事实。Hook 与恢复共用 `reconcile()`。显式 `--offline` 才使用脚本模型。复用订单客服模型客户端，不修改其行为；不接真实网页、预约系统或自动调度。

实现与验证见 [I-2026-006](../implementation/I-2026-006-agent-cancellation-demo.md)。
