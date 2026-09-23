# C-2026-003：Agent Task Completion Verification 与完成证据学习

- Status: active
- Area: Agent / Task System / Verification / Eval / Reliability / Side Effects
- Origin: W-2026-003
- Started: 2026-09-14
- Owner: personal
- Priority: high
- Main learning record: [LEARNING_NOTES.md](../../learning-notes/work-pool/W-2026-003-study-task-completion-verification-任务完成验证/LEARNING_NOTES.md)
- Related: [s12 Task System](../../s12_task_system/)、[s13 Background Tasks](../../s13_background_tasks/)、[s15 Agent Teams](../../s15_agent_teams/)、[s18 Worktree Isolation](../../s18_worktree_isolation/)、[W-2026-004 Tool Result 恢复](../changes/C-2026-012-study-tool-result-compaction-and-recovery.md)、[W-2026-006 副作用 Tool 安全](../work-pool/W-2026-006-study-side-effect-tool-security.md)、[W-2026-015 Subagent Runtime](../work-pool/W-2026-015-study-production-subagent-runtime.md)

## 本次启动范围

研究如何把“模型声称完成”转化为“系统有证据地允许完成”，重点覆盖任务契约、确定性验证器、状态机、证据关联、LLM 语义评估边界，以及失败、重试、部分成功和未知状态。

本轮采用混合线，顺序为：通用概念 → 一个固定版本的源码样本 → 最小确定性实验 → 失败恢复与生产设计。启动阶段只做只读分析，不立即修改 `s12` 教学实现，不安装新依赖，不调用付费模型或真实副作用服务。

## 首个学习小节

先回答一个问题：`in_progress → completed` 到底证明了什么、没有证明什么？以 `s12_task_system/code.py` 的 `complete_task()` 为基线，追踪状态、执行结果和证据之间的断裂，再设计最小的任务契约字段。

## 目标产出

- 任务契约和验收标准模板；
- 验证状态机与失败转移图；
- 确定性 verifier registry 设计；
- Evidence 与 Artifact 的关联格式；
- 确定性验证与 LLM 语义评估的对照实验；
- 覆盖虚假完成、响应丢失、验证超时和重复副作用的 Eval；
- 适用于 Subagent、后台任务和高风险 Tool 的完成门设计。

## 当前证据与未决事项

- 已读仓库规则、003 原任务卡、s12/s13/s15/s18 相关资料和当前工作区状态。
- 当前教学实现的确定事实：`complete_task()` 只检查任务处于 `in_progress`，不检查 Bash、测试、文件、数据库或外部 API 的真实结果。
- 未决定主源码样本；正式源码线开始时重新核对版本、Commit、许可证和官方资料。
- 尚未运行实验，尚未形成生产级完成结论。

## 验证与完成标准

每个结论都标记为通用原理、教学代码事实、源码核验或运行观察。完成本 Change 前，需要能解释 `completed`、`verified`、`approved` 与模型自述的边界，并对失败、部分成功、未知状态、重试和重复副作用给出可执行的状态与证据设计。

