# DBOS Transact

- 仓库：[dbos-inc/dbos-transact-py](https://github.com/dbos-inc/dbos-transact-py)
- 官方文档：[Python docs](https://docs.dbos.dev/python)、[Transactions & Datasources](https://docs.dbos.dev/python/tutorials/transaction-tutorial)
- 本次查验：2026-09-26；Python 包 metadata 声明 MIT，版本维护和近期 GitHub 提交可见；未在此固定版本。
- 开源分类：MIT 开源 Python 库；托管/平台能力需按各自许可另核，不由库许可推出。
- 难度/顺序：D2-D3，推荐第 5 个，作为 Temporal 后的窄架构对照。

## 适合回答的问题

如果把 durable workflow 状态放进应用所用的 Postgres，编程接口与独立 workflow 服务有何不同？数据库操作如何同持久执行记录关联？

## 建议阅读入口

读 Python Quickstart、workflow/step decorators、队列和 transaction/datasource tutorial；重点区分 framework 声称的 exactly-once step replay 和“对任意外部服务副作用保证 exactly-once”并不是一回事。若调用支付网关，仍需要稳定 idempotency key/状态核对。

## 前置、优势与局限

- 前置：Python 装饰器、SQL、事务、Postgres 基础。
- 优势：相比 Temporal 服务端部署模型，展示数据库后端持久工作流的另一条架构路线；包仓库本身 MIT。
- 局限：数据库事务与外部 HTTP 副作用边界仍需设计；本地可用不代表已经满足当前系统的规模/高可用/运维要求。
- 推荐顺序：读完 Temporal 的 Workflow/Activity 基本概念后，只比较状态后端、部署组件、恢复粒度和幂等责任。

## 证据边界

官方 DBOS 文档与仓库 pyproject 支持其 Postgres-backed Python durable workflow 定位和 MIT 许可；语义、事务保证和外部服务边界需在固定版本源码/测试中继续核实。
