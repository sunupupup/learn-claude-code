# Zammad

- 仓库：[zammad/zammad](https://github.com/zammad/zammad)
- 官方资料：[README](https://github.com/zammad/zammad#readme)、[Developer Manual](https://docs.zammad.org/en/latest/)、[REST API](https://docs.zammad.org/en/latest/api/intro.html)
- 本次查验：2026-09-26；GitHub repo 声明 AGPL-3.0，官方说明全产品源码开放；官方 GitHub Packages 显示 7.1.2 系列镜像仍在发布（页面最近显示约数小时前）。这是镜像 tag 的活动信号，不替代固定源码 tag/commit。
- 开源分类：AGPLv3 开源完整工单产品；云托管是商业服务，部署/网络提供服务时需理解 AGPL 条件。
- 难度/顺序：D2-D3，推荐第 8 个，适合工单领域学习。

## 适合回答的问题

真实工单系统如何表达 ticket 生命周期、用户/客服/组织权限、创建/更新 API 和相关业务副作用？Agent 创建动作需要依赖哪个 server-side identity 与资源规则？

## 建议阅读入口

先读官方 REST API 认证与 ticket endpoints，再沿源码找 controller/API policy、模型验证、ticket/article 写入、通知/自动化/审计相关路径。重点挑一个“创建工单”，不要初学时展开所有渠道集成。

## 前置、优势与局限

- 前置：HTTP REST、JSON、数据库记录、工单状态；Ruby on Rails 是选学代码阅读背景。
- 优势：完整业务产品，比教学 demo 更能看到真实领域对象、状态和权限入口；可回答“Agent 适配已有业务系统要尊重什么”。
- 局限：产品源码复杂且 AGPL 有使用/修改/网络服务义务；不属于 Agent 框架，也没有资料证明把 API 暴露给模型后自然安全。该应用的权限仍要与 Agent 委托身份和幂等策略集成。
- 推荐顺序：完成 `create_ticket` 幂等模型后再读一个 controller/service path；只静态阅读，不连接实例。

## 证据边界

官方 repo 和官网确认产品定位、开源声明与 API 文档入口；当前只读导航，不推断每个 API 端点具体鉴权规则或部署配置。
