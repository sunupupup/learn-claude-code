# 实操 02：MCP 网关按用户身份分配工具权限

> **具体防护场景：** 防止只能查询资料的成员，通过同一个 MCP 入口调用本不属于自己的工具，例如删除、发布或运维工具。通过网关验证用户身份、按身份过滤工具列表，并在实际调用时再次授权；下面用 echo 和 get-sum 两个公开工具演示这个机制。

## 场景

两个用户连接同一个 MCP。用户 A 只能调用 `echo`，用户 B 只能调用 `get-sum`；即使直接构造被隐藏工具的调用，也要被网关拒绝。

## 配置代码

使用 **agentgateway**，不是 Cursor Hook。前提：已有 agentgateway 二进制，以及能够签发 JWT 的身份服务。下面用公开的 Server Everything 演示工具授权，不冒充真实翻译或 UI 服务。

**文件：`agentgateway.yaml`**。

```yaml
mcp:
  port: 3333
  policies:
    # 必须先验签，不能直接相信客户端填写的用户 ID。
    mcpAuthentication:
      issuer: https://id.example.com/
      audiences:
        - https://mcp.example.com/mcp
      jwks:
        url: https://id.example.com/.well-known/jwks.json
      jwtValidationOptions:
        requiredClaims:
          - exp
          - aud
          - sub
      resourceMetadata:
        resource: https://mcp.example.com/mcp
        scopesSupported:
          - tools:use
        bearerMethodsSupported:
          - header
    mcpAuthorization:
      rules:
        # user-a / user-b 是经过验签的 sub，不是 Git name。
        # 已存在 allow 规则，因此没有匹配项的操作不会获得允许。
        - allow: 'jwt.sub == "user-a" && mcp.tool.name == "echo"'
        - allow: 'jwt.sub == "user-b" && mcp.tool.name == "get-sum"'
  targets:
    - name: everything
      mcp:
        host: https://servereverything.dev/mcp
```

必须替换 `issuer`、`jwks.url`、`audiences`、`resourceMetadata.resource` 为实际身份服务和网关地址；把 `user-a`、`user-b` 替换为实际账号的稳定主体 ID。令牌需要由身份服务签发，不能把邮箱字符串当 Bearer Token。

启动网关：

```bash
agentgateway -f agentgateway.yaml
```

**业务项目的 `.cursor/mcp.json`**：令牌由当前用户的登录流程提供到 `MCP_ACCESS_TOKEN`，不要把真实值写入文件。

```json
{
  "mcpServers": {
    "governed-tools": {
      "url": "http://localhost:3333/mcp",
      "headers": {
        "Authorization": "Bearer ${env:MCP_ACCESS_TOKEN}"
      }
    }
  }
}
```

本地 HTTP 地址只供开发连接；共享部署使用实际 HTTPS 网关。接自己的 MCP 时，替换 `targets` 和真实工具名，不能只改显示名称。

## 能起到的作用

- 按已验证的身份过滤工具发现列表，并在实际调用时再次检查。
- 未匹配用户不能获得这两个工具的权限；不能通过自行声明“我是 A”获得授权。
- 后端仍需禁止绕过网关直连。此配置是工具级授权，不判断工具参数里的文件路径。
- 按当前文档编写，未部署。依据：[官方授权配置](https://agentgateway.dev/docs/standalone/latest/documentation/configuration/security/mcp-authz/)、[公开操作示例](https://learncloudnative.com/blog/2026-08-14-7-practical-mcp-policies-agentgateway)。

## 我的笔记

