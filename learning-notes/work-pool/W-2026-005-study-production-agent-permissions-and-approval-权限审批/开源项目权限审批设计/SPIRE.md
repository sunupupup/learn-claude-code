# SPIRE：运行中工作负载身份

- **官方仓库**：[spiffe/spire](https://github.com/spiffe/spire)；[SPIFFE/SPIRE 官方文档](https://spiffe.io/docs/latest/spire-about/)
- **用途/层次**：SPIFFE 身份标准实现中的运行时基础设施，为服务/工作负载做身份验证与短期凭证签发；与 Keycloak 面向人类用户和应用登录的常见用途不同。
- **相关机制**：Workload API、节点/工作负载 Attestation、SPIFFE ID、SVID 轮换；可用于给 Agent executor 或工具服务分配独立身份。
- **具体入口**：SPIRE Concepts、Architecture、Workload API、Registration Entries、Quickstart。
- **前置/难度/顺序**：TLS/mTLS、容器/节点、服务身份；高；只有讨论多服务部署/短期身份时深入。
- **维护/许可证（2026-09-26）**：GitHub API 显示 Apache-2.0、最近推送 2026-09-24、latest release `v1.15.3`（2026-08-21）；SPIRE 为 CNCF graduated 项目。部署前仍需核安全公告和运行环境支持矩阵。
- **优点**：展示进程身份凭证可以短期、自动轮换而非把长期 API key 塞给 Agent；适合授予最小范围服务身份。
- **局限/边界**：身份真实性不等于资源授权；需要部署信任域、attestation 插件与运维基础设施。不能单靠 SPIRE 决定某个 Agent 是否可退款或删数据库记录。
- **建议观察**：哪个 executor workload 能领取什么身份；如何撤销或缩短证书有效期；Agent 的“代表用户”与自身 workload 身份如何同时审计。



