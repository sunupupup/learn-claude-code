# OpenFGA

- 仓库：[openfga/openfga](https://github.com/openfga/openfga)
- 官方文档：[Modeling guide](https://openfga.dev/docs/modeling)、[Getting started](https://openfga.dev/docs/modeling/getting-started)、[Production](https://openfga.dev/docs/getting-started/production)
- 本次查验：2026-09-26；GitHub 仓库声明 Apache-2.0；官方 `RELEASES.md` 说明维护者的版本与维护/安全更新流程，当前最新 release/tag 未在本轮结果中确认，正式源码学习时复核。
- 开源分类：Apache-2.0 开源授权服务；托管服务或部署包按单独条款核验。
- 难度/顺序：D2，授权窄对照（推荐路线第 6 个）。

## 适合回答的问题

“当前用户能不能对这个 order/ticket 执行 read/update？”如何用用户、对象和关系表示，而不是仅在 Agent prompt 里写一条规则？

## 建议阅读入口

读 Modeling Guide 与 Concepts 中 authorization model、relationship tuples、direct/implied relationship；然后看 HTTP/gRPC check API 与仓库的 model tests。构造合成关系如 `user:alice` 是 `order:123` 的 owner、`agent:helper` 只被授权读取派发给用户的资源。

## 前置、优势与局限

- 前置：基本身份/角色概念、关系表、API 服务端授权链；本任务 W-005 的主体/委托身份概念优先。
- 优势：聚焦细粒度的主体—资源关系，适合把“查自己的订单、客服操作被分配订单、Agent Scope 交集”写成可检查模型。
- 局限：OpenFGA 计算授权关系，不替业务 API 认证 caller、锁定业务状态、写数据库或落实决定；接入点和故障时 fail-closed 仍是应用责任。
- 与 OPA 对比：OpenFGA 的中心是关系图/对象模型；OPA 更通用地对结构化输入执行政策规则。初学者选其一即可。

## 证据边界

项目定位、文档入口和 Apache 许可来自官方仓库/文档；“被某些组织采用”不能单独证明本任务关注的具体授权语义安全。没有运行或审查生产部署。
