# gVisor：沙箱学习候选

- 定位：进阶：用户态内核隔离。
- 状态：推荐/选题阶段，尚未启动源码学习。
- 核验日期：2026-09-26。
- [官方仓库](https://github.com/google/gvisor)；默认分支 master；GitHub 元数据显示未归档，最近推送日期 2026-09-26。
- 仓库声明许可证：Apache-2.0；正式进入源码阅读时还需核对选定 Commit 的 LICENSE 及相关组件许可。
- 当前证据：官方 README/架构说明与在线目录检查；未逐函数追踪、未运行、未作生产验证。正式学习用 Commit、版本与本地目录均待选定。
- [返回专题大纲](子项目.md)

## 项目简介

操作系统执行层的应用内核，以用户态实现 Linux 类接口，并提供 runsc 容器运行时。它不是 Agent SDK，也不是普通意义的虚拟机。

## 适合回答的学习问题

- 应用为什么不直接把所有系统调用交给宿主内核？
- 用户态内核怎样缩小应用直接触达宿主内核的范围？
- 更强隔离为什么可能带来系统调用兼容和性能取舍？

## 推荐观察入口

以下是已经检查的在线目录或文档入口；链接随默认分支变化，正式阅读后替换为固定 Commit 的证据链接。

- [项目与边界：README.md](https://github.com/google/gvisor/blob/master/README.md)
- [运行时入口：runsc](https://github.com/google/gvisor/tree/master/runsc)
- [内核相关实现：pkg](https://github.com/google/gvisor/tree/master/pkg)
- [技术文档：g3doc](https://github.com/google/gvisor/tree/master/g3doc)

## 首轮范围

先读官方架构 https://gvisor.dev/docs/ ，理解应用、Sentry（应用内核）、宿主内核的关系，再挑一个文件操作追踪。先修是进程、系统调用和容器，当前不进入整套内核源码。

## 边界与待核验事项

理解控制面/数据面后再选学。它可作为上层平台的执行后端，不与 OpenSandbox 构成同层替代；仍要控制暴露的数据与网络。

## 后续小实验候选

未来只比较一个系统调用或文件访问在普通容器与 gVisor 下的行为；运行环境、内核和兼容性先核对，暂不安装。

