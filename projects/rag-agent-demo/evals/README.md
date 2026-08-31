# Eval 目录说明

这里的评测不是“跑几个成功 Demo”，而是用冻结用例检查 Agent 的结果、轨迹和安全边界。`cases.json` 是标准 JSON，因此字段解释放在此处而不是写进文件内部。

- `id`：用例稳定标识；
- `question`：用户问题；
- `groups` / `tenant`：模拟当前请求的身份和权限；
- `expected`：本用例要检查的 Oracle，例如 `answerable`、`no_evidence`、`one_tool_call`、`known_source_only`。

运行 [run_evals.py](run_evals.py) 时使用 fake retriever 和 scripted model，因此不测量真实 Embedding 召回质量，只验证：

1. Tool 是否按要求调用；
2. tenant/group ACL 是否阻止越权；
3. 无证据是否进入正常拒答终态；
4. 最终来源是否来自本次检索结果。

真实系统还应增加人工标注的语义质量集、Prompt Injection 集、延迟/Token/成本指标，以及线上抽样评测。
