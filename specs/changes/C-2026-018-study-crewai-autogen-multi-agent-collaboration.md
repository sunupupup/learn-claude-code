# C-2026-018：CrewAI 与 AutoGen 多 Agent 协作框架学习

- Status: active
- Area: Multi-Agent Framework / Orchestration / Agent Collaboration / Runtime Boundaries
- Difficulty: D1 → D2（从框架定位进入常见协作控制流与实现对照）
- Started: 2026-09-27
- Learning record: [LEARNING_NOTES.md](../../learning-notes/work-pool/W-2026-033-study-crewai-autogen-multi-agent-collaboration/LEARNING_NOTES.md)
- Knowledge map: [多 Agent 协作框架知识图谱](../../learning-notes/work-pool/W-2026-033-study-crewai-autogen-multi-agent-collaboration/多Agent协作框架知识图谱.md)
- Related: [Agent-to-Agent 协作模式](C-2026-009-study-agent-to-agent-collaboration-patterns.md)、[Agent Team 层级与委派](../work-pool/W-2026-017-study-agent-team-hierarchy-and-delegation.md)、[生产级 Subagent Runtime](../work-pool/W-2026-015-study-production-subagent-runtime.md)

## Objective

以 CrewAI 和 AutoGen 为主要开源样本，理解多 Agent 框架怎样把多个 Agent 组织成可运行的协作流程。建立从用户任务、任务拆分、Agent 选择、消息/状态传递、工具执行到结果汇总与验证的常见链路，并能对照框架实现解释每个环节由谁控制。

用户的初始判断“这两个项目与多 Agent 协作有关”成立。学习中继续区分多 Agent 框架、单 Agent 工具循环、确定性 Workflow 与底层 Runtime，不根据项目名称或示例演示直接推断生产能力。

## 必学主线

1. 多 Agent 编排要解决什么问题；哪些任务用一个 Agent 或普通 Workflow 更合适。
2. CrewAI 的 Agent、Task、Crew、Process 与 Flow 如何组合；常见顺序执行与管理者协调流程是什么。
3. AutoGen 的 AgentChat 与 Core 如何分层；常见团队对话/选择模式和消息驱动机制如何协作。
4. 对照两者的控制权、共享上下文/状态、消息或任务交接、工具调用、停止条件与最终结果。
5. 用固定的小任务逐步追踪文档与源码；区分文档声明、源码行为、运行观察和生产效果证据。
6. 讨论多 Agent 带来的协调成本、重复工作、失败传播、权限边界、可观测性和结果验收。

AutoGen 官方文档在 2026-09-27 经 Context7 查询显示项目处于 maintenance mode，并建议新项目关注 Microsoft Agent Framework。该项目只作为 AutoGen 生命周期和后续方向的背景，不把它扩成第三个同深度主样本；启动源码学习前需再次核实状态。

## 推荐学习顺序

1. 用最小例子建立“单 Agent / Workflow / 多 Agent”的问题边界。
2. 先读 CrewAI 的核心概念，画出一个任务从输入到 Crew 输出的控制流。
3. 再读 AutoGen 的 AgentChat 常见模式，辨认其与更底层 Core 的边界。
4. 按同一观察表比较双方的消息、状态、工具、终止与结果验收机制。
5. 按需固定版本、许可证和 Commit，追踪一条源码调用链；不要预先克隆或安装。
6. 用同一安全任务设计可重复对照，观察协作收益及额外成本；真实模型运行或依赖安装须在需要时再决定。

## Expected Output

- [知识图谱](../../learning-notes/work-pool/W-2026-033-study-crewai-autogen-multi-agent-collaboration/多Agent协作框架知识图谱.md)与[名词清单](../../learning-notes/work-pool/W-2026-033-study-crewai-autogen-multi-agent-collaboration/名词清单.md)；
- [开源项目专题](../../learning-notes/work-pool/W-2026-033-study-crewai-autogen-multi-agent-collaboration/开源项目多Agent协作框架设计/子项目.md)，含 CrewAI 与 AutoGen 独立项目入口；
- 一张同任务下两框架常见协作链路和机制对照表；
- 至少一条经固定版本核验的源码链路，说明教学模型与项目实现的异同；
- 一份多 Agent 适用条件、额外成本及生产边界总结。

## Success Criteria

1. 能用自己的话说明 CrewAI 和 AutoGen 为什么属于多 Agent 应用/编排框架，并说明其抽象不完全相同。
2. 能说明 CrewAI 的 Crew 与 Flow、AutoGen 的 AgentChat 与 Core 在常见学习路径中的职责边界。
3. 能沿同一任务对照任务控制、消息/状态、工具执行、结束条件和结果回收，而不只罗列 API 名称。
4. 能判断常见任务使用单 Agent、确定性 Workflow 或多 Agent 的取舍，并指出协调成本。
5. 对随版本变化的项目状态、API 和源码行为给出带版本与证据类型的结论；未运行的行为明确标为待验证。

## Boundaries

- 当前建立学习入口与项目选题骨架；不安装依赖、不克隆第三方源码、不调用付费模型、不修改教学代码。
- 主样本限 CrewAI 与 AutoGen；Microsoft Agent Framework 只用于说明 AutoGen 官方提及的后续方向，不作同等深度比较。
- 不把角色命名、群聊轮次或 Agent 数量本身当作可靠协作或效果证据。
- 生产权限治理、Durable Runtime、深层嵌套团队和广泛框架市场比较作为选学/关联主题，避免重复 W-2026-015、W-2026-017 与 C-2026-009。
- 学习过程与掌握状态以 `LEARNING_NOTES.md` 及其子笔记为准；本 Change 维护范围、验收和进度摘要。

## Initial Setup and Verification

- 2026-09-27：用户确认新开章节并要求 push。检查仓库 Spec 流转、现有 Agent 协作专题与工作区状态；创建章节索引、知识图谱、术语入口和两个独立项目选题页。
- Context7 已查询 CrewAI、AutoGen 官方维护文档，用来核对初始概念与 AutoGen 当前状态；来源入口记录在各自项目笔记。动态状态须在正式源码研究时重查。
- 本次只初始化文档骨架；尚无项目版本/Commit/许可证核验、克隆、实验或学习掌握证据，成功标准均待学习验证。
