# Onyx：企业知识 Agent 整体链路

## 学习问题与范围

- 对应截图：EP01；进度：已初始化，源码入口已初步定位。
- 当前问题：从公司数据到有依据的回答，中间经过哪些模块？
- 本次只做模块介绍与入口分析，后续逐个小问题深入。

## 简单介绍与我的理解

以“客户为什么频繁投诉登录问题”为例，需要先找到 Slack 讨论、GitHub Issue 和内部文档，再组织答案或调用业务工具。本篇是整体地图，后续七篇分别放大其中一段。

**我的理解（学习概括）：**我把它理解为两条连接起来的链路：后台提前准备可检索的知识，前台在用户提问后运行 Agent。Context Layer（上下文层）负责提供可用资料；Runtime（运行时）负责模型与工具的循环，二者不是同一个模块。

## 源码位置与阅读方向

- [connector_document_extraction](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/background/indexing/run_docfetching.py#L514)（`backend/onyx/background/indexing/run_docfetching.py`）：观察后台拉取数据的入口。
- [run_indexing_pipeline](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/indexing/indexing_pipeline.py#L1711)（`backend/onyx/indexing/indexing_pipeline.py`）：观察文档如何准备为索引。
- [build_chat_turn](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/chat/process_message.py#L575)（`backend/onyx/chat/process_message.py`）：准备用户本轮对话所需的模型、工具和上下文。
- [run_llm_loop](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/chat/llm_loop.py#L769)（`backend/onyx/chat/llm_loop.py`）：执行模型与工具循环；引用状态也在这条链路中管理。

教学概括：数据源 → 同步 → 索引准备；用户提问 → 对话准备 → 模型/工具循环 → 回答与引用。不是已完成运行验证的完整调用图。

- 下一小步：先找到一次用户请求进入聊天后端的位置，再追它怎样建立 ChatTurnSetup。

## 源码与证据

- 固定 Commit：`32c08fb95c3b829570466258958bbc8b3f129ad7`；读取日期：2026-10-15。
- 本地源码：`D:\code\third-party-labs\agent\source-reading\onyx`；位于学习仓库外。
- 证据状态：所列文件和符号已静态核验；完整模块调用链、部署与运行效果待验证。
- 边界与待验证：这八篇是学习主题，不是八个一一对应的源码包；引用来源也不等于已经证明答案正确。
- [项目入口与版本、许可证说明](README.md)。

## 问题验收

1. 以“客户频繁投诉登录问题”为例，请串起从企业数据到最终回答的主要环节，并区分哪些发生在后台同步时、哪些发生在用户提问后。
2. 上下文层与 Agent 运行时各自负责什么？如果回答附有文档引用，为什么仍不能仅凭引用认定答案正确？

## 我的笔记

