# Restate（源码可见但受限的对照项）

- Runtime 仓库：[restatedev/restate](https://github.com/restatedev/restate)
- Python SDK：[restatedev/sdk-python](https://github.com/restatedev/sdk-python)
- 官方文档：[Python SDK](https://docs.restate.dev/develop/python)、[Durable Execution](https://docs.restate.dev/concepts/durable_execution)
- 本次查验：2026-09-26；Runtime `Cargo.toml` 标记 BUSL-1.1；Runtime LICENSE 明示其不是 Open Source license，并对 Public Restate Platform Service 有限制及版本对应的 change date。Python SDK 单独声明 MIT。使用/分发前应读 Runtime LICENSE 全文并按目标版本核验。
- 开源分类：Runtime **源码可见但受限，不计入 OSI 开源项目数量**；Python SDK MIT 开源。Restate 托管服务属于商业产品，不能混为一谈。
- 难度/顺序：D3，选学；只有在需要比较运行时日志/重放模型时阅读。

## 适合回答的问题

持久化调用 journal 如何让异步 handler 在故障恢复后复用已完成步骤？“不丢消息/不重复传递”与业务系统是否重复扣款是不同层次吗？

## 建议阅读入口

先读官方 Durable Execution 概念和 Python SDK Quickstart，再读 Runtime 许可证、服务 invocation/journal 与 idempotency-key 文档；关注 endpoint idempotency key 的保留语义与每个服务定义的事件处理，不直接把宣传中的 once/exactly-once 映射到外部业务系统。

## 前置、优势与局限

- 前置：async/await、事件驱动服务、持久工作流；对比 Temporal 后再看更合适。
- 优势：提供基于 durable journal 的另一种代码表达方式，值得比较事件驱动请求、服务之间通信和等待人工输入。
- 局限：Runtime BUSL 许可限制某些分发/托管服务使用；其 Python SDK MIT 不改变 Runtime 许可。必须将“公开源码”“OSI 开源”“商业托管”分开判断。

## 证据边界

本次直接核对官方 GitHub Runtime LICENSE、Runtime manifest 和 Python SDK 页面；具体某个 release 是否发生许可证变更应在深入时再次查看该版本的 LICENSE。
