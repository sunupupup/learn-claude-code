# Saleor

- 仓库：[saleor/saleor](https://github.com/saleor/saleor)
- 官方资料：[Saleor docs](https://docs.saleor.io/)、[GraphQL API reference](https://docs.saleor.io/api-reference)、[License](https://github.com/saleor/saleor/blob/main/LICENSE)
- 本次查验：2026-09-26；BSD 3-Clause；GitHub Releases 显示 3.23.36 于 2026-09-24 发布，支持分支与 security advisories 可见。启动源码阅读需选择 tag/commit，关注该日期之后的更新。
- 开源分类：BSD-3-Clause 开源核心电商应用；Saleor Cloud 等托管/服务产品单独核验，不能由仓库许可推断。
- 难度/顺序：D3，推荐第 9 个，作为订单/结账领域应用样本。

## 适合回答的问题

Cart/Checkout 如何进入订单？下单前后价格、库存、地址与支付状态由哪个业务层验证？Agent 的“代用户下单”为什么需要准备报价和独立提交动作？

## 建议阅读入口

从 GraphQL API 的 checkout/order mutations 和官方 checkout/order guides 入手，再找 resolver/service/domain 层对应实现和测试。对照 prepare/confirm/submit 的本章安全切分；不要触发真实支付。可以检查订单状态变化、并发库存与支付 webhooks 的边界。

## 前置、优势与局限

- 前置：GraphQL 基础、购物车/结账/订单领域对象、事务与状态机概念。
- 优势：真实电商核心代码，能把抽象 Tool 安全落到报价、库存、支付和订单生命周期。
- 局限：大型产品难度高，不适合第一份源码；公开有安全公告是维护/修复流程证据，不等于没有漏洞或自动证明安全。Agent 应通过受限业务 API，而不是绕过领域规则直接改库。
- 推荐顺序：先完成查询/工单与幂等基础，再挑一条 checkout→order 主路径阅读。

## 证据边界

官方 release、LICENSE 和 security 页核验到当前版本/许可证/持续维护信号；具体 GraphQL mutation 语义与事务细节应固定 3.23.x 具体 tag 后再核实。
