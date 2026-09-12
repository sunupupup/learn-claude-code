# s19：真实 MCP Response 记录

这份文档记录 2026-09-11 对真实 Context7 MCP Server 的只读 HTTP 实测结果。

## 实测对象

- Endpoint：**https://mcp.context7.com/mcp**
- Client：本章学习代码之外，使用一个最小 HTTP 客户端直接发送 JSON-RPC 请求
- Transport：Streamable HTTP；本次响应的 Content-Type 是 **text/event-stream**
- 认证：本次请求没有携带 API Key 或 Authorization header
- 协议版本：请求使用 **2025-11-25**
- 重要边界：这是一次观测记录，服务端的版本、工具描述和响应内容以后可能变化

## 1. initialize：建立 MCP 会话能力协商

### 请求

~~~http
POST /mcp
Accept: application/json, text/event-stream
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": {
      "name": "learn-claude-code-inspector",
      "version": "0.1.0"
    }
  }
}
~~~

### HTTP 响应

- Status：**200**
- Content-Type：**text/event-stream**
- 本次响应没有 **Mcp-Session-Id** header

### 完整响应事件

~~~text
event: message
data: {"result":{"protocolVersion":"2025-11-25","capabilities":{"prompts":{"listChanged":true},"resources":{"listChanged":true},"tools":{"listChanged":true}},"serverInfo":{"name":"Context7","version":"4.1.0","websiteUrl":"https://context7.com","description":"Context7 provides up-to-date documentation and code examples for libraries and frameworks.","icons":[{"src":"https://context7.com/context7-icon-green.png","mimeType":"image/png"}]},"instructions":"Use this server to fetch current documentation whenever the user asks about a library, framework, SDK, API, CLI tool, or cloud service — even well-known ones like React, Next.js, Prisma, Express, Tailwind, Django, or Spring Boot. This includes API syntax, configuration, version migration, library-specific debugging, setup instructions, and CLI tool usage. Use even when you think you know the answer — your training data may not reflect recent changes. Prefer this over web search for library docs.\n\nDo not use for: refactoring, writing scripts from scratch, debugging business logic, code review, or general programming concepts."},"jsonrpc":"2.0","id":1}
~~~

### 解析后的关键结构

~~~json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-11-25",
    "capabilities": {
      "prompts": {
        "listChanged": true
      },
      "resources": {
        "listChanged": true
      },
      "tools": {
        "listChanged": true
      }
    },
    "serverInfo": {
      "name": "Context7",
      "version": "4.1.0",
      "websiteUrl": "https://context7.com",
      "description": "Context7 provides up-to-date documentation and code examples for libraries and frameworks.",
      "icons": [
        {
          "src": "https://context7.com/context7-icon-green.png",
          "mimeType": "image/png"
        }
      ]
    },
    "instructions": "Use this server to fetch current documentation whenever the user asks about a library, framework, SDK, API, CLI tool, or cloud service — even well-known ones like React, Next.js, Prisma, Express, Tailwind, Django, or Spring Boot. This includes API syntax, configuration, version migration, library-specific debugging, setup instructions, and CLI tool usage. Use even when you think you know the answer — your training data may not reflect recent changes. Prefer this over web search for library docs.\n\nDo not use for: refactoring, writing scripts from scratch, debugging business logic, code review, or general programming concepts."
  }
}
~~~

### 这次响应说明了什么

1. 客户端告诉服务端自己支持什么协议版本，并提供 clientInfo。
2. 服务端返回最终采用的协议版本。
3. capabilities 是服务端能力声明：
   - prompts.listChanged: true：服务端支持 Prompts 相关能力，并可能通知客户端列表发生变化。
   - resources.listChanged: true：服务端支持 Resources 相关能力，并可能通知客户端列表发生变化。
   - tools.listChanged: true：服务端支持 Tools 相关能力，并可能通知客户端工具列表发生变化。
4. serverInfo 是服务端身份和版本信息。
5. instructions 是服务端给客户端的使用说明；它不是某个可调用 Tool，也不是权限授予。

## 2. notifications/initialized：通知初始化完成

initialize 成功后，客户端又发送了一个没有 id 的 JSON-RPC 通知：

~~~http
POST /mcp
Accept: application/json, text/event-stream
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
~~~

### HTTP 响应

- Status：**202**
- Body：空

这个请求没有 id，所以它是 notification，客户端不等待 JSON-RPC result。它表达的是：客户端已经处理完 initialize，可以继续进行后续 MCP 操作。

## 3. tools/list：获取服务端提供的 Tool 定义

### 请求

~~~http
POST /mcp
Accept: application/json, text/event-stream
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
~~~

### HTTP 响应

- Status：**200**
- Content-Type：**text/event-stream**
- 本次响应没有 Mcp-Session-Id header

### 完整响应事件

~~~text
event: message
data: {"result":{"tools":[{"name":"resolve-library-id","title":"Resolve Context7 Library ID","description":"Resolves a package/product name to a Context7-compatible library ID and returns matching libraries.\n\nYou MUST call this function before 'Query Documentation' tool to obtain a valid Context7-compatible library ID UNLESS the user explicitly provides a library ID in the format '/org/project' or '/org/project/version'.\n\nEach result includes:\n- Library ID: Context7-compatible identifier (format: /org/project)\n- Name: Library or package name\n- Description: Short summary\n- Code Snippets: Number of code examples\n- Source Reputation: Authority indicator (High, Medium, Low, or Unknown)\n- Benchmark Score: Quality indicator (100 is the highest score)\n- Versions: List of versions if available. Use one of those versions if the user provides a version in their query. The format of the version is /org/project/version.\n\nFor best results, select libraries based on name match, source reputation, snippet coverage, and relevance to your use case.\n\nSelection Process:\n1. Analyze the query to understand what library/package the user is looking for\n2. Return the selected library ID in a clearly marked section\n3. Provide a brief explanation for why this library was chosen\n4. If multiple good matches exist, acknowledge this but proceed with the most relevant one\n5. If no good matches exist, clearly state this and suggest query refinements\n\nFor ambiguous queries, request clarification before proceeding with a best-guess match.\n\nIMPORTANT: Do not call this tool more than 3 times per question. If you cannot find what you need after 3 calls, use the best result you have.","inputSchema":{"type":"object","$schema":"https://json-schema.org/draft/2020-12/schema","properties":{"query":{"type":"string","description":"What to look up in the library's documentation. This is used to rank library results by relevance to what the user is trying to accomplish. The query is sent to the Context7 API for processing. Do not include any sensitive or confidential information such as API keys, passwords, personal data, or proprietary code in your query."},"libraryName":{"type":"string","description":"Library name to search for and retrieve a Context7-compatible library ID. Use the official library name with proper punctuation — e.g., 'Next.js' instead of 'nextjs', 'Customer.io' instead of 'customerio', 'Three.js' instead of 'threejs'."}},"required":["query","libraryName"]},"annotations":{"readOnlyHint":true,"destructiveHint":false,"openWorldHint":true,"idempotentHint":true}},{"name":"query-docs","title":"Query Documentation","description":"Retrieves and queries up-to-date documentation and code examples from Context7 for any programming library or framework.\n\nYou must call this tool after 'resolve-library-id' to obtain documentation for a library, unless the user explicitly provides a Context7-compatible library ID in the format '/org/project' or '/org/project/version'.\n\nDo not call this tool more than 3 times per question.","inputSchema":{"type":"object","$schema":"https://json-schema.org/draft/2020-12/schema","properties":{"libraryId":{"type":"string","description":"Exact Context7-compatible library ID (e.g., '/mongodb/docs', '/vercel/next.js', '/supabase/supabase', '/vercel/next.js/v14.3.0-canary.87') retrieved from 'resolve-library-id' or directly from user query in the format '/org/project' or '/org/project/version'."},"query":{"type":"string","description":"What to look up in the library's documentation, scoped to a single concept. Be specific and include relevant details, but keep each query to one topic — if the user asks spans multiple distinct concepts, make separate calls instead of combining them, unless the question is about how the concepts interact. Good: 'How to set up authentication with JWT in Express.js' or 'React useEffect cleanup function examples'. Bad: 'auth' or 'hooks'. Bad: 'routing and auth and caching in Next.js'. The query is sent to the Context7 API for processing. Do not include any sensitive or confidential information such as API keys, passwords, personal data, or proprietary code in your query."}},"required":["libraryId","query"]},"annotations":{"readOnlyHint":true,"destructiveHint":false,"openWorldHint":true,"idempotentHint":true}}]},"jsonrpc":"2.0","id":2}
~~~

### 解析后的完整 Tool 列表

#### Tool 1：resolve-library-id

- name：resolve-library-id
- title：Resolve Context7 Library ID
- description：

~~~text
Resolves a package/product name to a Context7-compatible library ID and returns matching libraries.

You MUST call this function before 'Query Documentation' tool to obtain a valid Context7-compatible library ID UNLESS the user explicitly provides a library ID in the format '/org/project' or '/org/project/version'.

Each result includes:
- Library ID: Context7-compatible identifier (format: /org/project)
- Name: Library or package name
- Description: Short summary
- Code Snippets: Number of code examples
- Source Reputation: Authority indicator (High, Medium, Low, or Unknown)
- Benchmark Score: Quality indicator (100 is the highest score)
- Versions: List of versions if available. Use one of those versions if the user provides a version in their query. The format of the version is /org/project/version.

For best results, select libraries based on name match, source reputation, snippet coverage, and relevance to your use case.

Selection Process:
1. Analyze the query to understand what library/package the user is looking for
2. Return the selected library ID in a clearly marked section
3. Provide a brief explanation for why this library was chosen
4. If multiple good matches exist, acknowledge this but proceed with the most relevant one
5. If no good matches exist, clearly state this and suggest query refinements

For ambiguous queries, request clarification before proceeding with a best-guess match.

IMPORTANT: Do not call this tool more than 3 times per question. If you cannot find what you need after 3 calls, use the best result you have.
~~~

- inputSchema：

~~~json
{
  "type": "object",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "properties": {
    "query": {
      "type": "string",
      "description": "What to look up in the library's documentation. This is used to rank library results by relevance to what the user is trying to accomplish. The query is sent to the Context7 API for processing. Do not include any sensitive or confidential information such as API keys, passwords, personal data, or proprietary code in your query."
    },
    "libraryName": {
      "type": "string",
      "description": "Library name to search for and retrieve a Context7-compatible library ID. Use the official library name with proper punctuation — e.g., 'Next.js' instead of 'nextjs', 'Customer.io' instead of 'customerio', 'Three.js' instead of 'threejs'."
    }
  },
  "required": [
    "query",
    "libraryName"
  ]
}
~~~

- annotations：

~~~json
{
  "readOnlyHint": true,
  "destructiveHint": false,
  "openWorldHint": true,
  "idempotentHint": true
}
~~~

#### Tool 2：query-docs

- name：query-docs
- title：Query Documentation
- description：

~~~text
Retrieves and queries up-to-date documentation and code examples from Context7 for any programming library or framework.

You must call this tool after 'resolve-library-id' to obtain documentation for a library, unless the user explicitly provides a Context7-compatible library ID in the format '/org/project' or '/org/project/version'.

Do not call this tool more than 3 times per question.
~~~

- inputSchema：

~~~json
{
  "type": "object",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "properties": {
    "libraryId": {
      "type": "string",
      "description": "Exact Context7-compatible library ID (e.g., '/mongodb/docs', '/vercel/next.js', '/supabase/supabase', '/vercel/next.js/v14.3.0-canary.87') retrieved from 'resolve-library-id' or directly from user query in the format '/org/project' or '/org/project/version'."
    },
    "query": {
      "type": "string",
      "description": "What to look up in the library's documentation, scoped to a single concept. Be specific and include relevant details, but keep each query to one topic — if the user asks spans multiple distinct concepts, make separate calls instead of combining them, unless the question is about how the concepts interact. Good: 'How to set up authentication with JWT in Express.js' or 'React useEffect cleanup function examples'. Bad: 'auth' or 'hooks'. Bad: 'routing and auth and caching in Next.js'. The query is sent to the Context7 API for processing. Do not include any sensitive or confidential information such as API keys, passwords, personal data, or proprietary code in your query."
    }
  },
  "required": [
    "libraryId",
    "query"
  ]
}
~~~

- annotations：

~~~json
{
  "readOnlyHint": true,
  "destructiveHint": false,
  "openWorldHint": true,
  "idempotentHint": true
}
~~~

### 这次 tools/list 说明了什么

1. Agent/Host 在真正调用工具之前，先通过 tools/list 获得工具名、说明、参数 JSON Schema 和提示性 annotations。
2. inputSchema 让客户端知道调用参数的结构，通常会被 Host 转换成模型可理解的 Tool definition。
3. Tool 的 description 可以包含调用顺序和使用限制，例如先调用 resolve-library-id，再调用 query-docs。
4. 这些 description 是模型选择工具时的重要上下文，但仍然属于不可信的外部元数据；生产客户端不能只依赖 description 做权限控制。
5. tools/list 返回了两个工具，但 initialize 中还声明了 prompts/resources 能力；这不等于本次已经请求了 prompts/list 或 resources/list。

## 4. tools/call：调用一个已经发现的 Tool

这次先调用 resolve-library-id，查询 Model Context Protocol 相关库。

### 请求

~~~http
POST /mcp
Accept: application/json, text/event-stream
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "resolve-library-id",
    "arguments": {
      "query": "MCP",
      "libraryName": "Model Context Protocol"
    }
  }
}
~~~

### HTTP 响应

- Status：**200**
- Content-Type：**text/event-stream**
- 本次响应没有 Mcp-Session-Id header

### 完整响应事件

~~~text
event: message
data: {"result":{"content":[{"type":"text","text":"Available Libraries:\n\n- Title: Model Context Protocol\n- Context7-compatible library ID: /modelcontextprotocol/modelcontextprotocol\n- Description: This repository contains the specification and protocol schema for the Model Context Protocol, with schemas defined in TypeScript and available as JSON Schema.\n- Code Snippets: 4161\n- Source Reputation: High\n- Benchmark Score: 85.68\n----------\n- Title: Model Context Protocol\n- Context7-compatible library ID: /microsoft/mcp-for-beginners\n- Description: This curriculum provides a structured learning path for the Model Context Protocol (MCP), a framework for standardizing AI model and client application interactions, with hands-on code examples in C#, Java, JavaScript, Python, and TypeScript.\n- Code Snippets: 14445\n- Source Reputation: High\n- Benchmark Score: 76.43\n----------\n- Title: Model Context Protocol\n- Context7-compatible library ID: /websites/modelcontextprotocol\n- Description: Model Context Protocol is an open-source standard that enables AI applications to connect seamlessly to external data sources and tools through a standardized JSON-RPC protocol.\n- Code Snippets: 3347\n- Source Reputation: High\n- Benchmark Score: 76.92\n----------\n- Title: Model Context Protocol\n- Context7-compatible library ID: /websites/modelcontextprotocol_io_specification_2025-11-25\n- Description: Model Context Protocol (MCP) is an open protocol that enables seamless integration between LLM applications and external data sources and tools, providing a standardized way to share contextual information, expose tools, and build composable integrations.\n- Code Snippets: 733\n- Source Reputation: High\n- Benchmark Score: 82.63\n----------\n- Title: Model Context Protocol\n- Context7-compatible library ID: /llmstxt/modelcontextprotocol_io_llms-full_txt\n- Description: Model Context Protocol is an open standard that enables AI applications and LLM-based tools to securely interact with external data sources and services through a standardized interface.\n- Code Snippets: 15958\n- Source Reputation: High\n- Benchmark Score: 75.46"}]},"jsonrpc":"2.0","id":3}
~~~

### 解析后的响应

~~~json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Available Libraries:\n\n- Title: Model Context Protocol\n- Context7-compatible library ID: /modelcontextprotocol/modelcontextprotocol\n- Description: This repository contains the specification and protocol schema for the Model Context Protocol, with schemas defined in TypeScript and available as JSON Schema.\n- Code Snippets: 4161\n- Source Reputation: High\n- Benchmark Score: 85.68\n----------\n- Title: Model Context Protocol\n- Context7-compatible library ID: /microsoft/mcp-for-beginners\n- Description: This curriculum provides a structured learning path for the Model Context Protocol (MCP), a framework for standardizing AI model and client application interactions, with hands-on code examples in C#, Java, JavaScript, Python, and TypeScript.\n- Code Snippets: 14445\n- Source Reputation: High\n- Benchmark Score: 76.43\n----------\n- Title: Model Context Protocol\n- Context7-compatible library ID: /websites/modelcontextprotocol\n- Description: Model Context Protocol is an open-source standard that enables AI applications to connect seamlessly to external data sources and tools through a standardized JSON-RPC protocol.\n- Code Snippets: 3347\n- Source Reputation: High\n- Benchmark Score: 76.92\n----------\n- Title: Model Context Protocol\n- Context7-compatible library ID: /websites/modelcontextprotocol_io_specification_2025-11-25\n- Description: Model Context Protocol (MCP) is an open protocol that enables seamless integration between LLM applications and external data sources and tools, providing a standardized way to share contextual information, expose tools, and build composable integrations.\n- Code Snippets: 733\n- Source Reputation: High\n- Benchmark Score: 82.63\n----------\n- Title: Model Context Protocol\n- Context7-compatible library ID: /llmstxt/modelcontextprotocol_io_llms-full_txt\n- Description: Model Context Protocol is an open standard that enables AI applications and LLM-based tools to securely interact with external data sources and services through a standardized interface.\n- Code Snippets: 15958\n- Source Reputation: High\n- Benchmark Score: 75.46"
      }
    ]
  }
}
~~~

### 这次调用说明了什么

1. tools/call 的 params 里传的是 Tool 名称和 arguments。
2. Tool 名称来自前一步 tools/list，客户端不是凭空猜出来的。
3. MCP Server 返回的是一个统一的 JSON-RPC result；其中 content 是 MCP 内容块数组，本次内容块类型是 text。
4. Agent Host 收到结果后，通常会把这个结果转换为模型下一轮可读取的 Tool result。
5. 这一次调用是只读查询；生产环境中仍然需要在 Host 层单独做权限、超时、预算和审计控制。

## 5. 和本章教学 Mock 的对应关系

本章代码里的 Mock 结构：

~~~python
mcp_client = MCPClient()
mcp_client.register(tool_definition, handler)
tools = mcp_client.tools
result = mcp_client.call_tool(tool_name, tool_input)
~~~

它把真实 MCP Client、Transport、Server 的多个边界压缩在一个 Python 对象里：

| 本章教学 Mock | 真实 MCP 中更接近的对象 |
| --- | --- |
| register() | Server 注册 Tool，或 Client 连接后缓存 tools/list 结果 |
| mcp_client.tools | Client 通过 tools/list 获得的 Tool definitions |
| call_tool(name, input) | Client 发送 tools/call JSON-RPC 请求 |
| MOCK_SERVERS["docs"] | 一个真实 MCP Server 的地址、启动命令或配置项 |
| 本地 handler 函数 | MCP Server 内部真正执行 Tool 的代码 |
| connect_mcp | 本章 Host 自己提供的连接/发现入口，不是 MCP 标准方法名 |

Agent 看到的工具名还可能经过 Host 命名空间转换。例如本章会把已连接 MCP 的工具暴露成：

~~~text
mcp__docs__search_docs
~~~

而真实 MCP Server 在 tools/list 中只返回：

~~~text
search_docs
~~~

这个前缀是 Host 为了避免多个 Server 出现同名 Tool 而增加的本地映射，不是 MCP Server 返回的原始 Tool 名。

## 6. 本次实测的边界和待继续学习点

### 已直接观察到

- initialize
- notifications/initialized
- tools/list
- tools/call
- JSON-RPC request/response
- HTTP text/event-stream 响应
- capabilities
- serverInfo
- instructions
- Tool 的 name、title、description、inputSchema、annotations

### 本次没有请求

- prompts/list
- prompts/get
- resources/list
- resources/read
- resources/subscribe
- notifications/tools/list_changed

因此，initialize 返回 prompts 和 resources 能力，只能证明服务端在能力声明中支持相关机制；不能据此断言这次服务暴露了哪些 Prompt 或 Resource，必须分别调用对应方法才能知道。

### 关于会话和 HTTP 连接

这次响应没有 Mcp-Session-Id，所以不能仅凭这次观测断言 Context7 使用了有状态会话。HTTP keep-alive、SSE 响应流、MCP logical session 是三个不同层次：

1. HTTP 连接复用是传输层行为。
2. SSE 是本次响应的 HTTP 内容传输方式。
3. MCP session 是否有服务端状态，要看协议实现和响应 header/后续行为。

### 生产实现不能照抄的地方

- 不能把 Tool description 当成权限系统。
- 不能把服务端返回的 instructions 当成 Host 的安全策略。
- 不能只根据 readOnlyHint 就跳过审批；它是提示性 metadata。
- 需要处理超时、取消、重试、重复执行、结果大小、错误映射和审计。
- 需要隔离不同 MCP Server 的身份、凭据、网络权限和 Tool 命名空间。
- 需要处理 tools/list 动态变化，不能永远使用启动时的缓存。

## 7. 一条最小真实调用链

~~~text
Host 配置 endpoint
  -> POST initialize
  <- serverInfo + capabilities + instructions
  -> POST notifications/initialized
  -> POST tools/list
  <- Tool definitions + inputSchema
  -> 把 Tool definitions 转成模型可见的 tools
  -> 模型选择某个 Tool
  -> POST tools/call { name, arguments }
  <- JSON-RPC result.content
  -> Host 把结果放入下一轮模型上下文
~~~

这条链说明了本章最重要的区别：MCP Server 负责按协议声明和执行能力；Agent Host 负责连接、发现、命名空间映射、把定义交给模型，以及把调用结果送回模型。
