# 我的笔记

用户点击了中断，应该是发送一个cancel请求，一般有个 agent_runs 这张表
Agent 执行任务表，例如 agent_runs

然后将其中的一个 run_id 的状态标记为取消

然后agent 代码，在关键地方，时刻检查这个状态

这边就是在做清理工作, 业务工具补偿策略

```js
if user_clicked_stop:
   # 重复停止、重复 Hook、重复恢复和重复外部撤销都不得增加业务副作用。
   harness.request_cancel(operation_id)
   harness.tool_result_hook(operation_id)
   harness.recover()
   external.cancel_booking(operation_id)
   external.create_booking(operation_id)
   external.finish_create(operation_id)
```

```js
def cancel_booking(self, operation_id):
   if self.fail_next_cancel:
      self.fail_next_cancel = False
      raise RuntimeError('模拟撤销失败，预约仍有效')
   # 【幂等补偿】只有 ACTIVE -> CANCELLED 才增加副作用计数。
   # 同一 operation_id 反复撤销，最终仍然只撤销一次。
   with self.db:
      self.db.execute("UPDATE bookings SET status='CANCELLED', cancel_effects=cancel_effects+1 "
                        "WHERE operation_id=? AND status='ACTIVE'", (operation_id,))
   trace(operation_id, 'external.cancel_applied', **self.query(operation_id))
   if self.lose_next_cancel_response:
      self.lose_next_cancel_response = False
      raise RuntimeError('模拟撤销已生效，但响应丢失')
```

# Agent 取消与业务补偿：最小实战

学习目标：通过错误与正确版本对照，理解“停止 Agent 不等于撤销业务操作”。Hook 补偿、恢复与重试是一套机制，共用同一个 `reconcile()`，不分成三个工程。

需要 Python 3.10+，没有第三方 Python 依赖。完整 Demo 默认使用真实 DeepSeek 模型：模型查询时间、选择创建工具、接收工具结果并继续循环。预约后端和前端文案仍用本地模拟；打断、外部完成和失败均由代码赋值与函数调用确定顺序，不需要真实等待 500 毫秒。

模型客户端复用 [订单客服的 model.py](../order-support-agent/order_support_agent/model.py)。配置优先环境变量，其次本项目 `.env`；本项目没有 `.env` 时复用 `../order-support-agent/.env`。可复制 `.env.example` 为 `.env` 并填写密钥。真实运行会消耗模型调用额度。

## Agent 从哪里开始运行

打开 [demo_02_complete.py](./demo_02_complete.py)，先搜索 **`def run_agent`**。这是实际的模型—工具循环；`run_scenario()` 负责组装环境与恢复验证，文件底部 `__main__` 负责命令行启动。

```text
__main__ → 加载真实模型 → run_scenario() → run_agent()
                                             │
                    ┌── model.complete(messages, TOOLS)
                    │         ↓ 模型返回 assistant.tool_calls
                    │   校验参数，执行 search_slots / create_booking
                    │         ↓ 创建执行期间直接赋值模拟停止
                    │   工具完成 → tool_result_hook() → reconcile()
                    │         ↓
                    └── role=tool 结果写回 messages → 下一轮模型
                              用户已停止时：结束模型循环

跳过 Hook / 补偿失败 → 重开数据库 → recover() → 同一个 reconcile()
```

停止的是后续模型调用和新工具派发；已发出的创建请求仍执行完成，Harness 继续补偿。`cancel_booking` 由可信的协调代码调用，不交给模型决定是否撤销。

## 运行

在仓库根目录执行（`-X utf8` 用于 Windows 中文输出）：

```powershell
python -X utf8 practice/agent-cancellation-demo/demo_01_wrong.py
python -X utf8 practice/agent-cancellation-demo/demo_02_complete.py hook
python -X utf8 practice/agent-cancellation-demo/demo_02_complete.py recovery
python -X utf8 practice/agent-cancellation-demo/demo_02_complete.py retry
```

正常预约可以看到完整的模型—工具—模型循环：

```powershell
python -X utf8 practice/agent-cancellation-demo/demo_02_complete.py normal
```

一次用真实模型验证所有场景：

```powershell
python -X utf8 practice/agent-cancellation-demo/demo_02_complete.py all
```

没有密钥时可以显式离线验证（脚本模型，仅验证控制流程）：

```powershell
python -X utf8 practice/agent-cancellation-demo/demo_02_complete.py all --offline
```

每个场景结束出现 `validation.passed` 即代表对应断言通过；错误 Demo 以“错误复现成功”结束。每次运行创建临时 SQLite 数据库，场景结束自动清理，不覆盖其他项目的数据。

## 直接找到关键代码

完整代码集中在 [demo_02_complete.py](./demo_02_complete.py)，可以搜索下列中文标记或函数名：

| 关注点 | 函数 / 标记 | 阅读内容 |
|---|---|---|
| **Agent 主循环** | `run_agent()` / `【真正的 Agent Loop 主入口】` | 请求真实模型、派发工具、回传结果、下一轮或停止 |
| 创建工具执行 | `Harness.start()` / `【真实工具执行位置】` | 模型返回创建调用后，Harness 保存操作 ID 并执行 |
| 点击停止 | `Harness.request_cancel()` / `【取消意图】` | 取消意图先落盘，界面仍显示正在确认 |
| **Hook 补偿** | `run_agent()` 中的 `【Hook 补偿调用位置】`、`Harness.tool_result_hook()` | 工具返回后在实际 loop 中触发统一协调逻辑 |
| 共同的补偿决策 | `Harness.reconcile()` / `【Hook / 恢复共用的补偿逻辑】` | 查询外部结果、等待、撤销、确认最终状态 |
| **恢复与重试** | `Harness.recover()` / `【恢复与重试入口】` | 扫描 SQLite 中尚未完成的取消操作，再调用同一协调逻辑 |
| **失败后的重试** | `reconcile()` 中的 `【重试保留点】` | 保留取消意图，把失败留给下次恢复处理 |
| 幂等撤销 | `ExternalSystem.cancel_booking()` / `【幂等补偿】` | 重复请求只增加一次真实撤销副作用 |
| 模拟各种打断 | `run_scenario()` / `【模拟打断：直接赋值】`、`【模拟 Hook 未运行】`、`【模拟重试】` | 修改变量或单独运行场景观察差异 |

推荐顺序：错误 Demo → `normal` → `hook` → `recovery` → `retry` → `response_lost`。先读 `run_agent()`，再沿调用进入 Hook、`reconcile()` 和 SQLite 操作。

## 状态与职责

```text
BOOKING ──正常创建成功──> BOOKED
   │ 用户停止
   ▼
CANCEL_REQUESTED ──外部结果未定──> 保持等待
   │ 外部确认创建成功
   ▼
COMPENSATING ──确认撤销成功──> CANCELLED
   │ 调用失败 / 响应丢失
   ▼
CANCEL_FAILED ──恢复扫描──> reconcile() 重新查询并决定是否补偿
```

如果外部确认创建最终失败，没有有效预约，取消请求可以直接进入 `CANCELLED`。外部查不到记录只算 `UNKNOWN`，不能证明以后不会创建成功。

`CANCEL_FAILED` 表示本次补偿调用未获得成功确认，业务可能仍有效，也可能已撤销；界面显示“取消结果未确认，需要重试或人工处理”。外部业务状态与工作流状态是两套记录，不能混为一谈。

| 层次 | 本 Demo 的职责 |
|---|---|
| 模型（默认真实 DeepSeek） | 根据用户确认选择工具、读取工具结果后回答；不决定业务最终状态 |
| Harness（Agent 运行协调代码） | 持久化取消意图、运行 Hook、恢复扫描，依据外部事实决定工作流及界面状态 |
| 工具后端 / 外部系统 | 接受请求、完成创建、查询结果、幂等撤销；拥有预约是否有效的业务事实 |

Hook（钩子）是工具结果返回后的回调入口；恢复是在没有旧回调和旧内存对象时重新处理持久记录；重试是再次处理未完成操作。幂等指同一操作重复执行，业务效果不重复。`operation_id` 是稳定操作标识，串联创建、查询、补偿及 Trace（执行事件记录）。

## 场景与验收

| 参数 | 注入情况 | 必须观察 / 检查 |
|---|---|---|
| `normal` | 不停止 | 最终 `BOOKED` / 外部 `ACTIVE`，创建 1 次、撤销 0 次 |
| `hook` | 执行中停止 | `CANCEL_REQUESTED → COMPENSATING → CANCELLED`，创建和撤销各 1 次 |
| `recovery` | 外部创建成功后跳过 Hook，关闭并重开两方数据库 | `simulation.restart_from_sqlite`、`recovery.retry_or_resume`；取消意图保留，最终撤销 1 次 |
| `retry` | 第一次撤销在生效前失败 | `compensation.error` 后状态 `CANCEL_FAILED` 且预约仍有效；重开 Harness 后恢复成功 |
| `pending` | 创建尚未结束时先恢复一次 | 仍为 `CANCEL_REQUESTED` / 外部 `PENDING`；以后创建成功才补偿 |
| `create_failed` | 外部确认创建最终失败 | 最终 `CANCELLED` / 外部 `FAILED`，无创建、撤销和提醒副作用 |
| `response_lost` | 撤销已生效，返回响应丢失 | 工作流暂为 `CANCEL_FAILED`、外部已为 `CANCELLED`；恢复查询确认，撤销计数仍为 1 |

取消场景还会重复触发停止、Hook、恢复、外部创建及撤销，检查终态不倒退，副作用计数不增加。每条 Trace 带 `operation_id`；重点看 `workflow.state` 的前后状态和 `reconcile.query` 的外部事实，不能只看工具调用记录。

## 已验证与边界

🟢 离线控制流程已验证：错误示例以及完整版本全部 7 个场景，断言检查工作流、外部业务结果、创建 / 撤销 / 提醒计数。恢复使用关闭连接、丢弃对象后重开 SQLite，验证持久状态可重新加载。真实模型运行验证见 [实现记录](../../specs/implementation/I-2026-006-agent-cancellation-demo.md)。

教学简化：没有真实进程杀死、网络并发、后台定时任务和真实网页；恢复与重试由代码手动触发。`operation_id` 同时作为创建和撤销的去重依据，没有实现参数冲突检查。生产扩展需要调度、退避及重试上限、人工接管、多执行者并发控制，以及外部接口契约核验；本 Demo 不提供这些保证。

补偿不是完整回滚：创建时发送的提醒计数不会因为撤销而归零，已经发生的通知无法自动收回。

相关课程：[工具调用](../../s02_tool_use/README.md)、[Hook](../../s04_hooks/README.md)、[错误恢复](../../s11_error_recovery/README.md)。
