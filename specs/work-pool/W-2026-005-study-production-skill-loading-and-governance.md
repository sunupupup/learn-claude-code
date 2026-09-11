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

## 核心生产关注点（全部必学）

下面九类问题不是可选扩展，而是动态加载 Skill 从教学 Demo 走向生产 Runtime 时的共同验收面。学习过程中每一类都要有机制解释、故障样例、可观察证据和明确边界。

1. **Context 预算与渐进披露**：目录、`SKILL.md`、reference、Tool Result 分层进入 Context；限制每个 Skill、每次 Run、每个租户的字节数、Token、行数和延迟预算。截断、拒绝或降级必须可观察，不能静默吞掉关键指令。
2. **版本与一致性**：明确 Run 是否固定 Skill 及资源版本；使用版本、内容哈希和缓存键保持一致；更新要有原子发布、缓存失效、兼容性检查、灰度或回滚策略。
3. **供应链信任**：记录来源、许可证、版本、哈希、签名、审核状态和依赖；区分内置、组织仓库、公共市场和用户上传；默认不信任外部 Skill 及其脚本。
4. **安全边界与授权判定**：Skill 文本是模型可见输入，不是授权；读取资源不自动获得执行脚本、联网、写文件或读取凭证的能力。Runtime 必须基于主体、租户、Run、Skill 版本、资源和动作风险独立做 allow/ask/deny 判定。
5. **隔离与数据边界**：隔离租户、用户、任务、Agent 的 Skill 可见性、缓存、临时文件、凭证、运行状态和 Context；禁止跨 Run 或跨租户复用未经授权的内容。
6. **路由质量与冲突处理**：研究发现、候选匹配、阈值、多个 Skill 冲突、优先级、漏加载、误加载和无合适 Skill 时的降级策略；不能只凭模型最终答案判断路由正确。
7. **失败恢复与生命周期**：为资源缺失、版本冲突、超时、部分加载、缓存陈旧、更新中断以及恢复/compact 后的重新组装定义类型化状态、重试边界、固定快照和安全降级。
8. **可观测性与因果链**：Trace 至少能串起 discovery、routing、version resolution、loading、resource read、context injection、model generation、Tool/Subagent 和 outcome；同时记录版本、哈希、预算、耗时和决策原因，并避免把敏感正文直接写入日志。
9. **Eval 与质量门禁**：除最终答案外，评测 Skill 选择准确率、漏/误加载率、资源读取轨迹、越权拦截率、冲突处理、恢复行为、Token、延迟、缓存命中率和成本，并把安全与回归指标接入发布门禁。

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

## 建议学习路径与阶段产出

采用“先建立边界，再做最小实验，最后组合验证”的顺序；每个阶段只推进一个主要问题，完成后保留证据再进入下一阶段。

### Phase 1：Context 预算与渐进披露

- 以 s07 的 `catalog → SKILL.md → 单个 reference` 为基线，比较三种加载层级的消息、Token、延迟和最终可见内容。
- 产出：一张 Context 分层图、一张预算表，以及“超预算时拒绝、截断还是降级”的决策表。
- 验收：能够解释“没有加载”与“加载后被截断”的区别，并能从 Trace 还原实际进入 Context 的内容。

### Phase 2：安全边界、供应链与隔离

- 先建立主体、租户、Run、Skill、资源、Tool 和凭证的权限矩阵，再注入路径遍历、恶意指令、未声明资源、跨租户缓存和越权 Tool 场景。
- 产出：威胁模型、allow/ask/deny 判定表、来源与版本记录结构、隔离边界图。
- 验收：能够证明“Skill 声明了权限”不等于“Runtime 授予了权限”，且一个租户的 Skill 内容不会进入另一个租户的 Context。

### Phase 3：版本、一致性、更新与恢复

- 比较 Run 固定快照、热刷新和缓存失效三种策略；模拟资源更新、版本冲突、部分加载、超时、恢复和 compact。
- 产出：Skill 生命周期状态机、缓存键设计、更新/回滚流程和失败状态表。
- 验收：能够回答一次 Run 在中途更新 Skill 后究竟继续使用哪个版本，以及失败恢复后如何保持同一版本语义。

### Phase 4：路由、可观测性与 Eval

- 冻结一组带有明确期望 Skill、故意相似 Skill、无合适 Skill 和恶意 Skill 的任务集；为 discovery、routing、loading、injection 和 Tool 建立稳定事件与 Trace 关联。
- 产出：事件 Schema、Trace 示例、离线 Eval 表和发布门禁指标。
- 验收：能够回答“为什么选择这个 Skill、加载了什么、它是否影响了后续动作”，并能区分路由失败、加载失败和模型执行失败。

### Phase 5：最小集成 Runtime

- 只组合本地、只读、固定版本的 Skill；暂不引入公共 Skill 安装、脚本执行、真实凭证或外部副作用。
- 产出：一个可重复运行的最小 Demo，包含 catalog、版本固定、资源 allowlist、预算、策略判定、Trace、Eval 和故障注入。
- 验收：用确定性测试证明越界读取、恶意资源、未授权 Tool、预算超限、版本冲突和资源缺失都能被识别或阻断。

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

当前条目只进入 Work Pool，不自动启动。建议在完成 s08 Context Compact、s11 Error Recovery 和基础安全章节后，按 Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 推进；第一轮先完成 Phase 1 和 Minimal Experiments 1-3，不立即引入公共 Skill、脚本执行、联网或真实凭证。

## Success Criteria

完成后应能够：

1. 画出 Skill Catalog、`SKILL.md`、辅助资源、Tool、Policy 和 Model Context 的数据流；
2. 为一个 Skill 设计版本固定、来源审核和资源 allowlist；
3. 解释主 Agent 与 Subagent 的 Skill 分配取舍；
4. 用故障注入证明越界读取、恶意指令和缺失资源会被发现或阻断；
5. 用 Eval 证据比较不同 Skill 路由和资源加载策略；
6. 区分 AgentSkills 标准、MCP Resources、某个 SDK 实现和本仓库教学 Demo 的边界。
