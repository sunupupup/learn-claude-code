# pi-durable

构建“进程重启后还能恢复执行”的 Agent 应用


普通 session：
读回已有历史 → 用户说“继续” → 模型判断接下来做什么

Durable：
读回未完成的工具任务 → 检查恢复策略
    → 允许安全重跑：重新执行
    → 不允许：记录中断，交给模型处理


# Durable 的作用

1. 中断后继续执行、前端重新接回进度
2. 多个客户端看同一份进度
3. 避免重复提交任务


# 普通session重启

SessionManager.open(session文件)
    ↓
读取 JSONL → 恢复 entries → 建立父子索引
    ↓
buildSessionContext()
    ↓
沿当前分支、结合压缩记录，重建 messages
    ↓
new Agent({ initialState: { messages } })
    ↓
new AgentSession({ agent, sessionManager, ... })

```js
默认会话数据， 
const sessionDir = "~/.pi/agent/sessions/按工作目录编码的子目录/${时间戳_sessionId}.jsonl"

// ① 当前 Pi 的工作目录，用来定位历史会话目录。
const cwd = process.cwd();

// ② 计算 ~/.pi/agent/sessions/<编码后的工作目录>/。
const sessionDir = getDefaultSessionDir(cwd);

// ③ 在这个目录中选择最近修改的有效 .jsonl 文件。
const sessionFile = findMostRecentSession(sessionDir);

// ④ 打开该 JSONL 文件。
// 内部 loadEntriesFromFile() 分块读取文件，逐行解析成 entries。
const sessionManager = SessionManager.open(sessionFile!);

// ⑤ 根据 entry.id / parentId 找到当前分支，
// 再结合压缩摘要、保留边界等，转换成 messages。
const restored = sessionManager.buildSessionContext();

// ⑥ 创建一个新的 Agent，将旧消息作为它的初始对话状态。
// 这里省略模型、工具等其他初始化配置。
const agent = new Agent({
  initialState: {
    messages: restored.messages,
  },
});
```

# Durable的session重启

```js
// 新：这是基于原代码增量修改的对比伪代码。
// 新：保留原来的六步；新增的任务存储、调度和 runtime 函数
// 新：用于展示 Durable 的职责，不是可直接混用的真实库 API。

const cwd = process.cwd();

const sessionDir = getDefaultSessionDir(cwd);

const sessionFile = findMostRecentSession(sessionDir);

const sessionManager = SessionManager.open(sessionFile!);

const restored = sessionManager.buildSessionContext();

const agent = new Agent({
  initialState: {
    messages: restored.messages,
  },
});

// 新：读取这个会话对应的持久化执行记录。
// 新：这里沿用原版会话文件加载 messages；
// 新：真实 Durable 会将消息与任务统一接入自己的 Storage。
const taskStore = await openTaskStore(sessionManager.getSessionId());

// 新：恢复未完成任务及 checkpoint、取消标记、等待关系。
const records = await taskStore.loadLiveTasks();

// 新：恢复调度器，并明确绑定上面恢复出来的 agent 和会话。
// 新：后续任务使用的就是这个 agent，不是另一条独立执行链。
const scheduler = createRecoveryScheduler({
  taskStore,
  registry,

  createRuntime(record) {
    return createTaskRuntime({
      taskId: record.id,
      agent,
      sessionManager,
      taskStore,

      // 新：恢复后的模型任务通过这里取得同一 Agent 的消息。
      getMessages: () => agent.state.messages,

      // 新：后续产生的消息同步进入同一 Agent，并保存到会话。
      appendMessage(message) {
        agent.appendMessage(message);
        sessionManager.appendMessage(message);
      },
    });
  },
});

for (const record of records) {
  if (record.state.status === "running") {
    // 新：旧进程已经不存在，保留检查点，改为等待重新调度。
    record.state = {
      status: "pending",
      checkpoint: record.state.checkpoint,
    };

    await taskStore.save(record);
  }

  // 新：恢复任务集合，供调度器判断等待关系、取消和可执行状态。
  scheduler.restore(record);
}

// 新：启动恢复调度。
// 新：内部为可执行任务找到注册的任务定义及 checkpoint.phase，
// 新：再调用对应阶段，并传入上面绑定了 agent 的 runtime。
// 新：模型阶段读取 runtime.getMessages()，使用恢复的历史继续请求；
// 新：工具阶段读取检查点参数，按重放策略恢复工具调用；
// 新：产生的新消息通过 runtime.appendMessage() 回到同一会话。
await scheduler.resume();
```

# 框架层面和业务代码层面

首先，durable机制对于原harness侵入性很大

如果要把一个普通 Harness 改成“执行过程可恢复”，通常会比较有侵入性。因为运行代码必须在关键位置主动提交状态，不能只在启动时多加载一个对象。

而且，具体怎么恢复，恢复到业务内部的哪一步，通常需要这项业务自己定义

| Tool | 保存的中间态 | 恢复逻辑 |
|---|---|---|
| 搜索 | 搜索参数 | 重新搜索 |
| 部署 | 部署任务 ID | 查询这次部署是否完成，再决定继续等待还是结束 |
| 文件上传 | 上传 ID、已完成分片 | 查询已有分片，继续上传剩余部分 |

框架层面负责的可以归纳为四件事：
1. 存状态：保存任务输入、当前阶段、阶段数据和结果。
2. 读状态：重启后还原这些记录。
3. 识别未完成任务：判断哪些需要继续、等待或取消。
4. 调度恢复：根据任务类型和 checkpoint.phase，调用对应阶段函数。 （业务代码自定义任务需要自己注册）


# 我的看法

说实话，其实要是我们自己弄，倒是也能实现

但是框架层面，他提供了一种注册的机制，进行更好的恢复

但是 ，如果我们自己写

要同时 合并jsonl  数据 + 判断不完整性  + 恢复到中间态 + 后续执行

Pi Durable 替你提供状态存储、任务注册、未完成任务识别和恢复调度；你仍负责业务阶段，以及每阶段怎样安全继续。 使用 SQLite 等存储时，不一定需要自己回放 JSONL。

专业叫法
**任务状态持久化与恢复**

| 用途 | 名称 |
|---|---|
| 技术概念 | **持久化执行** |
| Harness 模块名称 | **任务状态持久化与恢复** |
| 描述具体能力 | **基于检查点的中断恢复** |