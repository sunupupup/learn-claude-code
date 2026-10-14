# Web Agent 中 Ask User Question 的断线恢复笔记

## 一、问题现象

在前后端 Agent 对话中，Agent 有时会进入 `ask_user`，等待用户回答或审批。若用户此时刷新页面，可能出现：

- 问题卡片显示异常或消失；
- 后端仍在等待，但新页面找不到这次等待；
- 用户无法继续回答；
- 需要多次刷新才能恢复；
- 新旧连接同时更新状态，出现竞态。

## 二、核心结论

```text
浏览器连接可以断开，Agent 的等待状态不能丢失。
刷新不是业务失败；超时、取消或无法恢复才是失败。
```

必须把两个生命周期分开：

```text
浏览器连接：CONNECTED → DISCONNECTED → RECONNECTED
Agent Run：  RUNNING → WAITING_FOR_USER → RUNNING → COMPLETED
```

SSE、WebSocket 或流式 HTTP 只是事件传输通道，不应该成为 Agent Run 的唯一状态载体。

## 三、不推荐的处理方式

### 3.1 页面断开后立即写错误消息

页面刷新不代表工具错误或 Agent 失败。立即向对话写入 error 会污染消息历史，并可能让模型误判任务失败。

连接断开可以写入 Trace 或技术日志：

```text
client_disconnected
client_reconnected
```

但不应默认伪装成对话中的 `tool_result` 错误。

### 3.2 一直保持同步阻塞

CLI Demo 可以使用 `input()` 阻塞线程。Web 服务如果把等待状态只放在进程内存中的 Promise、Future 或线程里，会遇到：

- 浏览器刷新后无法重新关联；
- Worker 重启后状态丢失；
- 长时间占用线程或连接；
- 多实例环境无法确定应该连接哪台机器。

## 四、推荐状态模型

Agent Run：

```text
RUNNING
  ↓ 需要用户输入
WAITING_FOR_USER
  ├─ 用户回答 → RESUMING → RUNNING
  ├─ 用户拒绝 → RUNNING 或 CANCELLED
  ├─ 等待超时 → EXPIRED / FAILED
  └─ 用户取消 → CANCELLED
```

Pending Interaction：

```text
PENDING → ANSWERED
        → REJECTED
        → EXPIRED
        → CANCELLED
```

`QUESTION` 与 `APPROVAL` 可以共用 `WAITING_FOR_USER`，但业务语义不同：

- `QUESTION`：补充缺失信息；
- `APPROVAL`：授权一个有副作用的具体动作。

## 五、需要持久化的数据

一次等待记录至少需要：

```text
pending_interaction
├─ id
├─ run_id
├─ session_id
├─ tool_use_id
├─ kind: QUESTION | APPROVAL
├─ status: PENDING | ANSWERED | REJECTED | EXPIRED
├─ question
├─ tool_name
├─ tool_args_hash
├─ user_id
├─ tenant_id
├─ created_at
├─ expires_at
└─ version
```

敏感工具参数不一定要完整明文存储，可以保存受保护的快照或引用，并用参数哈希保证“审批的动作”和“最终执行的动作”一致。

`tool_use_id` 只负责工具调用与结果的协议配对，不能代替用户、session、run 或 tenant 的鉴权。

## 六、后端进入等待状态的流程

```text
模型返回 tool_use / ask_user
→ 持久化完整 assistant message
→ 创建 pending_interaction(PENDING)
→ Run 改为 WAITING_FOR_USER
→ 保存 checkpoint 或可恢复消息历史
→ 提交事务
→ 发布 ask_user 事件
→ Worker 释放，不必永久阻塞线程
```

持久化必须发生在发布前，否则前端可能先收到事件，刷新后却查不到对应记录。

## 七、页面刷新后的恢复流程

前端挂载时应遵循：

```text
1. 查询 conversation/run 快照
2. 恢复历史 messages
3. 查询 pending_interaction
4. 如果 Run 为 WAITING_FOR_USER，重新渲染提问或审批卡片
5. 获取最后一个 event cursor
6. 再建立 SSE/WebSocket，订阅后续增量事件
```

记忆句：

```text
先恢复快照，再订阅增量。
```

如果前端只依赖实时 `ask_user` 事件，而不查询服务端当前状态，刷新期间很容易漏掉事件。

## 八、用户回答后的恢复流程

```text
POST /pending-interactions/{id}/answer
→ 验证当前 user、tenant 和 run
→ 检查状态仍为 PENDING
→ 检查参数哈希与版本
→ 原子更新为 ANSWERED 或 REJECTED
→ 保存用户输入或构造 tool_result
→ 使用原 tool_use_id 配对
→ 投递一次 resume job
→ Run: WAITING_FOR_USER → RESUMING → RUNNING
```

回答接口必须幂等。重复点击、网络重试或多个页面同时回答时，只能有一个请求成功触发恢复，不能重复执行工具。

## 九、什么时候才写错误结果

正常刷新和临时断线不应产生工具错误。以下情况才适合结束等待并返回错误结果：

- 超过审批或回答有效期；
- 用户明确取消；
- checkpoint 无法恢复；
- Pending 数据损坏；
- 对应工具、Prompt 或 Agent 版本已无法兼容恢复。

示例语义：

```text
error_code = user_input_expired
message = User input request expired before a response was received.
```

## 十、最小可行修复

如果暂时不引入完整 Durable Execution（耐久执行），至少实现：

1. 后端持久化 pending question / approval；
2. Run 增加 `WAITING_FOR_USER` 状态；
3. 页面刷新时主动查询 pending interaction；
4. 用户回答接口支持幂等和状态版本检查；
5. 回答后通过队列或可靠任务机制恢复 Agent；
6. 设置超时、取消和清理逻辑；
7. 对断开、恢复、重复回答和最终工具执行记录 Trace。

## 十一、验收用例

1. Agent 提问后立即刷新，问题卡片能恢复；
2. 刷新多次，始终只有一个 Pending 记录；
3. 两个页面同时回答，只恢复一次 Run；
4. SSE/WebSocket 断开重连，不漏事件、不重复显示；
5. Worker 在等待期间重启，仍可恢复；
6. 回答过期后不能继续执行原工具；
7. 审批后工具参数发生变化，系统拒绝复用旧审批；
8. 用户 A 无法回答用户 B 或其他 tenant 的 Pending；
9. 页面断开只写技术日志，不向对话伪造 error；
10. 恢复后生成的 `tool_result` 与原 `tool_use.id` 正确配对。

## 十二、待结合真实项目确认

- 当前通信方式是 SSE、WebSocket 还是流式 HTTP；
- Pending 状态目前保存在前端、后端内存还是数据库 / Redis；
- Agent 是否已有 checkpoint 或可重放的完整消息历史；
- 回答接口是否有幂等键、状态版本和租户鉴权；
- 多实例部署时由谁负责恢复等待中的 Run。
