# OpenSandbox

OpenSandbox 本身就是一个独立的沙箱服务
其他Agent的社区插件将OpenSandbox变成插件，提供了一套harness的设施

我们先聊给harness提供了哪些能力，然后再深入顶层看看这些能力
还是从agent角度出发

底层倒是支持了很多沙箱的类型

| 选择                      | 底层隔离机制                                    |
| ----------------------- | ----------------------------------------- |
| **普通容器，默认方案**           | 通常使用 `runc`，依靠 Linux namespace、cgroup 等机制 |
| **gVisor**              | 在应用和宿主机内核之间增加用户态内核                        |
| **Kata Containers**     | 把容器工作负载放进独立虚拟机，可搭配 QEMU 等                 |
| **Firecracker MicroVM** | 使用微型虚拟机；当前项目提供 Kubernetes 下的相关集成          |

不过只是支持而已，按需使用还需要安装各自的依赖
用普通容器：需要先准备 Docker。
用 gVisor：需要安装并配置 runsc，再让 OpenSandbox 使用它。
用 Kata：需要部署 Kata 运行时。
用 Firecracker：需要部署对应的 Kubernetes 集成，例如它支持的 Fast Sandbox 后端。

# OpenSandbox in Agent

三种形式 

| 入口 | 谁来调用 | 常见使用方式 |
|---|---|---|
| **SDK** | 业务程序、自己写的 Harness | 在代码里创建沙箱、传文件、执行命令、回收环境 |
| **MCP** | 支持 MCP 的 Agent／Harness | 把沙箱能力暴露为工具，让 Agent 选择并调用 |
| **CLI** | 人，或者 Agent 的 Bash 工具 | 执行 `osb ...` 命令操作沙箱 |

## SDK

npm install @alibaba-group/opensandbox

## MCP

```json
{
  "mcpServers": {
    "opensandbox": {
      "command": "opensandbox-mcp",
      "args": ["--domain", "localhost:8080", "--protocol", "http"]
    }
  }
}
```

## CLI

安装
```bash
pip install opensandbox-cli
# or
uv tool install opensandbox-cli
```

```bash
osb --help  # 有这个就ok
osb config init
osb config set connection.domain localhost:8080
osb config set connection.protocol http
osb config set connection.api_key <your-api-key>
osb sandbox create --image python:3.12 --timeout 30m -o json
osb command run <sandbox-id> -o raw -- python -c "print(1 + 1)"
```

# OpenSandbox MCP

主要是21个工具 + 1段介绍（可以放在system prompt里面）

| 类别 | 能力 |
|---|---|
| **沙箱管理：9 个** | 创建、连接已有沙箱、销毁、查询信息、列举、续期、健康检查、资源指标、获取端口访问地址 |
| **命令执行：4 个** | 执行命令、查询状态、读取后台日志、中断执行 |
| **文件操作：8 个** | 读、写、删除、按路径模式搜索、创建目录、删除目录、移动、替换内容 |


```py
def create_server(connection_config: ConnectionConfig | None = None) -> MCPServer:
    """Create the MCP server instance for OpenSandbox."""
    mcp = MCPServer(
        "OpenSandbox Sandbox",
        instructions=(
            "Use these tools to create and manage isolated sandboxes. "
            "Always keep track of the sandbox_id returned by sandbox_create/connect. "
            "Use command_run for execution, file_read/file_write for file IO, and "
            "sandbox_kill to terminate remote sandboxes. Use sandbox_get_endpoint to "
            "expose sandbox ports; for large files, prefer range reads. "
            "For command_run with background=True, poll command_get_status and read "
            "new output with command_get_logs, passing back the returned cursor; "
            "once the status reports running=false, read the logs one last time."
        ),
    )
    register_tools(mcp, connection_config=connection_config)
    return mcp
```

# 1. sandbox_create 工具

