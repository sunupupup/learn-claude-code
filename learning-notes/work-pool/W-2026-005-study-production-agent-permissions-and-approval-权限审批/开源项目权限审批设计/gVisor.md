# gVisor：用户态内核隔离

- **官方仓库**：[google/gvisor](https://github.com/google/gvisor)；[官方文档](https://gvisor.dev/docs/)；[Security model](https://gvisor.dev/docs/architecture_guide/security/)
- **用途/层次**：OCI `runsc` Sandbox Runtime，用用户态应用内核减少不可信容器直接暴露给宿主机内核的系统调用面。
- **相关机制**：Sentry/Gofer 结构、文件代理、host syscall 限制、OCI/Docker/Kubernetes 集成；这是授权后执行隔离层，不是策略或审批框架。
- **具体入口**：What is gVisor、Security model、Architecture guide、runsc user guide、OCI integration。
- **前置/难度/顺序**：Linux 容器、namespace/syscall 基础；高；结合 W-030 只挑一个实验后端。
- **维护/许可证（2026-09-26）**：GitHub API 显示仓库 SPDX Apache-2.0、最近推送 2026-09-26、latest release `release-20260921.0`（2026-09-23）；LICENSE 注明部分文件有其他许可声明，源码学习时要逐文件核。Google Cloud 的 GKE Sandbox/Cloud Run 是托管产品服务，不等同于仓库代码本身。
- **优点**：比“Docker 容器=安全沙箱”的直觉更准确地展示了宿主内核暴露面与 syscall 中介；官方安全文档明确列出 sandbox 可访问资源和 host 交互面。
- **局限/边界**：不能阻止业务层越权访问主动挂载给容器的数据；性能兼容、网络、文件挂载和平台内核条件需实测。官方采用方清单不能等同本地部署已安全。
- **建议观察**：executor 被授予的文件、网络、凭证是否最小化；关闭网络时能否 rootless；隔离不能回滚已经写入远端服务的副作用。



