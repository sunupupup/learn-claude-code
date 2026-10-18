# E2B Runtime：沙箱学习候选

- 定位：窄对照：SDK 请求如何进入沙箱内的 envd。
- 状态：推荐/选题阶段，尚未启动源码学习。
- 核验日期：2026-09-26。
- [官方仓库](https://github.com/e2b-dev/runtime)；默认分支 main；GitHub 元数据显示未归档，最近推送日期 2026-09-25。
- 仓库声明许可证：Apache-2.0；正式进入源码阅读时还需核对选定 Commit 的 LICENSE 及相关组件许可。
- 当前证据：官方 README/架构说明与在线目录检查；未逐函数追踪、未运行、未作生产验证。正式学习用 Commit、版本与本地目录均待选定。
- [返回专题大纲](子项目.md)

## 项目简介

提供 E2B 沙箱后端，包括控制面 API、节点编排器、Firecracker 微型虚拟机及沙箱内 envd。GitHub API 核验：旧 e2b-dev/infra 地址现在重定向到 e2b-dev/runtime；旧索引中“只支持云部署”的摘要不能替代当前 README。

## 适合回答的学习问题

- envd 如何把 SDK 请求变成进程操作和文件操作？
- 输出、退出、交互式终端与取消分别怎样表示？
- SDK 重连的是服务连接、进程，还是整个执行环境？
- 为什么创建、命令执行和暂停恢复属于不同路径？

## 推荐观察入口

以下是已经检查的在线目录或文档入口；链接随默认分支变化，正式阅读后替换为固定 Commit 的证据链接。

- [架构：docs/ARCHITECTURE.md](https://github.com/e2b-dev/runtime/blob/main/docs/ARCHITECTURE.md)
- [envd 入口：packages/envd/main.go](https://github.com/e2b-dev/runtime/blob/main/packages/envd/main.go)
- [envd 文档与协议：packages/envd](https://github.com/e2b-dev/runtime/tree/main/packages/envd)
- [控制面 API：packages/api](https://github.com/e2b-dev/runtime/tree/main/packages/api)
- [节点编排器：packages/orchestrator](https://github.com/e2b-dev/runtime/tree/main/packages/orchestrator)
- [单机评估包：embed](https://github.com/e2b-dev/runtime/tree/main/embed)

## 首轮范围

第一轮只比较 envd 与 OpenSandbox execd 的进程/文件接口，必要时补读 https://github.com/e2b-dev/E2B 中对应 SDK。完整控制面、模板快照、内存按需加载与调度放到进阶，不部署完整平台来理解一次命令执行。

## 边界与待核验事项

FC 兼容 E2B 接口，只能支持接口层对照，不能证明 FC 使用 E2B 的 Firecracker 或服务端源码。当前 README 提供 Linux/KVM 单机 Embed 评估路径，并明确其不是生产部署模式；本机能否满足运行条件尚未检查。

## 后续小实验候选

可在后续隔离环境中单独运行 envd，比较同一个输出/取消案例；这种组件实验不能证明虚拟机隔离。完整 Runtime 实验另行检查 Linux/KVM、资源需求和版本。

