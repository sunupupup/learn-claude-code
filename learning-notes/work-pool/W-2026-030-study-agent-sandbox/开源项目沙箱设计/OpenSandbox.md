# OpenSandbox：沙箱学习候选

- 定位：主项目：从 SDK 到执行环境的完整链路。
- 状态：推荐/选题阶段，尚未启动源码学习。
- 核验日期：2026-09-26。
- [官方仓库](https://github.com/opensandbox-group/OpenSandbox)；默认分支 main；GitHub 元数据显示未归档，最近推送日期 2026-09-26。
- 仓库声明许可证：Apache-2.0；正式进入源码阅读时还需核对选定 Commit 的 LICENSE 及相关组件许可。
- 当前证据：官方 README/架构说明与在线目录检查；未逐函数追踪、未运行、未作生产验证。正式学习用 Commit、版本与本地目录均待选定。
- [返回专题大纲](子项目.md)

## 项目简介

通用 Agent 沙箱平台，包含多语言 SDK、生命周期服务、Docker/Kubernetes 后端，以及沙箱内的 execd 执行服务。旧 alibaba/OpenSandbox 链接已指向 opensandbox-group/OpenSandbox；应采用当前规范仓库地址。

## 适合回答的学习问题

- SDK 的 create 到底创建了哪些资源，怎样知道环境已就绪？
- 执行命令与创建沙箱是否走同一个服务？
- 代码、文件、Shell 与 Jupyter 执行上下文怎样连接？
- 超时、主动删除、部分创建失败时，由谁回收资源？
- 网络策略在哪里落实，资源限制与底层隔离分别由谁承担？

## 推荐观察入口

以下是已经检查的在线目录或文档入口；链接随默认分支变化，正式阅读后替换为固定 Commit 的证据链接。

- [架构总览：docs/architecture/index.md](https://github.com/opensandbox-group/OpenSandbox/blob/main/docs/architecture/index.md)
- [Python SDK：sdks/sandbox/python](https://github.com/opensandbox-group/OpenSandbox/tree/main/sdks/sandbox/python)
- [生命周期服务：server/opensandbox_server](https://github.com/opensandbox-group/OpenSandbox/tree/main/server/opensandbox_server)
- [沙箱执行服务：components/execd](https://github.com/opensandbox-group/OpenSandbox/tree/main/components/execd)
- [网络出口组件：components/egress](https://github.com/opensandbox-group/OpenSandbox/tree/main/components/egress)
- [协议定义：specs](https://github.com/opensandbox-group/OpenSandbox/tree/main/specs)
- [测试：server/tests](https://github.com/opensandbox-group/OpenSandbox/tree/main/server/tests)

## 首轮范围

先只读 Python SDK → 生命周期服务 → Docker 后端 → execd 的命令执行，文件读写作为相邻路径。这里是待追踪的阅读路线，不是已核验的逐函数调用链；正式阅读时应分开生命周期路径和实际执行路径。第二轮才进入网络出口；Kubernetes、微型虚拟机、快照与大规模调度暂缓。

## 边界与待核验事项

它同时包含管理层与执行层，比只暴露客户端的项目更适合回答当前问题。但默认 Docker 后端的隔离边界不能代表所有可选安全运行时；不能据此推断阿里云 FC 使用相同实现。

## 后续小实验候选

最小观察目标：创建一个沙箱，写入固定文本，执行脚本读回文本，获取输出，再删除。失败对照选择命令超时或禁止目标访问之一；只有日志和资源状态核验后才写运行结论。

