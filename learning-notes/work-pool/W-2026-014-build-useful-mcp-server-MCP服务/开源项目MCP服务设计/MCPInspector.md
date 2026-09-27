# MCP Inspector

## 项目资料

- 仓库：[modelcontextprotocol/inspector](https://github.com/modelcontextprotocol/inspector)
- 文档：[官方 README 与运行说明](https://github.com/modelcontextprotocol/inspector#readme)、[Releases](https://github.com/modelcontextprotocol/inspector/releases)
- 分类：官方 MCP 开发/调试应用，源码公开；不是 Server SDK，也不是协议符合性或安全审计的替代品。
- 维护/版本：截至 2026-09-26，最新可见版本 2.8.0 于 9/23 发布，仓库持续更新；新规范适配事项仍可见于文档/开发路线。
- 许可证：许可证正在迁移。package manifest 仍显示 MIT；repo LICENSE 说明新贡献/获授权内容转 Apache-2.0、部分原贡献保留 MIT、一般文档 CC-BY-4.0。分发时逐文件检查，不能用单一标签概括整个仓库。

## 能回答的问题

不写 Host 就能否启动 Server、查看发现出的 Tools/Resources/Prompts、手动构造参数并观察结果/错误？Server transport 是否能连通？它能帮助区分协议连接问题与 Agent 选工具问题。

## 建议阅读与使用

先读启动方式与安全说明；观察 `clients/` 的 transport/client 页面如何构造请求；查看 v2 新协议影响记录和 release notes；只用本地无凭据测试服务，手工验证参数校验与错误结果。

## 前置与难度

不要求先掌握 TS，但需理解 Server endpoint 和基本 MCP 能力。难度低。推荐作为第一个观察工具；本轮不安装或启动它。

## 优点、局限与状态

优点是把抽象的发现/调用变成可见 UI 和请求面板。局限是 UI 点通不等于模型会正确选择工具，也不证明认证授权正确、版本全部兼容或生产安全。2026-09-23 新 release 表明活跃维护；混合许可证状态须再核。
