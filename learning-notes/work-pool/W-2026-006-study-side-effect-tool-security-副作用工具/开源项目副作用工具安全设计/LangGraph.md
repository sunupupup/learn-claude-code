# LangGraph

- 仓库：[langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)
- 官方文档：[Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)、[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[Release policy](https://docs.langchain.com/oss/python/release-policy)
- Context7：候选 ID `/langchain-ai/langgraph` 和 `/websites/langchain_oss_python_langgraph`；已核对 interrupt、checkpoint 和 resume 的官方文档/源码资料。
- 本次查验：2026-09-26；MIT，GitHub Releases 可见 1.2.12 发布于 2026-09-23，维护活跃；固定版本前重新复核。
- 开源分类：MIT 开源框架。
- 难度/顺序：D2，推荐第 3 个，作为 Agent Runtime 暂停恢复窄对照。

## 适合回答的问题

图节点在等待人工决定后如何恢复？如果同一节点在 interrupt 前已经做了外部写操作，恢复时会发生什么？

## 建议阅读入口

先读 Interrupts 与 Persistence；再看官方 `langgraph/types.py` 的 `interrupt` 语义及相关测试。文档明确：恢复从包含 interrupt 的节点开头重新执行，因此副作用放在 interrupt 前需要格外谨慎；可将副作用拆成独立可重入步骤或依赖业务幂等。

## 前置、优势与局限

- 前置：Python 函数、状态字典/TypedDict、节点与边的基本概念；了解 checkpoint（检查点）保存运行状态。
- 优势：暂停、持久化和恢复路径易观察，可研究人工输入、checkpoint 与节点重进的关系。
- 局限：checkpoint 不等于外部事务提交；恢复不承诺业务副作用 exactly-once；具体语义依赖所选 checkpointer、线程 ID 和执行版本。
- 推荐比较：和 OpenAI Agents SDK 对照审批由工具级 API 还是图级节点中断表达；和 Temporal 对照不同的重放/持久化模型。

## 证据边界

文档/Context7 核验了文档化的恢复和节点重跑语义；没有固定本章 commit，也没有运行故障实验。
