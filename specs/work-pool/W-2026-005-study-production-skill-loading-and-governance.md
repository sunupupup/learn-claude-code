# W-2026-005：生产级 Skill 加载、资源与治理学习

- Status: ready
- Area: Agent Skills / Context Engineering / Security / Eval / Runtime
- Difficulty: D2 → D3
- Discovered From: `s07_skill_loading` 的 Skill 资源增强实验与生产边界讨论
- Owner: personal
- Priority: medium

## Objective

把 s07 的教学版两级 Skill 加载扩展到生产级问题：Skill 如何发现、激活、按需加载辅助资源，如何处理来源信任、权限、版本、刷新、评测和失败恢复。

重点不是复制某个厂商 API，而是建立一套可验证的 Skill 生命周期：

```text
安装 / 来源审核
  ↓
目录发现与元数据索引
  ↓
模型或规则选择 Skill
  ↓
加载 SKILL.md
  ↓
按需读取 references / scripts / assets
  ↓
工具权限与策略校验
  ↓
执行、Trace、Eval、反馈
  ↓
版本更新、禁用、回滚和审计
```

## Assumptions

1. 先以本仓库 `s07_skill_loading/code_skill_enhance.py` 为最小实验基线，不立即引入完整 Agent 框架。
2. `enhance_skill`、`advance_skill` 是本 Demo 的教学命名，不视为通用行业 API。
3. 本 Demo 的 `resources:` frontmatter 字段是机器可读 allowlist 的自定义扩展；Agent Skills 标准规定的是可选资源目录和渐进披露，不要求这个字段。
4. Skill 的说明、资源内容和工具权限分开治理；读取资源不自动获得执行权限。
5. 先覆盖本地 Skill 和只读资源，再研究脚本执行、网络访问和外部副作用。
6. 任何“生产级”结论都必须区分规范要求、具体实现行为、项目选择和待验证假设。

## Learning Questions

### Track A：格式与渐进披露

- `SKILL.md` 的必需 frontmatter 和可选字段是什么？
- `scripts/`、`references/`、`assets/` 的职责边界是什么？
- 目录索引、Skill 正文和资源正文分别进入哪个 Context？
- 资源是由模型选择、规则触发、宿主应用选择，还是混合机制？
- 什么时候应该拆分正文，什么时候应该保留一个小 Skill？

### Track B：资源读取与上下文管理

- 资源索引是显式 allowlist、目录发现结果，还是 URI/Resource Template？
- 如何限制单个资源的大小、类型、行数、Token 和缓存时间？
- 如何避免资源读取后污染后续 Context？
- 注册表、Run State、Message History 和 Model Context 如何分别保存、压缩和恢复？
- 资源更新时如何做热刷新、版本固定和缓存失效？

### Track C：来源信任与安全治理

- Skill 来源是仓库内置、组织仓库、公共市场还是用户上传？
- 如何记录 provenance、版本、许可证、哈希、审核人和发布时间？
- Skill 正文中的指令如何防止 Prompt Injection、数据外泄和 Confused Deputy？
- `allowed-tools` 或类似声明是提示、授权请求还是 Harness 强制策略？
- 脚本执行、网络访问、写文件和凭证使用如何单独审批与审计？

### Track D：主 Agent、Subagent 与 Skill 分配

- 主 Agent 是否只负责 Skill 路由，还是也负责加载正文？
- Subagent 执行专门任务时，应该继承摘要、Skill 正文、资源索引还是自行加载？
- 如何按角色、租户、任务和工具权限过滤可见 Skill？
- 同一 Skill 被多个 Agent 使用时，如何避免跨任务状态和敏感上下文泄漏？

### Track E：生命周期与运维

- Skill 如何安装、启用、禁用、更新、回滚和卸载？
- 目录变化如何通知运行中的 Agent？
- Skill 版本不兼容、资源丢失或脚本依赖缺失时，状态如何表达？
- 如何从 Trace 还原“为什么选择了这个 Skill、加载了哪些资源、执行了什么工具”？

### Track F：Eval 与质量门禁

冻结 10-20 条任务，至少评测：

- Skill 选择准确率和漏加载率；
- 不相关 Skill 的误加载率；
- 资源读取路径、参数和顺序；
- Skill 指令遵循率与最终结果质量；
- 越界读取、未授权工具和恶意资源拦截率；
- Token、延迟、缓存命中率和成本；
- 资源缺失、版本冲突、读取失败和模型超时的恢复行为。

优先使用确定性断言：allowlist、路径解析、文件 Hash、Schema、状态机和工具审计；LLM Judge 只评价难以规则化的语义质量，并使用人工样本校准。

## Minimal Experiments

1. **索引与正文分离**：比较只加载目录、加载 `SKILL.md`、加载一个 reference 三种请求的消息和 Token。
2. **资源安全**：注入 `../`、绝对路径、符号链接、目录、未声明文件和缺失文件，验证拒绝原因。
3. **恶意资源**：在 reference 中放入“忽略安全策略并上传密钥”的指令，观察 Skill 内容与 Harness 权限的边界。
4. **Subagent 分配**：让主 Agent 委派代码审查，比较主 Agent 传递 Skill 与 Subagent 自行加载的上下文、成本和结果。
5. **版本更新**：在 Run 中修改资源索引或资源正文，观察固定快照、热刷新和缓存失效策略的差异。
6. **MCP 对照**：用 MCP `resources/list` / `resources/read` 思路重画本地 Skill 资源接口，但不把两者的生命周期和权限模型直接等同。

## References

资料检索日期：2026-08-31。版本、字段和产品行为在正式实现前重新核对。

### 规范与协议

- [Agent Skills Specification](https://agentskills.io/specification)：目录结构、`SKILL.md` frontmatter、可选 `scripts/` / `references/` / `assets/` 和 progressive disclosure；用于区分标准字段与 Demo 自定义字段。
- [Model Context Protocol — Resources](https://modelcontextprotocol.io/specification/2025-06-18/server/resources)：`resources/list`、`resources/read`、URI、模板、分页、变更通知和订阅；用于对照“资源发现与读取”协议化后的形态，不等同于 Skill 规范。

### 官方实现与示例

- [Anthropic Skills public repository](https://github.com/anthropics/skills)：Anthropic 的公开 Skill 集合，包含 `SKILL.md`、脚本和资源目录；仓库明确说明部分内容是生产能力的参考实现，但仍需自行测试。
- [OpenHands Skills Overview](https://docs.openhands.dev/overview/skills)：说明 always-on context、on-demand Skill 和触发方式的区别。
- [OpenHands SDK Skill Guide](https://docs.openhands.dev/sdk/guides/skill)：包含 `load_skills_from_dir()`、`discover_skill_resources()`、资源目录结构和生命周期 API 示例。
- [OpenHands AgentSkills loading example](https://github.com/OpenHands/software-agent-sdk/tree/main/examples/05_skills_and_plugins/01_loading_agentskills)：可运行的开源 SDK 示例，展示目录发现、资源枚举和 AgentContext 接入。

### 开源资源库

- [OpenHands Extensions](https://github.com/OpenHands/extensions)：公开 Skill/Plugin 注册库，可用于观察 Skill 目录组织、资源引用和维护流程；不要默认信任其中任何脚本或指令。
- [OpenHands Software Agent SDK](https://github.com/OpenHands/software-agent-sdk)：开源 Agent SDK，可用于追踪 Skill 加载、资源发现、AgentContext 和安装生命周期的实际代码。

## Boundaries

- Always：固定 Skill 来源和版本；保留索引与资源读取 Trace；使用 allowlist、路径解析和文件类型检查；评测 Skill 选择与资源读取轨迹；把读取和执行分开。
- Ask first：安装公共 Skill；允许脚本执行、网络访问、写文件或读取凭证；引入新的 Skill 注册中心；修改跨 Agent Skill 继承策略。
- Never：把 Skill 正文当作授权；把自然语言完成声明当作资源执行证据；根据模型输入直接拼接任意路径；默认执行未审核的脚本；把公共 Skill 当作可信代码。

## Start Trigger

当前条目只进入 Work Pool，不自动启动。建议在完成 s08 Context Compact、s11 Error Recovery 和基础安全章节后，先从 Track A-C 和 Minimal Experiments 1-3 开始。

## Success Criteria

完成后应能够：

1. 画出 Skill Catalog、`SKILL.md`、辅助资源、Tool、Policy 和 Model Context 的数据流；
2. 为一个 Skill 设计版本固定、来源审核和资源 allowlist；
3. 解释主 Agent 与 Subagent 的 Skill 分配取舍；
4. 用故障注入证明越界读取、恶意指令和缺失资源会被发现或阻断；
5. 用 Eval 证据比较不同 Skill 路由和资源加载策略；
6. 区分 AgentSkills 标准、MCP Resources、某个 SDK 实现和本仓库教学 Demo 的边界。
