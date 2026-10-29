# Kata Containers：以 microVM 加强容器隔离

- **官方仓库**：[kata-containers/kata-containers](https://github.com/kata-containers/kata-containers)；[Quick Start](https://github.com/kata-containers/kata-containers/blob/main/docs/quick-start-guide.md)；[Virtualization design](https://github.com/kata-containers/kata-containers/blob/main/docs/design/virtualization.md)
- **用途/层次**：OCI/CRI 兼容容器 Runtime，将 Pod/容器放进轻量 VM 和 guest kernel，提供比共享宿主内核更强的执行隔离。
- **相关机制**：containerd/CRI → Kata shim → hypervisor → guest VM → workload；文件、网络、资源通过虚拟设备映射。
- **具体入口**：Quick Start、Overview、Architecture/Virtualization、Hypervisor support、Limitations。
- **前置/难度/顺序**：容器、Linux、Kubernetes/虚拟化基础；高；与 gVisor 窄对照，或在有 KVM 设备的学习环境研究。
- **维护/许可证（2026-09-26）**：GitHub API 显示 Apache-2.0、最近推送 2026-09-25、latest release `4.2.0`（2026-09-15）；硬件/发行版支持矩阵仍要按部署环境重新确认。云服务可采用 Kata，但托管功能收费/支持另看。
- **优点**：VM 与容器的边界直观；官方 quickstart 清楚提示需硬件虚拟化，并强调 isolation 本身不等于完整多租户安全。
- **局限/边界**：启动/资源和兼容性成本高于普通容器；不管理 Agent Tool 授权，不限制已经显式挂载进去的数据，也无法撤销外部副作用。
- **建议观察**：guest kernel 与 host kernel 的隔离差别；共享目录/virtio 设备怎样重新形成边界；哪些风险仍需网络、存储和控制面额外防护。



