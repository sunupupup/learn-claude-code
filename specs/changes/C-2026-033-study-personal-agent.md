# C-2026-033：个人助手 Personal Agent 学习专题

- Status: active
- Origin: W-2026-039（本次直接启动，无待办卡需要迁移）
- Started: 2026-11-07
- 启动依据：用户要求按 Prompt 4 开一个 personal agent 学习专栏，并调研当前开源、闭源 Agent。
- 学习主记录：[个人助手学习入口](../../learning-notes/work-pool/W-2026-039-study-personal-agent-个人助手/LEARNING_NOTES.md)

## Objective

理解个人助手（Personal Agent，服务一个人的日常事务的 Agent）和编程 Agent、客服/企业知识 Agent、Agent 框架分别解决什么问题。先建立可复核的开源/闭源版图，再选一个开源个人助手看它如何接住消息、记住人和决定要不要行动。

## Work

1. 用一个日常例子区分个人助手、临时聊天、编程 Agent 和业务 Agent。
2. 维护一份开源/闭源版图，并标明证据日期；2026-11-07 在线复核失败，版图保持为初稿。
3. 选定一个开源个人助手后，固定仓库、版本、许可证，只追一条「外部消息进来 → 决定回复、等待或执行」的链路。
4. 用一个不该行动的例子观察权限、打扰和结果未知。不在本专题重做 Memory、Prompt Cache、客服或 Coding Agent 的已有深读。

## Expected Output / Success Criteria

- 必学：能解释个人助手通常多了渠道接入、跨会话记忆、主动时机和用户控制；能把一个产品放进正确类别。
- 版图：区分仓库已有记录与尚未在线复核的候选，不把候选名单写成当前市场事实。
- 源码阶段：有一个固定版本和一条调用链；实验阶段若进行，使用假数据和本地入口。
- 能指出隐私、误触发、成本和结果未知中的至少一项风险。
- 选学：全部渠道、全部闭源产品内部实现、Super-agent 双层架构的完整复刻。不阻塞主线。
- 当前仅完成入口和版图初稿，不代表已掌握或已复核产品现状。

## Boundaries / Related

- 不克隆外部仓库、不安装依赖、不调用付费模型、不接入真实邮箱、日历或聊天账号。
- 不覆盖用户已有未提交改动；不提交、不 push、不切换 worktree。
- 学习过程按 [Prompt 4](../../PROMPT_4_WORK_POOL_LEARN.md)。具体开源项目选定后再按 [Prompt 7](../../PROMPT_7_OPEN_SOURCE_PROJECT_LEARNING.md) 建项目笔记，不为全部候选建空目录。
- 相邻专题只引用，不重做：[Memory 中的 Hermes/OpenClaw 记忆分层](../../learning-notes/work-pool/W-2026-013-study-memory-production-practices-Memory/个人助手Agent开源项目与记忆层级.md)、[Context 缓存里的个人助手对照](../changes/C-2026-013-study-agent-context-and-prompt-cache.md)、[对话型应用 W-028](../work-pool/W-2026-028-study-conversational-agent-application-capabilities.md)、[dsh-superagent 讨论](../../开源项目学习/dsh-superagent/诞生的讨论.md)。
