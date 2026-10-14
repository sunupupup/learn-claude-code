# Codex

OpenAI 的编程 Agent。公开仓库包含 CLI 与 app-server（供客户端使用的后端服务），适合学习会话、工具执行及客户端协议。
本次从桌面端 Composer Prediction 切入；公开后端源码与桌面端实际行为分别核验。

- 官方仓库：[openai/codex](https://github.com/openai/codex)
- 本次研究范围：桌面端输入预测，以及公开 `codex-rs/app-server`、`codex-rs/app-server-protocol` 中的相关支撑机制。
- 源码基线：`740e5af33c71225640e0c1c1555c514c2c93ab74`；不代表本机桌面端版本。
- 许可证：公开仓库该基线为 Apache-2.0；不据此判断桌面应用的许可范围。
- 核验日期：2026-10-15。

## 学习模块

- [输入预测（Composer Prediction）](输入预测模块.md)：如何根据当前会话生成下一条输入建议？已初始化。
