# dsh-superagent

DeepSeek Harness 团队公开的编程 Agent 研究原型，接收单个 GitHub 仓库及可选飞书中的请求，组织任务并向原会话交付结果。
以 DeepSeek Harness bundle（扩展组合包）运行；宿主提供 Agent 执行支撑，本项目重点组织消息接入、授权任务和执行器派工。公开代码不等同于内部版本或设计文章的全部设想，也不代表正式 DeepSeek 产品。

- 官方仓库：[deepseek-ai/dsh-superagent-prototype](https://github.com/deepseek-ai/dsh-superagent-prototype)
- 本次研究范围：Harness 上的 bundle；先看 `src/sources/` 与 `src/core/` 的消息接入和任务路由。
- 许可证：MIT；已核对仓库 `LICENSE`。
- 读取版本：`6337fc823ce20251c8de8085948165c81aaa701e`；读取日期：2026-11-02。
- 外部源码：`D:/code/source-reading/dsh-superagent-prototype`。
- 相关旧笔记：[DeepSeek 插件化与 RSI 的关系](../../learning-notes/work-pool/W-2026-026-study-agent-self-evolution-harnesses-自进化Agent/DeepSeek插件化与RSI的关系.md)（宿主背景；不代表本项目已实现自进化）。

## 学习模块

- [消息接入与任务路由](消息接入与任务路由.md)：一条外部消息如何进入已有任务或新任务评估？已初始化。

# 我的感悟

用户侧很简洁，一次委派就能覆盖从需求到结果的整段过程。
结果导向、低人工干预的端到端委派。

deepseek super agent解决的问题有很多
1. 讨论任务 和 布置任务，应该是同时的，而不是 讨论完之后单独再进行布置任务
2. 人的注意力不被多session的方式而分散注意力

其实这种事件驱动的形式，还挺多的
我们也做过
钉钉对话的时候，直接艾特机器人，然后触发事件，起一个agent解决问题


额外的感觉就是，他确实解决了某些痛点
类似的还有 钉钉消息的主动查询、codex的prompt预测
其实都是 塑造一个更加主动的角色
