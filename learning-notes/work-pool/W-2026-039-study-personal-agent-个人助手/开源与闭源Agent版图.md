# 开源与闭源 Agent 版图

记录日期：2026-11-07。这是专栏的初稿，用来选学习对象，不是市场排名。

## 今天核验到哪一步

本机 `https_proxy` 指向 `127.0.0.1:7890`。实测 HTTP 请求返回 502，HTTPS 在 TLS 握手时中断，`gh api` 同样失败。所以今天没有打开 GitHub 或各产品官网，没有新的星标、许可证、收购或下线结论。

证据分成两档：

- **仓库已记录**：本仓库早先笔记写过，并带有当时的日期或版本。今天没有复核，不能当成 2026-11-07 的现状。
- **常见候选**：按公开产品形态做的分类草稿。未在今天打开官网，是否仍活跃、是否已经开源、功能是否如传闻，都标为待核验。

## 先分成四类

| 类别 | 主要用户 | 怎样算做成了 | 容易混进去的东西 |
| --- | --- | --- | --- |
| 个人助手 | 某一个人和他的日常事务 | 接住他的渠道，记住该记的，该安静时不打扰，行动可核对 | 把任何聊天产品都叫个人助手 |
| 编程 Agent | 写代码的人，工作对象是仓库 | 改动、命令和测试对得上 | 个人助手里顺手调用的编程能力 |
| 业务 Agent | 组织的客户或员工 | 按业务规则答对或办完，该转人工时停下 | 用同一个框架做的另一种产品 |
| 框架 / SDK | 开发者 | 提供循环、工具、状态等零件 | 框架自带的演示，不等于成品助手 |

开源表示能读实现并按许可证自己部署。闭源表示主要使用厂商托管的产品。同一家公司可以一边开源 CLI，一边把桌面端或模型保持闭源，不能用一个标签概括全部。

## 个人助手

### 仓库已记录

| 名字 | 源码 | 本仓库当时怎么写 | 证据停在 |
| --- | --- | --- | --- |
| OpenClaw | 开源，仓库 `openclaw/openclaw` | 自托管、多渠道，Gateway 常驻，有记忆检索 | [记忆笔记](../W-2026-013-study-memory-production-practices-Memory/个人助手Agent开源项目与记忆层级.md) 2026-09-23；[Prompt 笔记](../W-2026-032-study-agent-context-organization-and-prompt-cache-Context缓存/开源项目缓存设计/OpenClaw.md) 2026-09-26 |
| Hermes Agent | 开源，`NousResearch/hermes-agent` | 自托管，CLI、桌面和消息渠道，强调记忆、工具、Skill | 同上两份笔记 |
| Nanobot | 开源，`HKUDS/nanobot` | Python 个人助理；笔记固定 `v0.3.5`、commit `1bb712d`、MIT | [Nanobot 笔记](../W-2026-032-study-agent-context-organization-and-prompt-cache-Context缓存/开源项目缓存设计/Nanobot.md) |

这三份都是为了看提示词或记忆，不是个人助手产品的完整验收。

### 常见候选，今天未打开官网

闭源托管，通常被当作通用或个人助理产品：ChatGPT、Claude、Gemini、Microsoft Copilot、Apple 智能与 Siri、Manus、Genspark、Perplexity、Lindy、Notion 里的 AI。它们的记忆、定时任务、电脑或浏览器操作是否仍在、面向哪些地区，待核验。

开源或可自托管、但更靠个人知识库或本机操作，不一定是多渠道助手：Khoj、Open Interpreter。AstrBot 在 [W-028](../../../specs/work-pool/W-2026-028-study-conversational-agent-application-capabilities.md) 里是聊天机器人平台样本，可以承载伙伴或助手，本身不等于已经证明的个人助手。

## 编程 Agent

本仓库已经在看的：

- [Pi Coding Agent](../../../开源项目学习/Pi%20Coding%20Agent/README.md)，开源终端编程 Agent。
- [Codex](../../../开源项目学习/Codex/README.md)：笔记写的是公开 CLI 与 app-server 可观察，桌面端行为另核。
- [dsh-superagent](../../../开源项目学习/dsh-superagent/README.md)：DeepSeek Harness 的编程 Agent 研究原型，接入 GitHub 与可选飞书。

常见开源候选，今天未复核：OpenHands、Aider、Cline、Continue、Goose、OpenCode、SWE-agent、mini-swe-agent。mini-swe-agent 在总路线里被指定过，不表示本专栏要重读。

常见闭源候选，今天未复核：Cursor、Devin、GitHub Copilot、Replit Agent、JetBrains Junie、Amazon Q。Windsurf / Cascade 的归属变动过，不写入当前归属。

## 业务 Agent 与框架

业务方向，本仓库已有入口、不等同于个人助手：

- [Chatwoot](../../../开源项目学习/Chatwoot/README.md)：可自部署客服。
- [Onyx](../../../开源项目学习/Onyx/README.md)：企业知识搜索与问答。

闭源客服候选，今天未复核：Sierra、Intercom Fin，以及各云厂商的客服 AI。

框架候选，今天未复核：LangGraph、OpenAI Agents SDK、Claude Agent SDK、Google ADK、Mastra、smolagents、Pydantic AI。CrewAI 与 AutoGen 已有 [W-033](../W-2026-033-study-crewai-autogen-multi-agent-collaboration/LEARNING_NOTES.md)，不在本专栏重学。

## 这张表现在不能支持的结论

- 不能按名单长度说开源或闭源更强。
- 不能把 9 月笔记里的记忆、Skill 行为当成 11 月源码。
- 不能选出「最好的个人助手」。下一步只需要选一个开源样本，用来看一条消息链路。
