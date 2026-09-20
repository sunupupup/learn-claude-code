# Agent 架构与协作知识图谱

> 本章是 W-2026-016 的学习地图。**控制流、协作拓扑和生命周期是可组合的维度，不是从 ReAct 升级到多 Agent 的单一路线。**
> [学习总览](我的笔记.md) · [任务范围](../../../specs/changes/C-2026-009-study-agent-to-agent-collaboration-patterns.md)

## 1. 完整技术链路

```text
用户目标与成功条件
  → 选择推进方式：固定流程 / 反馈驱动的 Agent 循环 / 显式规划执行
  → 确定执行责任：单 Agent / 子任务委派 / 对话移交 / 团队协作
  → 准备上下文：任务、历史、Skill、记忆与工具说明
  → 模型决策 → 权限检查 → 工具或子 Agent 执行
  → 结果、消息与任务状态回收
  → 验证进展 → 继续 / 重规划 / 等待 / 失败或完成
```

状态保存、预算、日志和恢复贯穿各环节；不是每个任务都需要团队或持久执行。

## 2. 问题与扩展方案

| 面对什么问题 | 改变哪个环节、怎么改 | 概念或方案 | 深入入口 |
| --- | --- | --- | --- |
| 下一步必须根据刚读到的信息决定 | 工具结果回到模型，模型再选动作 | ReAct，推理与行动交替 | [控制流辨析](ReAct与规划执行的代码控制流辨析.md)、[s01](../../../s01_agent_loop/README.md) |
| 长任务容易忘记目标和进度 | 把步骤、状态保存在任务清单 | Todo，计划辅助 | [s05](../../../s05_todo_write/README.md) |
| 需要分别管理计划和当前步骤 | 规划结果进入状态，编排代码派发步骤并处理反馈 | Plan-and-Execute / Planner-Executor | [控制流辨析](ReAct与规划执行的代码控制流辨析.md)；重规划实验待安排 |
| 类似任务反复需要相同规范 | 在上下文准备环节加载方法与资源 | Skill，技能包 | [s07](../../../s07_skill_loading/README.md) |
| 局部任务的探索历史太多 | 子 Agent 独立上下文，回收结果 | Subagent / Agent-as-Tool | [s06](../../../s06_subagent/README.md)、[W-015](../../../specs/work-pool/W-2026-015-study-production-subagent-runtime.md) |
| 用户需要另一位专家持续接管 | 转移当前任务或对话控制权与所需上下文 | Handoff，控制权移交 | [任务模式地图](../../../specs/changes/C-2026-009-study-agent-to-agent-collaboration-patterns.md)；模块待学习 |
| 工作可并行，或需要持续协作 | 派发—汇总；或为独立循环增加 inbox | Fan-out/Fan-in、Lead-Teammate | [s15](../../../s15_agent_teams/README.md) |
| 多个执行者需要共同领取工作 | 使用共享任务状态，定义认领与完成规则 | Task Board，任务板 | [s12](../../../s12_task_system/README.md)、[s17](../../../s17_autonomous_agents/README.md) |
| 输出需要再次检查 | 增加评审与有上限的修正环节 | Generator-Critic，生成—评审 | [一手模式资料](https://www.anthropic.com/engineering/building-effective-agents) |
| 单一负责人难以协调全部工作 | 比较层级委派与同级协商，明确最终责任 | Hierarchical Team、Peer | [W-017](../../../specs/work-pool/W-2026-017-study-agent-team-hierarchy-and-delegation.md) |
| 需要等待消息或跨崩溃继续 | 区分 idle 等待和持久化恢复 | Idle、Durable、Checkpoint | [W-018](../../../specs/work-pool/W-2026-018-study-persistent-teammate-lifecycle.md) |
| 模型声称完成但证据不足 | 独立检查结果、权限与副作用状态 | 验收、预算、幂等、恢复 | [s16](../../../s16_team_protocols/README.md)、[s20](../../../s20_comprehensive/README.md) |

## 3. 概念之间的关系与术语速查

| 层次 | 术语 | 关系与边界 |
| --- | --- | --- |
| Agent 决策与控制流 | ReAct（Reasoning + Acting） | 依据观察交替推理和行动；有循环不自动证明严格复现论文 |
| 应用编排 | Plan-and-Execute（规划后执行） | 分离规划与执行；执行器内部可以采用 ReAct；显式派发代码是常见实现，不是唯一形式 |
| 上下文与能力组织 | Skill（技能包）、Tool（工具接口） | Skill 指导任务方法，可携带资源；Tool 执行具体操作，两者不替代控制流 |
| 系统协作 | Multi-Agent（多智能体）、Topology（拓扑） | 描述谁与谁协作、谁持有控制权；可以搭配不同执行模式 |
| 执行支撑 | Harness（Agent 周边控制代码） | 组织上下文、工具、状态、权限和循环；不是模型内部架构 |
| 运行与恢复 | Lifecycle（生命周期）、Checkpoint（检查点） | 说明实体何时运行/等待/停止及如何恢复；驻留线程不等于跨进程持久化 |

**组合例子：Planner 生成调研计划 → Manager 委派多个研究任务 → 每个 Worker 用 ReAct 探索 → 汇总器核对证据。** 这是教学构造，不是本仓库已运行的实验。

另一个边界：Todo 维护进度，不必然负责调度；Task Board 为多个执行者提供共享协调状态。上下文隔离也不等于文件目录或权限隔离。

## 4. 主线与选学扩展

必学主线按[总览](我的笔记.md)推进，保留原任务七项 Success Criteria。先看实际调用与状态变化，再讨论抽象名词。四类应用场景是研究、代码修改、客服路由和长任务审批。

选学：深层递归团队、大规模 Peer 协商、通用消息中间件、分布式调度器实现。遇到真实协调瓶颈、跨服务恢复需求时再展开，不预设多 Agent 更好。

## 5. 子笔记、Demo 与资料索引

- 场景选择：[ReAct、固定工作流与规划执行](ReAct、固定工作流与规划执行的场景选择.md)，区分探索、固定流程和动态计划。

- 真实项目窄对照：[Codex 计划模式源码调研](Codex计划模式源码调研.md)，已固定 Commit；用于区分产品 Plan Mode 和步骤派发架构，不代表整个真实项目验收完成。

- 已有子笔记：[ReAct 与规划执行的代码控制流辨析](ReAct与规划执行的代码控制流辨析.md)。
- 本任务尚无 Demo；后续确有需要才创建 `experiments/<module-slug>/`，不把伪代码当作运行证据。
- [ReAct 原论文](https://arxiv.org/abs/2210.03629)：2026-09-20 核对论文摘要，作为推理与行动交替的原始依据。
- [Anthropic：Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)：2026-09-20 核对流程与 Agent、组合模式和环境反馈；该文章含历史工具信息，本章只引用模式概念。
- [Anthropic 多 Agent 研究系统](https://www.anthropic.com/engineering/multi-agent-research-system)：本次对话查到的一手案例；后续精读通信和验收细节，不能替代源码与实验。
- 框架、SDK 与真实项目 API 的后续实现先查询 Context7，再固定源码版本。初始化阶段尚未确定主研究项目。
