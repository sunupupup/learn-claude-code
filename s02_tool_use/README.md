# s02: Tool Use — 多加一个工具，只加一行

[中文](README.md) · [English](README.en.md) · [日本語](README.ja.md)

s01 → `s02` → [s03](../s03_permission/) → s04 → ... → s20
> *"加一个工具, 只加一个 handler"* — 循环不用动, 新工具注册进 dispatch map 就行。
>
> **Harness 层**: 工具分发 — 扩展模型能触达的边界。

---

## 只有 bash 一个工具

s01 的 Agent 只有一个 bash 工具。读文件要 `cat`，写文件要 `echo "..." > file.py`，改文件要 `sed`。

模型想的是"读这个文件"，却要拼出 `cat path/to/file`。多了一层翻译，浪费 token，还容易拼错。

---

## 全局视角：工具分发

![Tool Dispatch](images/tool-dispatch.svg)

s01 的核心循环完全保留（LLM 调用、stop_reason 判断、消息追加）。核心分发只改 1 行：`run_bash()` 替换为按工具名查表；本章还额外加入一个很薄的错误边界，演示未知工具和错误参数如何返回给模型。

给 Agent 加一个工具只需要做两件事：

1. **定义工具**：在 `TOOLS` 数组里加一条描述
2. **注册处理函数**：在 `TOOL_HANDLERS` 字典里加一个映射

---

## 从 1 个工具到 5 个工具

s01 只有一个 bash：

```python
TOOLS = [{"name": "bash", ...}]

def run_bash(command): ...
```

s02 加到 5 个，每个工具都是独立定义：

```python
TOOLS = [
    {"name": "bash",       "description": "Run a shell command.", ...},
    {"name": "read_file",  "description": "Read file contents.",  ...},
    {"name": "write_file", "description": "Write content to file.", ...},
    {"name": "edit_file",  "description": "Replace text in file once.", ...},
    {"name": "glob",       "description": "Find files by pattern.", ...},
]
```

每个工具有自己的实现函数：

```python
def run_read(path, limit=None):
    lines = safe_path(path).read_text().splitlines()
    if limit:
        lines = lines[:limit]
    return "\n".join(lines)

def run_write(path, content):
    safe_path(path).write_text(content)
    return f"Wrote {len(content)} bytes to {path}"

def run_edit(path, old_text, new_text):
    text = safe_path(path).read_text()
    if old_text not in text:
        return "Error: text not found"
    safe_path(path).write_text(text.replace(old_text, new_text, 1))
    return f"Edited {path}"

def run_glob(pattern):
    import glob as g
    return "\n".join(g.glob(pattern, root_dir=WORKDIR))
```

---

## 工具分发

```python
TOOL_HANDLERS = {
    "bash":       run_bash,
    "read_file":  run_read,
    "write_file": run_write,
    "edit_file":  run_edit,
    "glob":       run_glob,
}

# 循环里只改了一行——从硬编码 run_bash 变成查表：
for block in response.content:
    if block.type == "tool_use":
        handler = TOOL_HANDLERS[block.name]    # 查表
        output = handler(**block.input)         # 调用
        results.append(...)
```

加一个工具 = 在 `TOOLS` 数组加一条 + 在 `TOOL_HANDLERS` 字典加一行。Agent 循环的主体不变。

---

## 工具调用失败：不要让 Agent 循环直接崩溃

`TOOLS[*].input_schema` 是发给模型的**工具契约**，它能显著提高模型生成正确参数的概率，但不能代替本地运行时校验。模型输出仍应被当成不可信输入：模型可能生成错误参数，历史消息可能来自旧版本工具，`TOOLS` 和 `TOOL_HANDLERS` 也可能因为代码维护不同步。

教学版只选 `glob` 演示参数校验：

```python
def validate_glob_input(tool_input: dict) -> str | None:
    if "pattern" not in tool_input:
        return "Missing required parameter 'pattern'"
    if not isinstance(tool_input["pattern"], str):
        actual = type(tool_input["pattern"]).__name__
        return f"'pattern' must be a string, got {actual}"
    return None

TOOL_VALIDATORS = {"glob": validate_glob_input}
```

统一执行边界按顺序处理四件事：查找 handler、校验输入、执行函数、转换异常。

```python
def execute_tool(tool_name, tool_input):
    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return f"Error: Unknown tool '{tool_name}'", True

    validator = TOOL_VALIDATORS.get(tool_name)
    if validator and (error := validator(tool_input)):
        return f"Error: Invalid input: {error}", True

    try:
        return handler(**tool_input), False
    except Exception as e:
        return f"Error: Tool failed: {e}", True
```

这里的布尔值表示结果是不是错误。错误仍然要与原来的 `tool_use_id` 配对，并显式告诉模型：

```python
{
    "type": "tool_result",
    "tool_use_id": block.id,
    "content": output,
    "is_error": True,
}
```

这样形成的是一个可恢复闭环：

```text
错误的 tool_use → 本地拒绝执行 → tool_result(is_error=true)
      → 模型读到具体错误 → 修改工具名或参数 → 再次 tool_use
```

注意，`is_error` 不是让 API 自动重试；是否重试、怎样修正仍由下一轮模型决定。程序还应设置最大轮数或重试预算，避免模型反复犯同一个错误形成死循环。

当前几个 `run_*` 函数为了保持示例简短，仍会在内部捕获部分异常并返回以 `Error:` 开头的普通字符串。外层无法可靠判断这种字符串究竟是错误还是正常文本，因此生产实现不要依赖 `startswith("Error:")`；更稳妥的方式是让 handler 抛出可分类异常，或统一返回结构化的 `ToolExecutionResult`。

### 生产环境一定要用 Pydantic 吗？

不一定，但一定要有可靠的运行时校验，并避免维护两份会逐渐不一致的 schema。

| 方式 | 适合场景 | 主要取舍 |
|------|----------|----------|
| 手写校验 | 教学、小工具、少量业务规则 | 直观，但工具一多容易漏字段和边界条件 |
| JSON Schema 校验 | `TOOLS.input_schema` 已经是权威定义、跨语言系统 | 可直接复用模型看到的 schema，但 Python 类型体验较弱 |
| Pydantic | Python 服务、复杂嵌套参数、希望得到结构化错误 | 类型体验和错误信息好，但应由 Pydantic 生成 JSON Schema，避免重复定义 |

如果项目以 Python 为主，可以让 Pydantic 模型成为单一事实来源：使用严格模式、禁止多余字段，在本地执行 `model_validate()`，再通过 `model_json_schema()` 生成给模型的工具 schema。如果项目需要跨语言共享契约，则更适合把 JSON Schema 作为单一事实来源，再用对应语言的校验器执行。

Pydantic 只解决“输入结构和值是否合法”，并不解决下面这些生产问题：

- **权限与副作用**：合法的 `write_file` 参数仍可能覆盖重要文件。
- **超时、重试和幂等**：工具可能超时；有副作用的调用不能盲目重试。
- **错误分级**：参数错误通常可以让模型修正，系统错误可能应退避或交给用户。
- **注册一致性**：启动时检查 `TOOLS`、handlers 和 validators，尽早发现名称或 schema 漂移。
- **敏感信息**：不要把完整异常栈、密钥或原始敏感输入放进 `tool_result`。
- **可观测性**：日志要记录工具名、调用 ID、耗时、错误类型和重试次数。
- **循环上限**：限制总轮数、单工具重试次数、token 和费用预算。

延伸阅读：

- [Claude 官方文档：处理工具调用与 `is_error`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)
- [Pydantic 官方文档：严格模式](https://docs.pydantic.dev/latest/concepts/strict_mode/)
- [Pydantic 官方文档：模型与 JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/)

---

## 多个工具调用

模型经常一次返回多个 tool_use："读一下 a.py 和 b.py，然后列出所有 .py 文件"。

教学版按 `response.content` 原始顺序逐个执行。CC 的做法更复杂：按原始顺序切成连续 batch，batch 内并发安全的工具并行执行，batch 间严格顺序（见附录）。

---

## 速查

| 概念 | 一句话 |
|------|--------|
| TOOL_HANDLERS | 工具名 → 处理函数的字典。加工具 = 加一行映射 |
| 工具定义 | 告诉模型"我能做什么"的 JSON schema |
| 多工具调用 | 模型可一次返回多个 tool_use，教学版按原始顺序逐个执行 |
| 错误回传 | 未知工具或非法参数作为 `is_error: true` 的 tool_result 返回模型 |
| 循环主体不变 | 仍然是 s01 的 `while True`；只给工具执行增加错误边界 |

---

## 相对 s01 的变更

| 组件 | 之前 (s01) | 之后 (s02) |
|------|-----------|-----------|
| 工具数量 | 1 (bash) | 5 (+read, write, edit, glob) |
| 工具执行 | 硬编码 `run_bash()` | TOOL_HANDLERS 查表分发 |
| 路径安全 | 无 | safe_path 校验（仅 file tools） |
| 循环 | `while True` + `stop_reason` | 主体不变，工具结果增加错误标记 |

---

## 试一下

```sh
cd learn-claude-code
python s02_tool_use/code.py
```

试试这些 prompt：

1. `Read the file README.md and tell me what this project is about`
2. `Create a file called test.py that prints "hello", then read it back`
3. `Find all Python files in this directory`
4. `Read both README.md and requirements.txt, then create a summary file`

观察重点：模型什么时候只调一个工具，什么时候一次调多个？多个工具调用的顺序和结果是否正确？

---

## 接下来

现在 Agent 有 5 个专用工具。file tools 受 `safe_path` 保护，但 bash 不受限制，`rm -rf /` 还是能跑。

s03 Permission → 在工具执行之前加一道门：这个操作安全吗？需要用户批准吗？

<details>
<summary>深入 CC 源码</summary>

> 以下基于 CC 源码 `Tool.ts`、`tools.ts`、`toolOrchestration.ts`、`toolExecution.ts`、`StreamingToolExecutor.ts` 的核查。

### 一、工具定义方式

**教学版**：`TOOLS` 数组 + `TOOL_HANDLERS` 字典。定义和实现分开。
**CC**：每个工具是 `buildTool()` 创建的独立对象，包含 schema、验证、权限、执行。`getAllBaseTools()` 汇总所有工具。

教学版的分离方式对教学更清晰——读者一眼看到"加一个工具 = 两条定义"。

### 二、并发安全判断：isConcurrencySafe()

![Tool Concurrency](images/concurrency-comparison.svg)

教学版按原始顺序逐个执行，不做并发。CC 用 `isConcurrencySafe(input)` 判断能否并发——注意这不是简单的"只读 vs 写"，而是按具体输入判断：

| | isReadOnly | isConcurrencySafe |
|---|---|---|
| FileRead | true | true |
| Glob | true | true |
| Bash `ls` | true | **true** ← 关键差异 |
| Bash `rm` | false | false |
| TaskCreate | false | **true** ← 改状态但可并发（TaskCreate 在 s12 介绍） |

CC 的 Bash tool 的 `isConcurrencySafe` 等于 `isReadOnly`——只读命令可并发，写命令不可。TaskCreate 虽然改了任务文件，但每次都写不同的文件，所以可以并发。

### 三、分区算法

CC 的 `partitionToolCalls()`（`toolOrchestration.ts:91-115`）不是分两组，而是把工具调用**按连续块分批**：

```
[read A, read B, glob *.py, bash "rm x", read C]
  → batch1(并发): [read A, read B, glob *.py]
  → batch2(串行): [bash "rm x"]
  → batch3(并发): [read C]
```

并发安全的连续块编入同一个 batch，batch 内真正并发执行（`toolOrchestration.ts:152-176`，有并发上限）。遇到非并发安全的就开新 batch 串行执行。batch 之间严格顺序。

### 四、验证管线

CC 的每个工具调用经过严格的 5 步验证（`toolExecution.ts`）：

1. **Zod schema 验证**（`614-680`）：参数类型/结构检查；教学版只把 JSON Schema 发给模型，本地仅用 `glob` 手写校验演示运行时验证
2. **工具级 validateInput()**（`682-733`）：参数值验证（如路径是否在工作区内）
3. **PreToolUse hooks**（`800-862`，s04 详细介绍）：钩子可以返回消息、修改输入、阻止执行
4. **权限检查**（`921-931`，s03 的核心内容）：canUseTool + checkPermissions → allow/deny/ask
5. **执行 tool.call()**（`1207-1222`）

教学版省略了 Zod（用 JSON Schema）、省略了 validateInput（用安全函数）、保留了权限检查和钩子概念。

### 五、流式工具执行

CC 的 `StreamingToolExecutor`（`StreamingToolExecutor.ts`）让工具在模型还在生成时就启动——不等模型说完。`read_file` 可能在模型还在输出"我来分析"的时候就跑完了。教学版不实现这个，目标和 s01 一致——概念清晰，不追求性能极致。

### 六、工具结果持久化

每个工具有一个 `maxResultSizeChars` 字段。结果超过这个值就落盘，模型看到的是预览 + 文件路径。FileRead 特殊——设为 `Infinity`，防止读文件的输出又被当成文件落盘。具体来说，如果 FileRead 的结果超过阈值被落盘，模型下次读那个落盘文件时又会触发落盘 → 无限循环（读文件 → 落盘 → 再读 → 再落盘 → ...）。

</details>

<!-- translation-sync: zh@v1, en@v0, ja@v0 -->
