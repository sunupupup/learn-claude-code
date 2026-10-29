# Keycloak：用户身份认证与令牌

- **官方仓库**：[keycloak/keycloak](https://github.com/keycloak/keycloak)；[官方文档](https://www.keycloak.org/documentation)；[Authorization Services architecture](https://www.keycloak.org/docs/latest/authorization_services/index.html)
- **用途/层次**：开源 Identity and Access Management 服务，提供用户登录、OIDC/OAuth2/SAML 身份和令牌，也包含可选授权服务。
- **相关机制**：用户/客户端认证、令牌 claims、resource/scope/policy 与 PDP/PEP/PAP/PIP；本章主要用它解释“有用户令牌”不等于“本次 Agent 工具调用已授权”。
- **具体入口**：Getting Started、Server Administration、Securing Applications、Authorization Services Architecture。
- **前置/难度/顺序**：HTTP、OAuth2/OIDC 基本概念；中；先看身份和令牌，再看可选授权服务。
- **维护/许可证（2026-09-26）**：GitHub API 显示 Apache-2.0、最近推送 2026-09-26、latest release `26.7.4`（2026-09-16）。Red Hat build/support 属商业产品边界，不等于 Keycloak 源码受限。
- **优点**：适合真实说明人类用户认证、服务账号和 OIDC token 的边界；还能对照授权服务组件术语。
- **局限/边界**：通用 Agent 是否可被作为独立主体、代理令牌能否安全委派需由应用设计；不要把登录页或 JWT 签名校验误当作对资源的全套授权检查。
- **建议观察**：执行请求携带的 user subject、client/service account 和 Agent run 如何关联；权限撤销后已签发 token 的有效期与再次查询策略。



