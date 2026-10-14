# Chatwoot

可自部署的多渠道客服平台，提供共享收件箱、网站在线聊天、帮助中心与 Captain AI 客服。后续围绕 Captain 学习客服业务如何与 Agent 执行机制衔接。

- 官方仓库：[chatwoot/chatwoot](https://github.com/chatwoot/chatwoot)。
- 本次研究范围：Captain 客服 Agent 及其与 Conversation、后台任务和人工客服的连接；具体源码子路径待定位。
- 客服平台学习只选择本项目，先沿同一条主线学习。
- 许可证：[根 LICENSE](https://github.com/chatwoot/chatwoot/blob/develop/LICENSE) 说明一般内容适用 MIT Expat，`enterprise/` 适用该目录独立许可证，第三方组件按各自许可；Captain 所涉代码的许可边界待定位后确认。
- 资料读取日期：2026-10-15；已读官方介绍和根许可证，源码版本 / Commit 待正式学习时固定。

## 学习模块

九个独立模块按以下顺序学习，目前均已初始化、待学习。

1. [客服消息进入Agent](客服消息进入Agent.md)：消息如何进入 Agent？
2. [Agent循环与对话状态](Agent循环与对话状态.md)：Agent Loop 如何运行？
3. [Scenario与多Agent协作](Scenario与多Agent协作.md)：多 Agent 如何拆 Scenario？
4. [Agent上下文组织](Agent上下文组织.md)：Agent 上下文如何组织？
5. [工具管理与执行](工具管理与执行.md)：工具如何真正执行？
6. [转人工与会话归属](转人工与会话归属.md)：什么时候转人工？
7. [Agent记忆分层](Agent记忆分层.md)：Memory 如何分层？
8. [Agent评估闭环](Agent评估闭环.md)：Agent Eval 如何形成闭环？
9. [客服Agent生产架构](客服Agent生产架构.md)：生产级 Agent 完整架构？

模块中的“我的笔记”由用户维护，后续一次推进一个小问题。
