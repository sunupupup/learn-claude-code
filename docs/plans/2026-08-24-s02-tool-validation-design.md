# s02 工具调用错误处理设计

## 目标

在不引入新依赖、不过度复杂化教学代码的前提下，为 s02 演示两类工具调用错误：

1. 模型请求的工具名没有对应的本地 handler。
2. `glob` 工具收到不符合约定的输入参数。

错误不终止 Agent 循环，而是作为带有 `is_error: true` 的 `tool_result` 返回模型，让模型观察错误并尝试修正。

## 方案选择

采用轻量的工具校验器注册表，仅为 `glob` 编写手动校验器。

- 不采用全量 JSON Schema 校验：它更适合作为本章之后的生产化扩展，并会引入额外依赖。
- 不直接采用 Pydantic：它适合生产级 Python 工具输入模型，但会增加当前示例的抽象层级。
- 保留 `TOOLS` 和 `TOOL_HANDLERS` 的教学主线，让读者先看清声明、分发、校验、执行、回传的完整链路。

## 组件与数据流

新增三个小组件：

1. `validate_glob_input(tool_input)`：严格要求 `pattern` 存在且类型为字符串。
2. `TOOL_VALIDATORS`：把工具名映射到可选的输入校验函数，目前只注册 `glob`。
3. `execute_tool(tool_name, tool_input)`：统一完成 handler 查找、输入校验、函数执行和异常转换，返回 `(output, is_error)`。

调用流程：

```text
tool_use
  -> 查找 TOOL_HANDLERS
  -> 查找并执行 TOOL_VALIDATORS
  -> 调用 handler
  -> 构造 tool_result
  -> 错误时设置 is_error: true
  -> 继续下一轮模型调用
```

## 错误处理

- 未知工具：返回可用工具名列表，不调用任何函数。
- `glob` 缺少 `pattern`：返回明确的必填参数错误。
- `glob.pattern` 不是字符串：只返回实际类型，不回显完整输入，避免错误信息泄露不必要的数据。
- handler 抛出异常：由执行边界转换为工具错误，避免 Agent 循环直接崩溃。
- 成功结果不写 `is_error`；错误结果显式写入 `is_error: true`。

## 验证

通过纯函数调用覆盖以下场景：

- 已知工具和合法 `glob` 参数正常执行。
- 未知工具返回错误且 `is_error` 为真。
- `glob` 缺少 `pattern` 返回错误。
- `glob.pattern` 为整数时返回类型错误。
- Python 语法编译通过。

## 学习文档

更新 `s02_tool_use/README.md`，补充：

- 为什么模型看过 JSON Schema 后仍不能省略运行时校验。
- 未知工具调用的可能来源。
- `is_error` 如何形成模型可自愈的反馈闭环。
- 手写校验、JSON Schema 和 Pydantic 的取舍。
- 生产级 Agent 仍需考虑的权限、超时、重试、幂等、日志和敏感信息处理。

