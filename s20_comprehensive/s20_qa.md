# s20 综合 Agent 代码问答

这是一份基于 `s20_comprehensive/code.py` 的自测题。先独立阅读代码，再用自己的话回答；不要只复述函数名。建议先完成第一组，之后再继续。

## 一、主循环

### 1. 每轮准备工作

`agent_loop()` 每一轮开始时，为什么要先处理 cron、后台通知和 todo reminder，再调用模型？

我的回答：因为  cron、后台通知和 todo reminder 通常代表某些 任务、线程的结果，需要塞入到messages中，告诉模型某些事已经完成了，这样可以有更进一步的规划、或者临时理解一些外部注入的信息

### 2. 模型调用前的上下文准备

`prepare_context(messages)` 为什么必须放在 `call_llm()` 之前？

我的回答：这个是负责context压缩的，他是对 call_llm 的入参处理

### 3. 核心反馈循环

用自己的话解释这一条链：

```text
response → tool_use → execute → tool_result → next round
```

我的回答：这个其实就是模型读取到了上下文和系统提示词，发现用户的任务，必须要通过某些tool的执行才能完成，所以会先回复一些 tool_use 的调用请求，然后harness层收到相关数据，在本地调用tool，然后再把结果交给模型，让模型进行下一步操作

### 4. 继续信号

代码为什么使用 `has_tool_use(response.content)`，而不是只判断 `response.stop_reason == "tool_use"`？

我的回答：因为后续处理数据那块，用的是 response.content ， 没法默认判断“tool_use的时候content 肯定包含 tool_use block”

### 5. assistant 消息的保存时机

为什么要先把 assistant response 追加到 `messages`，再判断是否有 `tool_use`？

我的回答：

### 6. 多工具调用

一次模型响应里出现两个 `tool_use` block 时，代码如何保证每个调用都对应自己的 `tool_result`？

我的回答：通过tool id来进行标记，tool result的block中会添加对应的 tool_id 字段

### 7. 停止条件

如果模型没有产生 `tool_use`，主循环在哪里结束？哪个 hook 会被触发？

我的回答：会在 类似于 has_tool_use(message.content) 的地方中断，这时候代表这一次loop快结束了，会调用 Stop 相关的 hook

## 二、权限与 hooks

### 8. hook 与 handler 的边界

`PreToolUse` hook 和具体工具 handler 的职责有什么区别？

我的回答：PreToolUse 是 harness 额外加的， 他是在 handler 之前做一些权限、日志等通用的逻辑而 handler 的职责一般负责真实的业务代码了、以及执行业务代码之前的必要的校验

### 9. 拒绝 bash

如果 `permission_hook()` 拒绝了一个 bash 命令，代码会不会执行 bash？模型还能不能收到结果？

我的回答：不会执行了，模型能收到，但收到的是 类似于 “用于拒绝了xxx请求”

### 10. 被拒绝工具的后处理

被 `PreToolUse` 拒绝的工具，会不会触发 `PostToolUse`？为什么？

我的回答：不会，PostToolUse 一般是记录tool call的结果、或者对结果二次处理，但被拒绝了之后工具就没执行了

### 11. 统一权限入口

`permission_hook()` 为什么可以同时检查 bash 命令、文件路径和 MCP 工具？

我的回答：因为这边拿到的其实是 content 的一整个block，这个block.name 就是工具名，可以通过这个工具名来进行分支的判断

### 12. 多个 hook 的处理

`log_hook` 返回 `None`，但 `permission_hook` 可能返回错误字符串。`trigger_hooks()` 遇到多个 hook 时如何处理？

我的回答：不清楚

### 13. 路径越界

如果 `write_file` 的路径越出了 workspace，具体在哪一层被拦截？

我的回答：会在 permission 拒绝掉，也就是 pre tool use 的 相关 hook

### 14. 四类 hook 的位置

`UserPromptSubmit`、`PreToolUse`、`PostToolUse`、`Stop` 四种 hook 分别处于什么阶段？

我的回答：UserPromptSubmit在loop最前面，用于包装一下用户的提示词

## 三、特殊工具与上下文压缩

### 15. `compact` 的特殊分支

`compact` 为什么在普通工具分发前被单独处理？

我的回答：

### 16. 同轮 compact 与危险工具

如果同一轮响应中同时有 `compact` 和一个危险 bash 工具，按照当前代码，危险 bash 会不会被检查？

我的回答：

### 17. 分层压缩

`tool_result_budget()`、`snip_compact()`、`micro_compact()`、`compact_history()` 各自解决什么问题？

我的回答：

### 18. 保持 tool_use/tool_result 配对

压缩时为什么不能随便从 assistant 的 `tool_use` 和 user 的 `tool_result` 中间截断？

我的回答：

### 19. 两种主动压缩

`compact_history()` 和模型主动调用 `compact` 有什么区别？

我的回答：

### 20. reactive compact

prompt too long 触发的 `reactive_compact()`，和普通每轮压缩有什么区别？

我的回答：这种算是被动的紧急压缩了，已经拿到了api的错误了，而且这种压缩通常损失是最大的

### 21. 大结果持久化

为什么大 tool result 会先持久化到 `.task_outputs/tool-results/`，而不是直接全部塞回上下文？

我的回答：

## 四、同步、后台和通知

### 22. 后台判定

什么条件下 bash 会走 `should_run_background()`？

我的回答：有个boolean的参数，或者是命中代码中写死的一些命令

### 23. 后台占位结果

后台任务启动后，主循环立即返回给模型的是什么？

我的回答： 一个 tool result content “后台xxx任务已提交， bg_id”

### 24. 后台结果回流

后台任务真正完成后，结果通过什么路径重新进入模型上下文？

我的回答：通过 每次 loop 开始之前，检查下内存那个bg task的map，然后再塞入到context中

### 25. 完成与可见性的时间差

“工具已经完成”和“模型已经知道工具完成”为什么是两个不同时间点？

我的回答：因为现有的机制是，每次loop最前面才插入任务完成的内容，而不是在loop期间，比如post tool call的时候注入的

### 26. `task_notification` 的作用

后台任务完成后，为什么使用 `task_notification`，而不是重新伪造一个普通 `tool_result`？

我的回答：因为之前已经有一个 tool result 里面已经谢了 task id占位了，并且对应这了tool_id，不能再有一个 tool result了

### 27. 后台失败

如果后台任务执行失败，当前 demo 会把失败信息放在哪里？

我的回答：

## 五、MCP 与动态工具池

### 28. MCP 工具何时出现

`connect_mcp("docs")` 执行成功后，为什么 MCP 工具通常要到下一轮才出现？

我的回答：因为 就算链接成功了，mcp 的 tool 也得下一轮，才能和buildin tools全部放到llm call里面

### 29. `assemble_tool_pool()` 的两面

`assemble_tool_pool()` 做了哪两件事？对模型侧和执行侧分别有什么作用？

我的回答：组合 buildin tools 和 mcp tools，执行侧 将 mcp tools 进行了 handler 的绑定

### 30. MCP 工具命名

为什么 MCP 工具名称会被转换成：

```text
mcp__server__tool  防止重名
```

我的回答：

### 31. 定义与 handler 的关联

`connect_mcp("docs")` 后，模型看到的工具定义和程序实际执行的 handler 是如何关联的？

我的回答：通过 connect 得到的resgiter 信息 把

### 32. 同名工具

如果两个 MCP server 都有同名的 `search` 工具，前缀解决了什么问题？

我的回答：去重

### 33. mock 隐藏的边界

当前 MCP 是 mock 实现。它隐藏了真实 MCP 中的哪些进程、通信、生命周期或错误处理边界？

我的回答：mcp的通信协议，本地stdio、http stream 、 sse 等

## 六、错误恢复

### 34. 429 与 529

429 和 529 在 `with_retry()` 中分别如何处理？

我的回答：

### 35. fallback model

为什么 529 连续失败后可能切换 `FALLBACK_MODEL`？

我的回答：

### 36. max_tokens 恢复

模型因为 `max_tokens` 截断时，代码为什么先提高 `max_tokens`，之后才发送 continuation prompt？

我的回答：

### 37. prompt too long

如果 prompt 太长，为什么不是普通重试，而是先做 `reactive_compact()`？

我的回答：

### 38. 异常分支与 Stop hook

当前异常分支里追加 `[Error] ...` 后直接返回。此时 `Stop` hook 会不会执行？你认为这是有意设计还是潜在缺口？

我的回答：

## 七、综合推演

### 39. 连接 MCP 再搜索

用户输入：

```text
连接 docs MCP，然后搜索 agent loop
```

请推演至少两轮中 `messages`、工具池和模型可见能力如何变化。

我的回答：

### 40. 后台安装

用户要求：

```text
在后台执行 npm install，然后继续读取 README.md
```

请说明可能出现的工具调用顺序，以及后台通知何时进入上下文。

我的回答：

```text
loop1:
  llm_call
  tool_call1: bash tool_call "npm install" in background
  tool_call2: read_file "README.md"
  get bg_id
  get README.md

background_task:
  npm install done
  update task status

loop2:
  collect_bg_task_result
  llm_call
```

标准答案：

**工具调用顺序（常见路径）**

```text
loop1:
  inject_background_notifications()          # 首轮通常无已完成任务
  llm_call
  → 模型一次返回两个 tool_use block（顺序由模型决定，常见为先 bash 后 read）

  tool_call1: bash "npm install"
    → should_run_background() = True
      （"npm install" 命中 is_slow_operation 慢操作关键词；不必显式传 run_in_background）
    → start_background_task()：后台线程启动，主循环不阻塞
    → 立即返回 tool_result 占位符：
      "[Background task bg_0001 started] Result will arrive as a task_notification."

  tool_call2: read_file "README.md"
    → 同步执行，立即返回 README 正文

  append 一条 user 消息（含上述两个 tool_result）
  → build_user_content() 末尾也会调 collect_background_results()
    若 npm 在 loop1 结束前就跑完，通知可能在此刻就进上下文（少见）

background_thread（与 loop1 并行）:
  npm install 完成
  → background_tasks[bg_id].status = "completed"
  → background_results[bg_id] = 命令输出

loop2:
  inject_background_notifications()          # 主路径：收集已完成任务
  → messages 新增 user 消息，内容为 <task_notification> XML
  llm_call                                   # 模型此时才看到 install 的真实结果
```

**后台通知何时进入上下文**

| 注入点 | 函数 | 时机 |
|--------|------|------|
| 每轮 loop 开头 | `inject_background_notifications()` | **主路径**：下一轮 `llm_call` 之前 |
| loop 末尾 append tool_result 时 | `build_user_content()` 内部 | 若后台任务在 loop1 结束前完成（少见） |

要点：

- bash 的 `tool_result` 只是「已启动」占位；真正输出走独立的 `task_notification` user 消息，**不会**补进 bash 那条 `tool_result`。
- `collect_background_results()` 收集后会从全局 dict pop 掉，避免重复注入。
- 两个 `tool_result` 合成**一条** user 消息返回模型；`task_notification` 是**另一条**独立的 user 消息。

### 41. 一个拒绝、一个允许

模型先调用一个被权限拒绝的 bash，再调用一个普通的 `read_file`。当前循环会怎样处理这两个 block？

我的回答：

### 42. handler 异常

如果某次模型响应含有 tool_use，但其中一个工具 handler 抛出异常，其他工具和下一轮会怎样？

我的回答：

### 43. 完整链路图

画出从“用户输入”到“最终返回”的完整链路，并标出：

- hooks
- context preparation
- LLM
- tool dispatch
- permission
- tool result
- background notification
- stop condition

我的回答：

### 44. “机制很多，循环一个”

请解释这句话。它具体指哪些机制共享了同一个循环，哪些机制仍然拥有自己的内部线程或子循环？

我的回答：

### 45. 核心伪代码

请写一段不超过 15 行的伪代码，重现这个 demo 的核心 `agent_loop()`。

我的回答：

update_context()
  return `
    memory: ...
    tools: ...
    active teammate:...
  `

agent_loop()
  system_prompt = update_context()
  messages = compact_messages(message)
  messages.append(handle_bg_task_result())

  res = with_retry(llm_call(system_prompt, messages, max_token, tools))

  if prompt_too_long_error:
      res = with_retry(llm_call(system_prompt, messages, large_max_token, tools))

  message.append(res.message)
  if has_tool_use(res.message.content)
    for block in res.message.content
      result = TOOL_HANDLER.get(block.name)(**block.input)
      message.append({name: "tool_result", content: result})

  msg = check_inbox()
  message.append({name: "user", content: msg})


## 自测记录

- 第一组：待完成
- 第二组：待完成
- 第三组：待完成
- 第四组：待完成
- 第五组：待完成
- 第六组：待完成
- 第七组：待完成

记录规则：把“代码已确认”“自己的推断”“运行后观察到的事实”分开写，避免把静态阅读结论当成运行验收。
