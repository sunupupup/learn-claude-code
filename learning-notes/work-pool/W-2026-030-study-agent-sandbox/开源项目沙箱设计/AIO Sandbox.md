# AIO Sandbox：沙箱学习候选

- 定位：体验补充：沙箱里面到底有哪些工具。
- 状态：推荐/选题阶段，尚未启动源码学习。
- 核验日期：2026-09-26。
- [官方仓库](https://github.com/agent-infra/sandbox)；默认分支 main；GitHub 元数据显示未归档，最近推送日期 2026-09-14。
- 仓库声明许可证：Apache-2.0；正式进入源码阅读时还需核对选定 Commit 的 LICENSE 及相关组件许可。
- 当前证据：官方 README/架构说明与在线目录检查；未逐函数追踪、未运行、未作生产验证。正式学习用 Commit、版本与本地目录均待选定。
- [返回专题大纲](子项目.md)

## 项目简介

All-in-One Sandbox 把浏览器、Shell、文件、Jupyter、MCP 和编辑器等能力组合在容器环境中。适合认识工具共享文件的业务流程，以及 SDK/API 如何描述操作。

## 适合回答的学习问题

- 浏览器下载的文件怎样接着交给 Shell 或 Python？
- 文件、浏览器、终端和编辑器如何访问同一个环境？
- SDK 对接的是已有服务还是负责创建实例？
- 哪些能力来自镜像，哪些来自公开仓库中的代码？

## 推荐观察入口

以下是已经检查的在线目录或文档入口；链接随默认分支变化，正式阅读后替换为固定 Commit 的证据链接。

- [项目说明：README.md](https://github.com/agent-infra/sandbox/blob/main/README.md)
- [客户端源码：sdk](https://github.com/agent-infra/sandbox/tree/main/sdk)
- [示例：examples](https://github.com/agent-infra/sandbox/tree/main/examples)
- [环境编排示例：docker-compose.yaml](https://github.com/agent-infra/sandbox/blob/main/docker-compose.yaml)
- [贡献说明：CONTRIBUTING.md](https://github.com/agent-infra/sandbox/blob/main/CONTRIBUTING.md)
- [镜像目录现状：docker](https://github.com/agent-infra/sandbox/tree/main/docker)

## 首轮范围

先看环境/API 清单与一个文件协作示例，再看 sdk 的请求封装；作为产品体验补充，不安排完整服务端调用链主课。

## 边界与待核验事项

2026-09-26 检查当前仓库目录：docker/ 只有 .gitkeep，CONTRIBUTING 主要描述 SDK。尚未确认完整运行镜像服务端实现的公开位置，因此不把“有镜像可运行”视为“完整内部实现可读”。README 快速启动使用 seccomp=unconfined，会放宽系统调用过滤，不应直接作为生产隔离配置。

## 后续小实验候选

后续若体验：固定镜像版本/摘要，在专用实验环境观察“浏览器产物 → 文件 API → Shell”的共享文件路径；无需先跑大模型。当前没有拉取或启动镜像。

