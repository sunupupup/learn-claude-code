# Pi多任务worktree的沙箱插件

一般进行多任务开发的时候，需要切出worktree来进行隔离开发

防止文件修改冲突、启动端口冲突 等 

# pi-cc-subagent 介绍

https://github.com/linearuncle/pi-cc-subagent

实现了 subagent + worktree 的组合

核心流程：
为子 Agent 创建工作目录，再启动一个新的 Pi 进程，把这个目录固定成子进程的工作目录。主 Agent 不需要来回切目录。

其实就是主Agent启动了一个子Pi Agent
所有的harness完全一样，只有工作区不同

正因为Pi的简洁性，使得他很灵活，完全可以随时成为另一个Agent调度的一个子模块

# pi-cc-subagent 内部实现

## 1. 注册 "agent" tool

专门用于委派任务的
   
内部流程其实就是
1. 调用agent工具，加上 desc 参数，标明subagent要干的事
2. 开worktree
3. 明确cwd，当前工作区
4. 创建新的子pi agent

主Agent派任务
```js
tools.agent({
  // 让子 Agent 去执行的任务
  prompt: "检查项目中的登录逻辑，找出可能的问题",
  // 后台执行，主 Agent 可以继续做其他事
  run_in_background: true
})
```

## 2. 主Agent查询任务状态 agent_output tool 

查询后台子 Agent 进度和结果”的工具。主 Agent 和子 Agent 之间，由插件负责传递任务、收集结果。

子Agent执行期间，主Agent可以查看进度

```js
agent_output({
  agent_id: "agent-1"
})

// 可能返回
状态：运行中
已经进行了 3 轮，调用了 5 次工具
最近活动：读取登录相关文件……
```

## 3. 主Agent继续布置任务

因为子pi agent本身就是一个完整的session
那就是有一个专门的session id

```js
agent({
  description: "继续检查",
  resume: "子Pi的会话ID",
  prompt: "你刚才找到的问题，具体应该怎么修复？"
})
```

## 4. 子Agent的 handleEvent

`pi --mode json "检查登录逻辑"`

首先 子 Pi 用 --mode json 启动，标准输出大致长这样（省略部分字段）：

```json
{"type":"turn_start"}
{"type":"tool_execution_start","toolName":"read","args":{"path":"src/login.ts"}}
{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"发现了一个登录问题……"}]}}
```

- 外层是事件对象，用 type 表示发生了什么。
- 部分事件里面才带 message 对象，比如 message_end。

这些type都是不同阶段、不同hook自己写进来的数据

其实这个数据本来就是发给前端的，但是这边子agent只有前面的主Agent，解析出来发给出Agent


| 收到的事件 | 它做什么 | 用途 |
|---|---|---|
| `session` | 保存 `task.agentId` | 后续用 `resume` 续接子会话 |
| `turn_start` | `task.turns++` | 统计运行了几轮 |
| `tool_execution_start` | 工具调用次数加一，保存最近 5 条工具活动 | 展示子 Agent 最近在干什么 |
| `message_end` | 如果是 assistant 消息，提取文本到 `task.finalText`，累计费用、记录错误信息 | 收集之后要交给主 Agent 的回答 |

但这边也是 子agent 在记录自己发生过哪些事
并没有主动发给主Agent的行为

子Agent一般记录 最近干了啥 + 子Agent的结论 + 修改内容 + 完整执行流程

```yaml
任务：修复登录问题
状态：完成

结果：修复了登录过期后未跳转的问题。
修改：auth.ts、login.tsx。
验证：相关测试通过。
遗留：未验证真实浏览器中的跳转行为。
```

## 5. 子Agent 任务报告

这个例子中，确实没有一个完整的任务报告机制

不过可以追加一个prompt 
> 最终消息会原样返回给父 Agent；请返回具体交付物，例如发现、数据、文件位置和结论。

或者 主Agent 布置任务的时候 多一些要求

```yaml
修复登录问题。完成后请汇报：
1. 修复了什么
2. 修改了哪些文件
3. 运行了什么验证，结果如何
4. 还有什么未解决
```


```yaml
子 Agent 输出最终回答
       ↓
插件从 message_end 中提取正文
       ↓
保存到 task.finalText
       ↓
作为 agent 工具结果返回
或通过后台完成通知交给主 Agent
```

## 6. worktree 隔离 

聊到现在，其实subagent，天生知道 worktree 的隔离了

他这个逻辑内置到 harness里面了，会主动切出worktree然后改变cwd

主 Agent 调用 agent，指定 **isolation: "worktree"**
    ↓
插件创建 worktree
    ↓
插件启动子 Pi，把 cwd 设为那个 worktree
    ↓
子 Agent 在自己的工作目录里执行任务


## 7. 端口隔离、docker沙箱

那文件冲突靠 worktree 隔离了，端口冲突呢？比如俩子agent都要启动项目，都用3000端口，这个一般咋处理？

这边就涉及 subagent的沙箱了


两种处理办法

| 方式 | 怎么处理 | 两个项目能否都使用内部端口 3000 |
|---|---|---|
| **分配不同端口** | A 用 3001，B 用 3002，通过启动参数或环境变量传入 | 不能，它们共享主机网络 |
| **隔离网络环境** | 每个任务放到独立网络命名空间、普通独立网络容器或虚拟机里 | 可以，各有自己的网络环境 |


如果是分配不同端口
```
子 Agent A
  worktree：项目副本 A
  启动端口：3001
  访问地址：http://localhost:3001

子 Agent B
  worktree：项目副本 B
  启动端口：3002
  访问地址：http://localhost:3002
```

如果是docker的话
```
宿主机 3001 → 容器 A 的 3000
宿主机 3002 → 容器 B 的 3000
```

但其实方法1，还是比较少见的
如果确实没有docker
子 Agent 通常可以自行换端口启动、测试
不需要主Agent多嘴

## 8. docker沙箱来源

完全可以走原项目的那种镜像配置

因为一般现在项目肯定都有docker file

也就是 原项目环境 + pi这个开发工具

其实也就是原来的docker file里面装上pi
`RUN npm install -g @mariozechner/pi-coding-agent`

然后目录的挂载
工作目录挂载到容器的 /workspace

密钥，会在docker启动的时候，通过 docker 启动命令行注进去一些环境变量是吧

**问题：每次开subagent 多一个沙箱，是不是会大量下载依赖？**

docker会对某些进行缓存么？
比如 有些关键的layer 独立出来单独下载，然后后续能继续使用 ？
agent 应该能理解这种行为吧

会缓存，而且你的理解对：把体积大、变化少的依赖做进镜像层，后续多个子 Agent 可以复用，不需要每开一个容器就重新下载。

| 操作 | 是否重复下载大依赖 |
|---|---|
| 第一次构建或拉取镜像 | 通常需要 |
| 用已有镜像创建多个容器 | **不需要重新下载镜像里的依赖** |
| 修改 Dockerfile 后重新构建 | 看哪些构建步骤的缓存失效 |


镜像只需要下载一次、构建一次，后续就能重复利用
```
基础镜像
  + 项目依赖
  + Pi 等开发工具
  = 项目的 Agent 开发镜像
       ├─ 子 Agent A 的容器
       ├─ 子 Agent B 的容器
       └─ 子 Agent C 的容器
```


镜像和层的不断叠加

```dockerfile
# 直接继承 M，其中已经有 A
FROM my-image-m:v1

# 示例：假设 B 是 Python 包
RUN pip install B
```

对，就是 Dockerfile 开头的 FROM！ 它指定“在谁的基础上继续构建”。