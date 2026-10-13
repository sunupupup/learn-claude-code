# 我的笔记

重点是
其实是 通过 大量的  emit
来实现 数据的流式响应是吧 
一般 SSE 就ok是吧

如果是重启进程，恢复对话，那就是从jsonl数据恢复

大多数带工具调用的聊天式 Agent，都可以先这样理解：
- 正文块：模型给用户的解释、回答、总结。
- 工具块：调用了什么工具、参数是什么、正在运行还是已结束。
- 工具结果展示：文本、代码、表格、图片等；可以放在工具块内部。

# 工具事件流与 JSONL 恢复：最小双进程 Demo

这是独立教学实现，不代表 Pi 的生产行为。只需 Python 3.10+，无第三方依赖。
前端是终端程序，后端是另一个 Python 进程；通过 stdin/stdout 管道通信。
工具是安全的三步模拟检查，不访问业务系统、不执行 shell，也不会把密钥交给模型。

## 立即运行（PowerShell）

```powershell
cd D:\code\third-party-labs\agent\learn-claude-code\practice\tool-stream-demo
python frontend.py --session first
```

看到不同的前端/后端 PID；随后依次看到模型消息、工具参数、工具运行、步骤 1/3、2/3、3/3、成功与最终总结。每行有事件序号和“实时/落盘”标记。任务结束后前端自动发送 quit，两个进程退出。

同一会话重新启动（只恢复，绝不执行工具）：

```powershell
python frontend.py --session first --restore
```

失败和中断演示，请使用新的 sessionId：

```powershell
python frontend.py --session failed --fail
python frontend.py --session failed --restore
python frontend.py --session interrupted --fault interrupt
python frontend.py --session interrupted --restore
```

中断故障在第二次进度后真实退出后端。恢复显示 `interrupted`（中断/结果未知），`output` 和 `isError` 为 null；不是失败结果，更不能当作成功。Ctrl+C 也会停止后端。已有历史的会话拒绝再次 start；要做新任务请换 ID。

落盘与发送之间的窗口：

```powershell
python frontend.py --session gap --fault after-persist
python frontend.py --session gap --restore
```

第一次前端不知道工具已成功；第二次从磁盘读到工具成功，但整体任务仍为中断（尚未形成模型总结）。此时两份状态不同是预期事实；恢复后的磁盘状态才是恢复依据。

## 真实 DeepSeek

当前项目的 `.env` 已按本次授权配置且被 Git 忽略。其他机器先执行：

```powershell
Copy-Item .env.example .env
notepad .env
python frontend.py --mode live --session real_first
python frontend.py --session real_first --restore
```

在 `.env` 填写自己的 key，模型使用 `DEEPSEEK_MODEL=deepseek-flash`。环境变量优先于 `.env`。
真实模式会发两次请求：强制指定工具调用 → 本地执行 → 将结果交给模型总结；强制调用用于稳定展示教学路径，不代表模型自主选工具。真实模型文本由 SSE（Server-Sent Events，服务端逐片发送）读取并转成前端事件；参数片段接收完整后才解析和执行。工具进度由后端生成，不依赖模型生成“进度事件”。

接口采用官方 [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/) 与 [Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)。关闭 thinking，限制输出为 512 tokens。HTTP 拒绝只报告状态码，不切换模型、不自动重试、不记录秘密请求头或原始错误正文。真实模式会产生 API 费用。

## 自动验证

```powershell
python check.py
python check.py --live --report validation.json
```

第一条完全离线；第二条额外执行真实模型调用，使用临时目录，结束自动清理。检查器实际启动、退出、重新启动后端，通过协议读取恢复状态，验证历史文件字节未改变、未再次发出工具执行事件。
比较工具 ID、名称、参数、最终输出、isError、终态，以及包含工具调用的完整消息与顺序；不比较临时进度与时间戳（协议未添加时间戳）。中断时先把失联前端的 running 状态归一为 interrupted，再比较。

已运行证据：[validation.json](./validation.json) 和 [demo-output.txt](./demo-output.txt)。记录使用固定模型的实际结果，不包含密钥。验收涵盖成功、工具失败、执行中断、落盘后发送前中断、残缺尾行、重复 start 拒绝和单写入者锁。

## 协议与持久化边界

RPC（Remote Procedure Call，远程过程调用）在这里仅表示前端把命令发给另一进程；不是网络服务。每行一个 JSON 对象，JSONL 是 JSON Lines。最小命令：

```json
{"command":"start","mode":"offline","fail":false}
{"command":"restore"}
{"command":"quit"}
```

事件例子：

```json
{"type":"tool_execution_update","sessionId":"first","seq":7,"durable":false,"toolCallId":"call_x","output":"步骤 1/3：模拟检查完成"}
```

| 事件 | 落盘 | 作用 |
|---|---|---|
| task_start / task_end | 是 | 是否开始、是否形成整体终态 |
| message_end | 是 | 完整 user/assistant/tool 消息，保持顺序 |
| tool_execution_start | 是 | 保存 ID、名称、参数，发现无结束的工具 |
| tool_execution_end | 是 | 保存最终输出、isError 与成功/失败 |
| message_update | 否 | 模型文字分片，未完成的分片不当作历史消息 |
| tool_execution_update | 否 | 运行中进度；恢复不重新展示三次进度 |
| session_ready / restored / rpc_error | 否 | 通信控制与恢复快照 |

所有事件都含 `sessionId`、单调递增 `seq` 和 `durable`。实时事件占用序号但不落盘，因此磁盘序号有空隙是正常的；恢复后从持久化最大序号继续，序号只在当前传输内用于检查顺序，并非跨所有连接的全局唯一 ID。工具通过稳定 `toolCallId` 关联开始、进度和结束。

`state.py` 的 reducer（状态归约器，把事件依次应用到状态的函数）同时用于前端实时展示与后端历史恢复。恢复不调用模型或工具。实时中间态可比历史丰富，最终稳定字段应一致；完整 JSONL 文件在 `data/<sessionId>.jsonl`，不是全部实时事件的 trace。

## 代码阅读顺序

1. [state.py](./state.py)：事件怎样改变消息、工具与任务状态。
2. [backend.py](./backend.py)：`emit()` 先持久化再发送；`tool()` 产生中间进度；`run()` 形成完整消息。
3. [frontend.py](./frontend.py)：前端启动后端、发送命令、逐行接收并显示。
4. [model.py](./model.py)：真实 SSE 内容与工具参数分片的组装。
5. [check.py](./check.py)：同一 sessionId 重新启动、内容比较与故障验证。

## 保证范围

先 append、flush、fsync 再发送，缩小“已显示但没落盘”的窗口；stdout flush 只是把数据送进管道，不代表前端确认收到了。文件写入和发送不是原子事务，也没有严格一次保证。若工具实际完成却未写入结束记录，恢复仍只能说结果未知。模拟工具没有外部副作用；真实业务需进一步考虑业务幂等、对账与事务。

一个后端独占一个 session，通过 `.lock` 防并发写。前端在确认自己的子进程退出后清理自己的锁；如果整个前端被强杀，确认旧后端已停止，再手动删除对应 `data/<sessionId>.lock`。不要删除仍在运行的锁。直接启动 backend 时也是如此。
残缺且无换行的最后一行被忽略，并将已有会话保持只读；完整行 JSON 损坏或乱序直接报错，不跳过错误。未验证断电、磁盘硬件 fsync 保证、网络代理兼容性和完整生产事务。

## 反思

- 不确定性：测试覆盖进程级故障，不能据此宣称断电安全或严格一次；真实模型结果也不保证每次措辞相同。
- 学习建议：先读 `emit()` 的“磁盘 → 管道”顺序，再观察 gap 实验；理解传输事件、恢复历史与业务事实是三个不同层次。
