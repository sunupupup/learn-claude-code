# Codex

OpenAI 的编程 Agent。公开仓库包含 CLI 与 app-server（供客户端使用的后端服务），适合学习会话、工具执行及客户端协议。
已加入输入预测、Goal 与沙箱模块；公开后端源码与桌面端实际行为分别核验。

- 官方仓库：[openai/codex](https://github.com/openai/codex)
- 研究范围：公开 app-server 协议，以及 `codex-rs/core`、`codex-rs/sandboxing`、`codex-rs/linux-sandbox` 的执行支撑机制。
- 输入预测源码基线：`740e5af33c71225640e0c1c1555c514c2c93ab74`；其他模块独立固定版本，见各模块入口；不代表本机桌面端版本。
- 许可证：公开仓库该基线为 Apache-2.0；不据此判断桌面应用的许可范围。
- 核验日期：2026-10-15。

## 学习模块

- [输入预测（Composer Prediction）](输入预测模块.md)：如何根据当前会话生成下一条输入建议？已初始化。
- [Goal 实现深入解析](goal实现深入解析.md)：目标如何持久化、如何触发下一轮及判断停止？已初始化，暂缓学习；源码基线待单独固定。
- [沙箱](沙箱.md)：一条 shell 命令怎样经策略选择、进程包装和操作系统限制进入受限执行？先学 Linux；已初始化。
