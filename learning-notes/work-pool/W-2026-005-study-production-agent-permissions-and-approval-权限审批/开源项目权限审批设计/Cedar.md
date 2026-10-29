# Cedar：类型化授权策略语言

- **官方仓库**：[cedar-policy/cedar](https://github.com/cedar-policy/cedar)；[官方文档](https://docs.cedarpolicy.com/)
- **用途/层次**：面向授权的策略语言与引擎；应用提出 principal/action/resource/context 请求，授权器返回 permit/forbid。
- **相关机制**：RBAC/ABAC 风格策略、schema 校验、策略测试、验证/分析工具；适合作为用户审批之后仍然需要的独立授权判定。
- **具体入口**：Getting Started、Policies、Authorization Requests、Schemas、Policy validation/testing。
- **前置/难度/顺序**：基础主体/资源/动作建模；中；默认作为 Agent HITL 流程的窄策略对照。
- **维护/许可证（2026-09-26）**：GitHub API 显示 Apache-2.0、最近推送 2026-09-25、latest release `cedar-policy-cli-v4.13.0`（2026-09-15）；仓库同时包含 Rust crates 和工具。外部托管授权产品各自定价和功能需单独看。
- **优点**：策略模型明确，能把规则从业务代码分离；Schema 有助于发现策略错误，策略与审批职责容易对照讲清楚。
- **局限/边界**：本身不提供用户身份认证、关系数据库、审批队列或运行时隔离；接入应用必须提供可信实体和动作上下文。
- **建议观察**：同一个高风险 `delete` 请求怎样由策略直接 deny、条件允许或交由 HITL ask；验证 schema 如何约束错误 policy。



