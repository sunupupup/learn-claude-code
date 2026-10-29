# Open Policy Agent（OPA）：通用策略决策

- **官方仓库**：[open-policy-agent/opa](https://github.com/open-policy-agent/opa)；[官方文档](https://www.openpolicyagent.org/docs/latest/)
- **用途/层次**：通用策略引擎 / PDP，可独立服务或嵌入应用周边；策略作者定义规则，业务服务查询决定并负责执行。
- **相关机制**：Rego、JSON input/data、allow/deny/decision document、bundles 与测试；本章可将 `principal/action/resource/context` 作为输入。
- **具体入口**：Getting Started → Rego language → Integrating OPA → Access control examples → Policy testing。
- **前置/难度/顺序**：理解 JSON、条件规则和服务端调用；中；作为外置策略服务路线的代表。
- **维护/许可证（2026-09-26）**：GitHub API 显示 Apache-2.0、最近推送 2026-09-26、latest release `v1.21.0`（2026-09-24）；OPA 是 CNCF graduated 项目。企业托管服务不是仓库本身。
- **优点**：规则可与应用代码分开维护；单一 PDP 可用于 API、部署、Agent Tool 等多个决策点。
- **局限/边界**：OPA 给决定但不强制工具执行器遵守；网络边界、输入可信度、策略发布与缓存一致性仍由接入方负责；Rego 初学门槛高于 Cedar 简单策略。
- **建议观察**：调用点将哪些可信数据传给 OPA；超时/不可达时是 fail closed 还是 fail open；策略版本如何出现在审计记录。



