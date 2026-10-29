# OpenFGA：关系型授权检查

- **官方仓库**：[openfga/openfga](https://github.com/openfga/openfga)；[官方文档](https://openfga.dev/docs)；[Model testing](https://openfga.dev/docs/modeling/testing)
- **用途/层次**：集中式细粒度 Authorization Service，以模型和关系事实回答“某主体是否对某对象有某关系”。
- **相关机制**：Authorization Model、relationship tuples、`Check` API、模型测试；适合团队/项目/文档资源和委派关系。
- **具体入口**：官方 Concepts → Modeling → Direct access/parent-child → Check → Testing。
- **前置/难度/顺序**：理解用户、对象、关系三元组；中；关系授权路线首选，先文档模型测试。
- **维护/许可证（2026-09-26）**：GitHub API 显示 Apache-2.0、最近推送 2026-09-24、latest release `v1.21.0`（2026-09-20）。官方托管 OpenFGA 服务是另一个服务边界；固定版本仍核传递依赖和安全公告。
- **优点**：关系与授权模型分离；官方 CLI 支持对 tuples、check 和 list_objects 期望结果做模型测试。
- **局限/边界**：不能代替身份认证、条件策略所有能力或 Agent 审批；每次 Tool 调用仍要在真正副作用入口检查，并正确划分 tenant/store 与模型版本。
- **建议观察**：Agent 是 principal 还是以用户委派主体检查；模型更新和 relationship tuple 更改如何影响已排队审批；store/tenant 隔离如何验证。
- **Context7**：已解析 `/openfga/openfga` 并查询官方 Check / authorization model 文档，2026-09-26。



