# MCP Conformance Suite

## 项目资料

- 仓库：[modelcontextprotocol/conformance](https://github.com/modelcontextprotocol/conformance)
- 官方运行说明：[README](https://github.com/modelcontextprotocol/conformance#readme)、[Requirements 文件](https://github.com/modelcontextprotocol/conformance/tree/main/requirements)
- 分类：官方 MCP 协议契约/一致性测试工具，源码公开；覆盖 Client 和 Server。它不是业务功能测试器、Inspector UI 或安全扫描器。
- 维护/版本：官方 SDK 的 CI 会使用它，仓库当前持续开发；本次未找到可以安心固定的 GA 工具版本。官方 [issue #426](https://github.com/modelcontextprotocol/conformance/issues/426) 曾指出当时 `main` 落后于 `2026-07-28` 最终版并错误归类 revision；截至 2026-09-26 是否完全修复尚未确认。因此开始时要固定 commit 和 requirement 文件，并核对它们与 final spec 对齐，不能只凭 `main` 的绿色结果宣称符合性。
- 许可证：MCP 官方组织许可证迁移期，新贡献 Apache-2.0，部分既有 MIT，通用文档 CC-BY-4.0；检查固定文件/提交。

## 能回答的问题

Client 是否按指定版本发出正确的协议消息？Server 是否正确响应固定版请求？哪些测试是该规范 revision 的必需项，哪些是可选扩展或后来新增？这把“看起来能连”提升为按协议版本执行的可重复合同检查。

## 建议阅读与固定

1. 仓库 README 的 client/server 运行流程与报告格式；
2. `requirements/2025-11-25.yaml`、`requirements/2026-07-28.yaml` 和被引用 scenario；
3. `src/` 的启动器、测试 fixture、wire capture/check；
4. 仓库 issue/release 中 final spec requirement 对齐问题；
5. 最终选用时记录工具 tag/commit、conformance npm 包版本、需求文件 hash 和执行客户端/Server 版本。

## 前置与难度

需会读 JSON-RPC 和客户端/服务端请求轨迹。难度中。推荐在首个 SDK 运行后使用，按实际选定的 2026 revision 固定要求集。

## 优点、局限与状态

优点是两端黑盒协议互操作检查，并通过冻结 requirement set 避免新加入场景倒灌到旧版本验收。局限是实现/测试工具自身也可能滞后规范；通过 conformance 不证明业务授权正确、凭据安全、错误恢复良好、模型成功使用工具或满足 SLO。项目公开源码，license 混合迁移；维护活跃但 revision 对齐需要特别核验。核验日期 2026-09-26。
