# Firecracker：沙箱学习候选

- 定位：进阶：microVM 的创建与隔离。
- 状态：推荐/选题阶段，尚未启动源码学习。
- 核验日期：2026-09-26。
- [官方仓库](https://github.com/firecracker-microvm/firecracker)；默认分支 main；GitHub 元数据显示未归档，最近推送日期 2026-09-25。
- 仓库声明许可证：Apache-2.0；正式进入源码阅读时还需核对选定 Commit 的 LICENSE 及相关组件许可。
- 当前证据：官方 README/架构说明与在线目录检查；未逐函数追踪、未运行、未作生产验证。正式学习用 Commit、版本与本地目录均待选定。
- [返回专题大纲](子项目.md)

## 项目简介

基于 Linux KVM 的轻量虚拟机监控器（VMM，Virtual Machine Monitor），用于管理 microVM。它提供机器、磁盘、网络等虚拟化能力，不直接提供 Agent 的文件和代码执行 SDK。

## 适合回答的学习问题

- 创建微型虚拟机需要客体内核、根文件系统和哪些配置？
- 运行时怎样启动、管理和限制一台 microVM？
- 快照保存什么，上层平台为何仍需要 envd 一类服务？
- 隔离机制与宿主系统配置各自负责什么？

## 推荐观察入口

以下是已经检查的在线目录或文档入口；链接随默认分支变化，正式阅读后替换为固定 Commit 的证据链接。

- [概述与边界：README.md](https://github.com/firecracker-microvm/firecracker/blob/main/README.md)
- [设计与运行说明：docs](https://github.com/firecracker-microvm/firecracker/tree/main/docs)
- [实现：src](https://github.com/firecracker-microvm/firecracker/tree/main/src)
- [测试：tests](https://github.com/firecracker-microvm/firecracker/tree/main/tests)

## 首轮范围

先画宿主内核/KVM → VMM → 客体内核 → 客体进程的分层，再读一个创建或快照路径。与 E2B Runtime 的编排层连接学习，不从虚拟设备实现开始。

## 边界与待核验事项

完整运行需要合适的 Linux/KVM 环境；Windows 主机不代表现成具备实验条件。官方明确安全性依赖宿主正确配置，不能把 microVM 当作无条件安全保证。

## 后续小实验候选

以后固定版本验证一次启动与停止，或快照恢复；不预先展开虚拟设备、性能调优和集群运维。

