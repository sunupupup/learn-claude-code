# 订单客服 Agent

通过一个订单售后场景，逐步学习如何让模型调用业务工具，以及如何由程序控制授权、执行和恢复。

目标场景：

> 昨天买的耳机还没发货，我周五就要出差了。能赶上就催一下，赶不上就退款。

完整学习背景与分阶段计划见 [Notion：案例——订单 Agent 处理用户退款](https://app.notion.com/p/Agent-3efd850183c580afa4b5f2371026b99c)。本目录维护实际实现与验证进度，不复制整份讨论笔记。

## 当前状态

- 阶段 1 与阶段 2 已实现：CLI、React 网页、真实 DeepSeek 流式回复、订单选择、工具卡片、模拟催单与退款确认。
- 后端使用 Python 标准库；前端使用 React + TypeScript + Vite。
- 使用固定用户和本地模拟订单，没有真实交易或登录系统；尚无持久化与独立 mock server。

## 分阶段实现文档

从 [docs 阶段索引](./docs/README.md) 按顺序进入各步骤。每份文档包含学习目标、功能清单、验收标准、阶段边界与验证记录。

第一步是 [阶段 1：最小模型与工具循环](./docs/01-agent-loop.md)。

阶段功能与验收要求统一维护在对应步骤文件。本 README 后续维护项目入口和实际运行说明，遵循 [实战区实践方式](../README.md#实践方式)。

开发与验收前先看 [用户故事](./docs/user-stories.md)：具体输入、预期交互、工具调用和禁止行为。

## 一键启动前后端

需要 Python 3.11+、Node.js 22.12+（含 npm），首次安装前端依赖需要联网。

Windows 下双击本目录的 [start.cmd](./start.cmd)，或在本目录运行：

```powershell
python start.py
```

脚本检查本地密钥配置，安装锁定的前端依赖、检查 TypeScript、构建页面，启动 Python 服务并打开 [本地网页](http://127.0.0.1:8765)。再次启动时，依赖和前端源码未变化就跳过安装和构建。关闭启动窗口或 Ctrl+C 停止服务；端口已被使用时不会自动结束其他进程。

可选参数：python start.py --no-open 不打开浏览器；--port 8766 更换端口。前后端由同一个本地地址提供，不需要另开前端常驻进程。

本机已有 .env；其他环境首次使用时复制 .env.example 为 .env 并填写密钥。不要把密钥放入前端或提交 Git。

### 从这些故事开始体验

1. “昨天买的耳机发货了吗？” → 两笔候选订单 → 点击一笔继续。
2. “白色耳机明晚20点前能收到吗？能到就帮我催一下。” → 查物流 → 催单确认。
3. “黑色耳机不需要了，帮我申请退款。” → 查规则 → 核对 299 元 → 取消或确认。
4. “充电线明晚20点前能到吗？” → 无预计时间 → 解释无法判断。
5. “定制键帽帮我退款。” → 规则缺失 → 人工处理入口（仅演示说明）。

工具卡片可展开参数和结果；等待选择或确认时输入框暂停使用。确认后的申请编号来自后端。每个新会话使用独立模拟订单副本，便于重复实验；刷新可恢复当前进程里的会话，重启服务后会话失效，页面会提示新建。

## 阶段 1 命令行入口

CLI 保留阶段 1 的查询能力，不加载网页售后工具。运行时只使用标准库，无需安装 Python 依赖。以下命令在本子项目目录执行。

首次配置：不存在 .env 时复制 .env.example 为 .env，填写 DEEPSEEK_API_KEY；已有文件不要覆盖。模型默认 deepseek-flash，环境变量优先于 .env。真实密钥文件已被 Git 忽略。

```powershell
python -m order_support_agent --query "查一下我昨天买的耳机，多少钱，发货了吗？"
```

连续对话并查看链路：

```powershell
python -m order_support_agent --debug
```

依次输入“帮我查一下订单。”、“昨天买的耳机。”，最后输入 exit 退出。正常答案输出到 stdout；--debug 将脱敏的模型消息和工具事件输出到 stderr，不包含认证请求头。

固定用户 demo-user-001 有一笔昨天购买的白色无线耳机订单，399 元、未发货。业务日期按启动时的上海日期生成。另一用户的订单仅用于隔离验证，不返回当前用户。

一次交互进程是一段内存会话，退出后历史丢失；每次 --query 都是新会话。每次输入最多调用模型 6 次，尚不是跨重启、跨请求的任务预算。

## 验证

离线测试不需要密钥或网络：

```powershell
python -m unittest discover -s tests -v
```

真实模型用户故事检查会产生 API 调用：

```powershell
python tests/live_stories.py
```

脱敏事件与回答保存在被 Git 忽略的 .local/。结构化断言通过后仍需检查回复含义。实际结果见 [阶段 1 验收记录](./docs/validation/stage-01.md)。

启动网页服务后，可执行真实阶段 2 故事检查（产生 API 调用）：

```powershell
python tests/live_stage_two.py
```

前端单独验证：npm --prefix frontend run build。完整结果见 [阶段 2 验收记录](./docs/validation/stage-02.md)。

## 代码阅读顺序

| 文件 | 阅读重点 |
|---|---|
| [loop.py](./order_support_agent/loop.py) | run_turn 如何消费模型输出、分发工具并决定继续或结束 |
| [context.py](./order_support_agent/context.py) | 保存调用与结果，snapshot 提供实际模型输入 |
| [tools.py](./order_support_agent/tools.py) | 工具定义、参数校验与可信身份传递 |
| [mock_orders.py](./order_support_agent/mock_orders.py) | 先限定归属，再筛选并返回订单 |
| [model.py](./order_support_agent/model.py) | HTTP 请求、响应校验和错误处理 |
| [main.py](./order_support_agent/main.py) | 配置、CLI 与内存会话入口 |

设计理由见 [阶段 1 设计](./docs/plans/2026-10-07-stage-one-design.md)。关键逻辑配有中文注释。

阶段 2 从 [server.py](./order_support_agent/server.py) 的 HTTP/SSE 接口进入，复用 loop；[business.py](./order_support_agent/business.py) 管理选择与确认，[App.tsx](./frontend/src/App.tsx) 展示交互，[api.ts](./frontend/src/api.ts) 解析流式事件。参见 [阶段 2 设计](./docs/plans/2026-10-07-stage-two-design.md)。
