# MCP 服务知识图谱

> 地图版本：初版，2026-09-26。已核验官方规范修订，不代表用户已掌握；实操时按选定 SDK、客户端和固定提交更新。

## 1. 完整技术链路

```text
使用者表达目标
  → Host（宿主应用）整理对话、策略和可用能力
  → 模型基于 Host 提供的上下文决定是否提出 Tool Call
  → Host 的 MCP Client 按固定 MCP 版本连接/发现能力
  → MCP Server 校验协议契约、身份和调用参数
  → Server 的业务适配器调用下游 API / 数据库 / 文件 / 服务
  → 业务结果或错误沿 MCP 响应返回 Client
  → Host 检查结果、加入上下文，再交给模型继续或回答使用者
```

Resource 的入口通常由 Host 决定读取并选择如何放入上下文；Prompt 是 Server 提供可复用消息模板，Host 决定何时取用；三者共享 MCP 接入与权限环境，但不是同一种调用。

## 2. 问题与扩展方案

| 面对的问题 | 改变的环节与方案 | 对应概念/项目 | 深入入口 |
|---|---|---|---|
| 不知道模型、协议客户端和外部服务谁负责决策/执行 | 分清模型提出意图、Host 决定可用能力并编排、Client 传协议、Server 执行适配 | Host / Client / Server / Tool Calling | [名词清单](./名词清单.md)；[MCP 官方规范](./开源项目MCP服务设计/MCP官方规范与Schema.md) |
| 不同语言服务难接入 | 统一发现、调用和返回约定 | MCP 协议、官方 SDK | [TypeScript SDK](./开源项目MCP服务设计/MCP官方TypeScriptSDK.md)、[Python SDK](./开源项目MCP服务设计/MCP官方PythonSDK.md) |
| 不同数据/动作怎样暴露 | 选 Tool（动作）、Resource（可读数据）或 Prompt（模板） | Tools / Resources / Prompts | [s19 三能力实验](../../../s19_mcp_plugin/LEARNING_NOTES.md) |
| 本机工具与远程服务通信方式不同 | stdio 子进程，或 Streamable HTTP 远程请求/流 | Transport / 生命周期 | [FastMCP](./开源项目MCP服务设计/FastMCP.md)、[Docker MCP Gateway](./开源项目MCP服务设计/DockerMCPGateway.md) |
| 库封装掩盖线路行为 | 用 Inspector、Conformance Suite 和固定版本源码分层核对 | Debugger / conformance | [MCP Inspector](./开源项目MCP服务设计/MCPInspector.md)、[Conformance Suite](./开源项目MCP服务设计/MCPConformance.md) |
| 真实业务 API 有身份、范围和副作用 | 在 Server 与下游边界执行校验、授权、限速和错误映射 | GitHub / Atlassian / PostgreSQL Server | [项目矩阵](./开源项目MCP服务设计/子项目.md) |
| 多个 Server 难统一路由和治理 | 网关负责聚合、策略、认证与可观测性；仍须检查每个后端权限 | Docker Gateway / agentgateway | [网关比较](./开源项目MCP服务设计/子项目.md#三部署认证与治理网关) |
| 新版协议取消会话后仍要保留业务进度 | 用明确句柄、幂等键或外部持久状态表达应用状态 | MCP stateless protocol ≠ stateless business operation | [C-2026-017](../../../specs/changes/C-2026-017-build-useful-mcp-server.md) |

## 3. 概念关系

- **MCP 规范**定义线上互操作契约；官方 SDK 是该契约的实现工具，不是规范本身。
- **Tool Calling**是模型与 Host/Runtime 之间的应用行为；MCP `tools/call` 是 Client 与 Server 之间的协议调用。通常 Host 把模型提出的调用转成 MCP 请求，但模型不会自行建立 MCP 网络连接。
- **Host 包含或管理 MCP Client**；一个 Host 可有多个 Client/Server 连接。MCP Server 暴露能力并连接业务系统；Server 不等于业务数据库或 API。
- **2025-11-25 及更早的会话握手**与 **2026-07-28 的无协议会话模型**是不同版本路线，不是 TCP 短连/长连之分。新版每个请求携带版本元数据、用 `server/discover` 获取支持信息；应用自身仍可能保存业务状态。
- **Gateway 是可选部署/治理层**，可代理或汇聚 Client 与多个 Server。它不能代替下游对象级授权，也不自动使提示词和返回内容可信。
- 项目之间是规范—SDK—框架—应用 Server—治理网关的组成关系，不是逐代替代关系；Inspector 是观察工具，不能替代契约测试或安全验证。

## 4. 主线与选学扩展

**必学主线**：角色和信任边界 → 固定协议版本及协商 → JSON-RPC 与能力发现 → Tools / Resources / Prompts → stdio / Streamable HTTP → 工具 Schema、结果和错误 → 真实只读业务适配 → 目标客户端接入 → 按生产矩阵验收。

**选学扩展**：Subscriptions、multi-round-trip、长任务/取消恢复、OAuth 多租户、跨服务凭据代理、高可用和负载治理；只在目标场景触发时深入。任务卡的每项生产考量仍都要先评估是否适用。

## 5. 子笔记、Demo 与资料索引

- 术语入口：[名词清单](./名词清单.md)
- 项目路线：[开源项目对照](./开源项目MCP服务设计/子项目.md)
- 官方参考资料：[规范与 Schema](./开源项目MCP服务设计/MCP官方规范与Schema.md)
- 可选源码学习入口：TS SDK、Python SDK、FastMCP、MCP Inspector、MCP Conformance Suite、GitHub MCP Server、MCP Atlassian、Postgres MCP、Docker MCP Gateway、agentgateway，均在项目目录各有一份笔记。
- 已有教学/实验材料：[s19 README](../../../s19_mcp_plugin/README.md)、[s19 学习笔记](../../../s19_mcp_plugin/LEARNING_NOTES.md)、[Raw MCP Server](../../../s19_mcp_plugin/web_mcp_server_raw.py)、[SDK MCP Server](../../../s19_mcp_plugin/web_mcp_server_sdk.py)。这些已有材料不代表本 Change 的实验已运行。
