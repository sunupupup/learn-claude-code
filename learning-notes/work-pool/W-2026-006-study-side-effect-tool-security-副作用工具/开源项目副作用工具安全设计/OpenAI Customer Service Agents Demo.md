# OpenAI Customer Service Agents Demo

- 仓库：[openai/openai-cs-agents-demo](https://github.com/openai/openai-cs-agents-demo)
- 维护者资料：[README](https://github.com/openai/openai-cs-agents-demo#readme)
- 本次查验：2026-09-26；GitHub 仓库公开，仓库声明 MIT。页面可访问且近期被抓取；没有据此推断其拥有稳定维护承诺。
- 开源分类：MIT 开源 Demo；不包含真实客服/订单产品。
- 难度/顺序：D1，推荐第 1 个。

## 适合回答的问题

客服流程中，Agent 如何分工调用订单/航班/补偿类工具？一个看起来真实的客服前端，哪些状态实际上只来自演示数据？

## 建议阅读入口

先读 README 的场景和 mock 数据说明，再从 `python-backend/` 找 Agent 定义、tools、server 路由；之后看 `ui/` 如何展示调用结果。启动前固定 commit；本次只是导航，未读取源码文件。

## 观察重点

- `cancel`、`book/rebook`、`issue_compensation` 等动作的输入输出和用户确认位置；
- 工具 handler 是如何操作 mock itinerary/state；结果是否有 operation/resource 凭证；
- 接口错误与模型可见结果之间如何映射；
- 把一次创建工单/补偿替换成“幂等写入 + 状态查询”的本地合成服务时，需要在哪一层改变。

## 前置、优势与局限

- 前置：知道 Python 函数可以注册为 Agent Tool；不需要先会分布式系统。
- 优势：业务流程直观，有前后端，便于给“查询/可逆/高风险写”分类。
- 局限：README 明确依赖 mock itineraries/演示工作流；不能把按钮、Agent 路由或演示结果当作生产鉴权、真实支付、事务、审计或故障恢复的证据。
- 推荐顺序：先用它建立场景词汇，然后读 Agents SDK 的审批机制；不要直接仿照其 mock handler 作为生产订单接口。

## 证据边界

已核验的是官方仓库入口、Demo 定位和 MIT 许可声明。业务行为细节必须在固定版本读取后标为 `source-verified`；本文件中的观察点仍属阅读计划。
