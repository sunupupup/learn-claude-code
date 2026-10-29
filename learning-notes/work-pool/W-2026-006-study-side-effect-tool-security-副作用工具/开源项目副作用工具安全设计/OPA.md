# Open Policy Agent（OPA）

- 仓库：[open-policy-agent/opa](https://github.com/open-policy-agent/opa)
- 官方资料：[OPA docs](https://www.openpolicyagent.org/docs)、[Policy language Rego](https://www.openpolicyagent.org/docs/policy-language)、[Access control examples](https://www.openpolicyagent.org/docs/comparisons/access-control-systems)
- 本次查验：2026-09-26；仓库 Apache-2.0；Releases 页面显示 v1.21.0 于 2026-09-24 发布，社区项目活跃。
- 开源分类：Apache-2.0 开源通用策略引擎；托管/商业分发若使用，分别核验。
- 难度/顺序：D2-D3，选学授权路线（推荐矩阵第 7 个，与 OpenFGA 二选一）。

## 适合回答的问题

工具请求的 caller、用户、租户、resource、action、金额、审批状态和环境，怎样作为结构化输入由策略返回 allow/deny？谁执行 deny？

## 建议阅读入口

从 “What is OPA” 与 Rego policy language 开始，运行 access-control example；再看 REST API / policy deployment 与 decision logging 文档。可建立只读查询和创建工单不同政策，随后说明服务端如何强制落实并如何处理 OPA 不可用。

## 前置、优势与局限

- 前置：JSON 数据结构、条件判断、API 中授权逻辑的常见写法；需知道 PDP/PEP 区别。
- 优势：决策与业务代码分离，策略输入输出显式，便于确定性测试与版本化。
- 局限：OPA 是 policy decision 组件；不会天然认证调用者、知道最新订单状态、保护 DB 写入或提供人工审批。调用服务必须是 PEP，且对策略不可用时选择安全失败策略。
- 与 OpenFGA 对比：OPA 可描述宽泛的属性/条件策略，OpenFGA 更直接表达主体与资源关系；可组合但本轮不需要同时部署。

## 证据边界

官方文档和 GitHub release/license 信息于 2026-09-26 核验；候选建议不构成本地策略执行证据。
