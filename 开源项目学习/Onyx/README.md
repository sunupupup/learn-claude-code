# Onyx

企业知识搜索与 AI 问答平台，为员工和 AI Agent 提供企业知识上下文。官方说明通过连接器同步内容、元数据与权限，并建立混合检索索引；本项目作为后续学习企业知识库实现的起点。

- 官方仓库：[onyx-dot-app/onyx](https://github.com/onyx-dot-app/onyx)；与 `onyx-robotics/onyx-agent` 区分。
- 本次研究范围：Standard Onyx 的企业知识库相关实现；按下方八个主题逐步学习。
- 许可证：[根 LICENSE](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/LICENSE) 已核验：非 `ee` 内容适用 MIT（第三方组件按各自许可），`ee` 目录适用 Onyx Enterprise License。
- 资料基线：`32c08fb95c3b829570466258958bbc8b3f129ad7`；读取日期：2026-10-15。
- 已读资料：[固定版本 README](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/README.md)、[官方文档入口](https://docs.onyx.app/welcome)。
- 证据状态：官方资料已读，八个主题的源码入口已初步静态定位；未完成完整调用链或运行验证。
- 本地源码：`D:\code\third-party-labs\agent\source-reading\onyx`（仓库外，固定到上述 Commit）。
- 相关旧笔记：[RAG 等知识组织方式的学习入口](../../learning-notes/work-pool/W-2026-025-study-rag-vs-llm-wiki-vs-ontology-RAG/LEARNING_NOTES.md)，仅作背景关联，不能作为 Onyx 实现的证据。

## 学习模块

截图 EP06 重复一次，去重后为八个学习主题；主题不等于八个独立源码包。

1. [企业知识 Agent 整体链路](企业知识Agent整体链路.md)：从公司数据到有依据的回答，中间经过哪些模块？
2. [企业数据接入与同步](企业数据接入与同步.md)：Slack、Drive、GitHub、Notion 的数据在回答前怎样进入 Onyx？
3. [文档处理与索引准备](文档处理与索引准备.md)：连接器返回的文档在进入检索前，要经过哪些处理？
4. [混合检索与初召回](混合检索与初召回.md)：用户 Query（查询）进入后，关键词与向量检索怎样找出第一批候选？
5. [候选证据筛选与重排](候选证据筛选与重排.md)：初召回之后如何筛选证据？传统 Reranker 在当前版本是否仍是主流程？
6. [知识检索权限隔离](知识检索权限隔离.md)：员工提问时，怎样防止 HR 私有文档进入其检索结果和模型上下文？
7. [Agent 循环与对话状态](Agent循环与对话状态.md)：一轮用户提问内，模型推理、工具结果与对话状态怎样反复衔接？
8. [工具管理与 MCP 接入](工具管理与MCP接入.md)：企业动作怎样变成模型可用工具，并由 Runtime 调用外部系统？

各模块已初始化，仅记录简短介绍、理解与源码入口，后续一次推进一个问题；“我的笔记”由用户维护。
