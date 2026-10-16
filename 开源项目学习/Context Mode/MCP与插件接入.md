# Context Mode：MCP与插件接入

## 学习问题与范围

- 当前问题：为什么使用本地 MCP 服务提供工具，插件与 Hook 又承担什么职责？
- 相关子问题：本地进程、工具清单与调用协议、插件安装与注册、跨宿主复用及平台差异。
- 进度：已初始化，待逐步学习。

## 源码与证据

- 官方仓库、固定版本与既有对话：[项目入口](README.md)；初始化日期：2026-10-15。
- 证据状态：已读固定版本的 `.claude-plugin/plugin.json`、`.mcp.json.example` 与 `hooks/hooks.json`；实现的完整调用链与运行行为待验证。

## 我的笔记

### 为啥使用MCP

这是一个开发MCP的很大的一个原因

为了让同一套工具能力能被更多 Coding Agent 复用，采用本地 MCP 是很自然的选择。

如果使用Plugin模式的话
会大大增加开发和长期维护的成本

如果每家 Agent 的插件标准不同，就需要分别适配工具注册、参数格式、生命周期事件和发布方式；各家升级后，还可能需要跟着调整。
MCP 把其中的工具发现与调用接口统一了，因此执行、索引、搜索等核心能力可以复用。平台特有的 Hook、自动提醒和会话恢复，仍需要适配。

了解！这个是一个，开发外部工具的一个很重要的抉择标准！

如果我希望开发一个通用的插件

那么他的形式必然是以 本地的mcp server为主

但是如果是那种Coding Agent的社区插件
那么基本上是 Tool、Hook、Skill 为主

### MCP组成部分

| 功能 | 示例中的位置 |
|---|---|
| 创建服务 | `new McpServer(...)` |
| 建立通信通道 | 两端的 `Stdio…Transport` |
| 协议初始化、版本与能力协商、就绪通知 | 客户端 `connect()` 与服务端 SDK 配合完成 |
| 请求 ID、响应匹配、协议错误 | SDK 内部处理 |
| 发现工具 | `client.listTools()` |
| 调用工具 | `client.callTool(...)` |
| 连通性检查 | `client.ping()` |
| 关闭连接 | `client.close()`；服务端主动关闭可用 `server.close()` |


### MCP的使用

Agent 调用 MCP 工具，最终会执行 MCP Server 中注册的一个处理函数。

```text
模型提出工具调用：ctx_search，参数是……
    ↓
Agent 的执行程序通过 MCP 客户端发送 tools/call
    ↓
MCP Server 的 SDK 根据工具名找到注册的处理函数
    ↓
执行函数：查询索引，整理结果
    ↓
通过 MCP 把结果返回给 Agent，再交给模型
```

# 疑惑：本地MCP是整个项目一个还是全局一个

我一开始的问题是 

假如本地有context mode 的 mcp server了
同时启动了 A 和 B 两个不同目录的文件，并且同时要求修改 ./index.js 文件

这个 mcp server哪知道修改哪个文件？？

这就涉及了mcp的两种启动模式

1. 每个项目一个MCP server

项目 A 的 Agent                     MCP 进程 1
workspace = D:/a  ──────────────→   配置的项目目录 = D:/a

项目 B 的 Agent                     MCP 进程 2
workspace = D:/b  ──────────────→   配置的项目目录 = D:/b

两个Agent都调用 {"path": "src/main.ts"}
此时mcp server是资源隔离的，不会互相影响

但是坏处是，会启动很多

2. 全局一个MCP server

Agent A ──→ {"path": "src/main.ts"} ──┐
                                    ├──→ 同一个 MCP Server
Agent B ──→ {"path": "src/main.ts"} ──┘


这种就需要 额外的根目录参数来配合了

{
  "workspace": "D:/a",
  "path": "src/main.ts"
}

但是其实这个通用的workspace参数，可以利用额外的机制注进去

claude code代码例子，cc用的是 配置事件 + 启动脚本的方式
```js
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__files__edit_file",
        "hooks": [
          {
            "type": "command",
            "command": "node",
            "args": [
              "${CLAUDE_PROJECT_DIR}/.claude/hooks/inject-workspace.cjs"
            ]
          }
        ]
      }
    ]
  }
}

const fs = require("node:fs");

// 宿主通过标准输入传入本次事件，里面包含模型生成的工具参数。
const event = JSON.parse(fs.readFileSync(0, "utf8"));

// 从宿主环境动态读取会话启动时的项目目录，没有写死 D:/a。
const workspace = process.env.CLAUDE_PROJECT_DIR;

if (!workspace) {
  console.error("缺少项目目录，无法补充 workspace");
  process.exit(2); // 阻止本次调用，避免目录含义不明确。
}

// 保留本次调用的所有参数，再补充 workspace。
// path 来自 event.tool_input，没有写死文件名。
const updatedInput = {
  ...event.tool_input,
  workspace,
};

// 这是返回给宿主的修改指令，由宿主继续发送 MCP 请求。
process.stdout.write(JSON.stringify({
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    updatedInput,
  },
}));

```

pi使用的是 on 事件回调的方式
```js
pi.on("tool_call", async (event, ctx) => {
  // 在回调里读取事件并处理。
});
```


它本身也有两种配置方式

就pi而言

| 放置位置 | 含义 |
|---|---|
| 项目中的 `.pi/mcp.json` | 项目级配置 |
| 用户目录的 `~/.pi/agent/mcp.json` | 全局配置 |

但这个只是 两个 配置的位置

最终还是每个Pi进程一个MCP Server

在 D:/a 启动 Pi A
  → Pi A 加载全局配置中的 Context Mode 扩展
  → 扩展启动 MCP 子进程 A，继承 D:/a 的工作目录

在 D:/b 启动 Pi B
  → Pi B 加载同一份全局配置中的扩展
  → 扩展启动 MCP 子进程 B，继承 D:/b 的工作目录

## 对原系统的影响

| 增加的内容 | Cursor 完整接入 | Pi 完整接入 |
|---|---|---|
| **工具定义** | 通过 MCP 获取 11 个工具及其描述、参数结构 | 扩展通过 MCP 桥接获取工具，再注册到 Pi |
| **使用指令** | `.cursor/rules/context-mode.mdc` | 扩展动态添加路由提示 |
| **事件处理** | 配置 `preToolUse`、`postToolUse`、`stop` 等 Hook | 注册 `tool_call`、`tool_result`、压缩和关闭等事件 |
| **运行与存储** | 本地 MCP 进程、索引和会话数据库 | MCP 桥接子进程、索引和会话数据库 |