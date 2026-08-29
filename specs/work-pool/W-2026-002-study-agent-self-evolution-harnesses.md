# W-2026-002：完整学习 Agent 自进化与可进化 Harness

- Status: ready
- Area: Agent / Self-Evolution / Memory / Harness / Eval / Post-training
- Difficulty: D4（从 D2 机制理解逐步进入平台与模型适配）
- Discovered From: `s04_hooks` 扩展讨论与 2026-08-28 Agent Harness 生态观察
- Owner: personal
- Priority: medium

## Assumptions

1. 这是一个后续完整学习项目，当前只进入 Work Pool，不立即安装、运行或修改任何外部 Harness。
2. “完整学习”包括理论分层、论文与源码阅读、最小安全实验和对比总结，不要求自行训练大模型或复现厂商完整 Benchmark。
3. “Agent 自进化”暂按本任务定义的工作分层研究；该术语当前没有统一的行业标准，不能把厂商或媒体口径直接当作共同定义。
4. DeepSeek Harness 与 FrontierAgent 是不同研究视角：前者重点研究可组合、可替换的 Runtime；后者重点研究模型、执行 Harness、轨迹、协调训练与 Eval 的协同。
5. 微信文章作为二手观点和问题线索；具体技术事实必须回到官方仓库、官方文档或原始论文核验。

## Work

建立一套能够区分“记住经验”“改变程序性策略”“修改 Harness”和“更新模型参数”的 Agent 自进化心智模型，并通过 DeepSeek Harness / Cordis 与 FrontierAgent / Apodex 1.1 两条主线研究完整闭环：

```text
Experience / Trajectory
        ↓
Diagnosis / Credit Assignment
        ↓
Memory、Prompt、Skill、Plugin 或 Model 候选变化
        ↓
隔离实验与 Eval
        ↓
Selection / Promotion Gate
        ↓
灰度启用、监控与 Rollback
```

学习重点不是证明 Agent “可以修改自己”，而是判断修改是否有证据地提高质量，并且能够审计、限制和回滚。

## Working Taxonomy：自进化级别

以下是本任务使用的工作分层，不主张它是行业统一标准：

| Level | 变化对象 | 需要回答的核心问题 |
| --- | --- | --- |
| E0：固定 Harness | 不跨任务保留变化 | 每次 Run 是否从相同配置开始？ |
| E1：Memory Adaptation | 工作、语义、情景记忆 | 写入什么经验，怎样召回、纠错、遗忘和防止投毒？ |
| E2：Procedural Evolution | Prompt、规则、Skill、策略记忆 | 经验如何变成可复用做法，怎样版本化并防止错误规则固化？ |
| E3：Harness Evolution | Tool、Plugin、Hook、Workflow、Agent Loop | Agent 如何提出、生成、装载、卸载和回滚新的执行能力？ |
| E4：Model Evolution | 模型权重或 Adapter | 轨迹怎样进入 SFT、偏好优化或 Agentic RL，怎样控制能力回归？ |
| E5：Model–Harness Co-evolution | 模型与执行环境共同变化 | 如何区分模型收益、Harness 收益和额外推理计算带来的收益？ |

每一级都必须单独分析 Experience、Mutation、Evaluation、Selection 和 Governance；只有 Memory 或自修改能力，不足以证明发生了可靠进化。

## Research Tracks

### Track A：稳定概念与判定标准

- 区分 State、Context、Memory、Skill、Harness、Runtime 与模型权重；
- 区分 Self-adaptation、Continual Learning、Self-improvement、Self-modification 与 Self-evolution；
- 定义“变好”的目标函数：任务成功率、轨迹质量、安全、成本、延迟和泛化；
- 研究 Credit Assignment：一次成功或失败应归因于模型、Prompt、Memory、Tool、Workflow 还是环境；
- 研究候选生成、离线 Eval、统计判断、晋级门禁、灰度和回滚。

### Track B：DeepSeek Harness 与 Cordis

重点追踪：

- “Everything is a Plugin”怎样覆盖 Model、Tool、Skill、Session、Sandbox、Storage、Loop、Scheduling 与 UI；
- Agent Loop、Session Event Log、Tool Pipeline 和 Extensions 子系统之间的关系；
- Runtime 如何检查、定义、运行、停止和删除动态插件；
- Cordis 的 Temporal Composability 与 Spatial Composability 如何支持副作用撤销和依赖重组；
- 动态插件目前哪些内容只存在于进程内存，哪些能够持久化；
- Developer Preview、API 变化、供应链、Prompt Injection、代码执行和权限边界；
- “可自修改”距离“经 Eval 证明并安全晋级”还缺哪些组件。

### Track C：FrontierAgent 与 Apodex 1.1

重点追踪：

- FrontierAgent 的通用 Runtime、Workflow Plugin、Tool Plugin、ReAct 和 Agent Team 的边界；
- `PipelineSpec`、State、Context Policy、Scheduler、AgentBus 和 Observer 如何组成执行链；
- Sandbox、审批、变更 Journal、Trace 与 Benchmark Harness 如何支持可验证工作；
- Apodex 1.1 中 Environment Scaling 与 Agentic Coordination Scaling 的含义；
- 执行轨迹、协调 Trace、SFT 与 Agentic RL 如何连接模型训练和 Harness；
- 如何通过消融或固定变量，区分模型能力、Harness、并行计算和 Eval 配置带来的提升；
- 官方报告的 Benchmark 应怎样看待数据、Judge、成本、并发和可复现性。

### Track D：Memory 与 Harness Evolution 的关系

- Memory 是经验来源、候选策略还是直接执行规则？
- Semantic、Episodic 与 Procedural Memory 分别对应哪些进化层级？
- 记忆怎样形成 Skill 或 Plugin 候选，但不直接越过 Eval Gate；
- 如何处理记忆投毒、错误总结、冲突、过期、隐私、跨用户污染和删除；
- 为什么完整 Session Log 或 Trace 不能直接无筛选地成为长期 Memory 或训练数据。

## Source Set

### Primary Sources

- [DeepSeek Harness 官方介绍](https://www.deepseek.com/harness/en/)
- [DeepSeek Harness 官方仓库](https://github.com/deepseek-ai/deepseek-harness)
- [DeepSeek Harness Architecture](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md)
- [DeepSeek Harness Extensions](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/extensions/README.md)
- [Cordis：A Programming Paradigm for Spatiotemporal Composability](https://arxiv.org/abs/2608.25512)
- [FrontierAgent 官方仓库](https://github.com/ApodexAI/FrontierAgent)
- [FrontierAgent Framework Architecture](https://github.com/ApodexAI/FrontierAgent/blob/main/docs/framework.md)
- [FrontierAgent Evaluation](https://github.com/ApodexAI/FrontierAgent/blob/main/docs/eval.md)
- [Apodex 1.1：Scaling Agentic Intelligence for Complex Work](https://arxiv.org/abs/2608.23283)
- [Apodex Discovery](https://arxiv.org/abs/2608.11341)

### Secondary Source / Lead

- [微信公众号文章](https://mp.weixin.qq.com/s/SyZFJh34Cbr4s16ODqtGsg)

该微信页面在 2026-08-28 建档时无法通过当前抓取工具读取正文。启动任务时先记录标题、作者、发布日期和核心论点，再逐条链接到一手证据；无法核验的内容应明确标成观点或待验证主张。

## Freshness Notes

截至 2026-08-28：

- DeepSeek Harness 官方标记为 Developer Preview，并明确提示可能出现破坏兼容性的变化；
- 官方 Extensions 文档显示，动态定义当前只存在于进程内存，重启会清除；
- FrontierAgent 官方仓库已公开 ReAct、Agent Team、Sandbox 与 Benchmark Evaluation 等实现，并以 Apache-2.0 发布；
- Apodex 1.1 原始报告把共享 Harness / AgentOS、环境轨迹、协调 Trace、SFT 和 Agentic RL 放在同一训练与执行体系中；
- 上述项目发展很快，正式开始学习时必须重新核对 Release、Commit、License、安全公告和文档状态。

## Relationship to Existing Work

本任务复用 [W-2026-001：调研小型 Agent 项目的 Hook 生产实践](./W-2026-001-study-agent-hook-production-practices.md) 中关于生命周期、插件契约、异常、权限与观测的结论，但不与它重复：

- W-2026-001 回答“扩展点如何安全运行”；
- W-2026-002 回答“系统如何基于经验提出变化、验证变化并选择新版本”。

## Reason Deferred

当前仍在按章节学习基础 Harness 机制。自进化同时依赖 Skill、Memory、Context、Error Recovery、Eval、Sandbox、Trace、版本和回滚；现在直接钻研完整项目，容易把厂商实现或媒体叙事误当成稳定原理。

## Start Trigger

满足以下条件后开始：

- 已完成 `s07_skill_loading`、`s09_memory`、`s11_error_recovery`，并优先完成 `s20_comprehensive`；
- 能独立区分 State、Context、Memory、Skill、Tool、Runtime 与 Harness；
- 能解释基本的 Eval Set、Trajectory Eval、版本门禁与回滚；
- 启动时把本文件转成 `specs/changes/C-YYYY-NNN-*.md`，并从 Work Pool 移除。

## Preferred Order

1. 固化术语和 E0–E5 工作分层，明确哪些层级没有改变模型权重。
2. 建立冻结的最小任务集和固定 Harness 基线，先定义怎样才算“变好”。
3. 阅读 DeepSeek Harness / Cordis 一手资料，画出插件装载、卸载、回滚和 Session Log 链路。
4. 阅读 FrontierAgent / Apodex 1.1 一手资料，画出 Runtime、Workflow、Eval 与训练轨迹链路。
5. 对微信文章和其他二手内容制作“主张—证据—结论”核验表。
6. 在隔离环境完成一个无危险副作用的插件热装载与卸载实验。
7. 实现或模拟一个最小 Evolution Gate：旧版本、候选版本、冻结 Eval、晋级条件和回滚。
8. 对两个项目做同口径比较，区分事实、推断、Benchmark 声明和营销表述。
9. 输出完整学习总结，并判断哪些机制值得迁移到自己的 Agent 项目。

## Experiment Boundaries

- 不在宿主机直接运行 Agent 生成的未知代码或自更新插件；
- 不授予实验 Agent 无限制文件、网络、凭据、包安装或进程控制权限；
- 不安装未经源码检查和版本锁定的社区“自进化”插件；
- 候选修改只能在隔离环境运行，必须有时间、Token、成本和步骤预算；
- 不让候选版本直接覆盖稳定版本；每次变化必须保留来源、Diff、Eval 结果和回滚点；
- 不把单次成功、厂商 Benchmark 或 LLM 自评当作进化证据。

## Expected Output

- 一份 E0–E5 Agent 自进化分层与术语边界说明；
- 一张完整 Evolution Loop 图：Experience → Mutation → Eval → Selection → Rollout / Rollback；
- 一张 DeepSeek Harness / Cordis 插件生命周期与自修改边界图；
- 一张 FrontierAgent / Apodex 模型—Harness—轨迹—训练—Eval 关系图；
- 一份相同维度的项目对比表，覆盖状态、Memory、插件、训练、Eval、可观测、安全和回滚；
- 一份“媒体主张—一手证据—核验结论”表；
- 一个隔离、可复现、可回滚的最小 Harness Evolution 实验；
- 至少一个候选版本被拒绝的案例，证明 Gate 不只会接受修改；
- 一份结论：哪些属于适应、哪些属于进化、哪些仍只是实验性可能。

## Acceptance Criteria

- 能用自己的话解释 Memory 为什么常被称为自进化，以及它单独缺少什么；
- 能分别指出 E1、E2、E3、E4、E5 改变的对象、收益证据与主要风险；
- 能从源码或官方文档追踪 DeepSeek 动态插件和 FrontierAgent Workflow / Eval 的真实调用边界；
- 能解释 Cordis 的可组合性为何有利于试验与回滚，但为何不能自动证明质量提升；
- 能解释 Apodex 1.1 中模型训练与 Harness 的关系，并避免把系统级收益全部归因于模型；
- 能用冻结 Eval、对照基线和回滚演示一次受控候选晋级或拒绝；
- 能识别记忆投毒、Prompt Injection、供应链、自修改代码和错误反馈闭环等风险；
- 所有版本敏感结论均带核对日期和一手来源，无法验证的说法明确标记为未知。

## Non-goals

- 不以训练或复现 Apodex 1.1 模型作为完成条件；
- 不追求复刻厂商全部 Benchmark 或排行榜成绩；
- 不把 DeepSeek Harness、FrontierAgent 或任一框架确立为唯一正确架构；
- 不构建无人监管、可以直接修改生产环境的自进化 Agent；
- 不在本任务启动前自动处理 Work Pool 中的任何实现工作。
