# SpiceDB：可扩展关系授权数据库

- **官方仓库**：[authzed/spicedb](https://github.com/authzed/spicedb)；[官方文档](https://authzed.com/docs/spicedb)
- **用途/层次**：关系型授权服务 / 权限数据与查询系统，受 Zanzibar 思路影响，面向复杂共享资源与分布式检查。
- **相关机制**：schema、relationship tuple、permission Check、dispatch/cache/consistency token；用于观察策略模型/关系数据与应用执行点如何协作。
- **具体入口**：Getting Started、Schema Language、Check API、Consistency、Security/Threat Model。
- **前置/难度/顺序**：建议先理解 OpenFGA 的主体-对象-关系模型；中高；它是 OpenFGA 的窄对照，不必两个都部署。
- **维护/许可证（2026-09-26）**：GitHub API 显示 Apache-2.0、最近推送 2026-09-24、latest release `v1.56.2`（2026-09-11）；LICENSE 正文为 Apache-2.0。Authzed Cloud 为独立托管服务。
- **优点**：能学习关系授权的可扩展数据服务、部署信任假设和一致性语义；官方 threat model 明确说明部署方负责网络、凭证与 API 边界。
- **局限/边界**：仅用当前 `main` 文档不足以定产品许可证或生产适配；关系授权模型错误也会直接变成授权漏洞；不处理 Agent 审批、凭证签发或沙箱。
- **建议观察**：一致性 token 如何保护关系变更后的读取；权限服务错误时 PEP 的拒绝策略；trace 不要泄露 secrets。


