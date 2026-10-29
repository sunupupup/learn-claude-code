# LangGraph：可持久化中断与人类审批

- **官方仓库**：[langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)；[HITL 官方指南](https://docs.langchain.com/oss/python/langgraph/human-in-the-loop)；[interrupt API](https://docs.langchain.com/oss/python/langgraph/interrupts)
- **用途/层次**：图式 Agent Runtime，用于构建有状态、可暂停并恢复的流程。
- **相关机制**：节点内 `interrupt()`；使用 checkpointer 持久化；用 thread ID 找回执行状态；以 `Command(resume=...)` 恢复。
- **具体入口**：Python 文档 Human-in-the-loop / Persistence / Interrupts；源码 `libs/langgraph/langgraph/types.py` 的 `interrupt`；看清恢复时节点会从头重跑。
- **前置/难度/顺序**：Python 基础、状态图/函数节点；中；OpenAI SDK 之后作为审批实现对照。
- **维护/许可证（2026-09-26）**：GitHub API 显示 MIT、最近推送 2026-09-26；latest release endpoint 返回 `cli==0.4.32.dev0`（2026-09-23），这是 CLI prerelease 而非 LangGraph 库版本，正式学习需另锁 Python/JS 包版本。LangGraph 库开源；LangGraph Platform/托管部署是另外的产品服务边界。
- **优点**：暂停/检查点/恢复概念清晰，适合观察长流程状态；通用 Runtime 风格，不局限审批 UI。
- **局限/边界**：`interrupt` 只是控制流原语，业务端必须提供可靠持久化、受权审批者、参数绑定、执行点授权和幂等；节点重跑可能重复副作用，必须理解恢复语义。
- **建议观察**：中断值如何序列化；恢复时哪些代码重跑；副作用放在中断之前/之后会怎样；checkpointer 的 thread ID 是否经过用户授权校验。
- **Context7**：已解析 `/langchain-ai/langgraph` 并查询官方 interrupt/checkpointer 文档，2026-09-26；实现版本届时再选定。



