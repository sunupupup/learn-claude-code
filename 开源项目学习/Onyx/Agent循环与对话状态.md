# Onyx：Agent 循环与对话状态

## 学习问题与范围

- 对应截图：EP07；进度：已初始化，源码入口已初步定位。
- 当前问题：一轮用户提问内，模型推理、工具结果与对话状态怎样反复衔接？
- 本次只做模块介绍与入口分析，后续逐个小问题深入。

## 简单介绍与我的理解

Turn（对话轮次）对应一次用户输入及其处理；Step（步骤）是轮次内的一次模型调用；State（状态）保存本轮处理所需的信息。Agent Loop（智能体循环）在模型与工具之间协调执行。

**我的理解（学习概括）：**模型提出工具调用意图，Runtime 执行工具，把结果放回后续模型输入。不是每次提问都只调用一次模型，也不是每个 Step 都开启新会话。

## 源码位置与阅读方向

- [build_chat_turn](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/chat/process_message.py#L575)（`backend/onyx/chat/process_message.py`）：准备本轮设置和上下文；同文件负责流式处理与完成收尾。
- [construct_message_history / run_llm_loop](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/chat/llm_loop.py#L769)（`backend/onyx/chat/llm_loop.py`）：阅读循环中的历史重建、run_llm_step 和 run_tool_calls 调用。
- [run_llm_step](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/chat/llm_step.py#L1312)（`backend/onyx/chat/llm_step.py`）：观察单次模型调用的封装与输出处理。
- [ChatStateContainer / ChatTurnSetup](https://github.com/onyx-dot-app/onyx/blob/32c08fb95c3b829570466258958bbc8b3f129ad7/backend/onyx/chat/chat_state.py#L33)（`backend/onyx/chat/chat_state.py`）：区分本轮设置与持续变化的状态容器。

已定位：构建本轮 → 重建模型消息 → run_llm_step → run_tool_calls → 更新工具结果、引用与历史 → 继续或收尾。

- 下一小步：先追一次内部搜索工具调用如何返回下一次模型输入，再看停止、失败与保存边界。

## 源码与证据

- 固定 Commit：`32c08fb95c3b829570466258958bbc8b3f129ad7`；读取日期：2026-10-15。
- 本地源码：`D:\code\third-party-labs\agent\source-reading\onyx`；位于学习仓库外。
- 证据状态：所列文件和符号已静态核验；完整模块调用链、部署与运行效果待验证。
- 边界与待验证：当前是固定版本静态阅读；取消信号、循环上限、并发及恢复行为尚未逐项验证。
- [项目入口与版本、许可证说明](README.md)。

## 问题验收

1. 一次提问触发搜索后继续回答时，Turn、Step、工具执行与 State 分别对应什么？请指出模型调用和工具执行的源码入口。
2. 工具结果怎样回到下一次模型输入？请根据源码说明继续循环与收尾的判断位置，并区分本轮状态更新和聊天持久化。

## 我的笔记

