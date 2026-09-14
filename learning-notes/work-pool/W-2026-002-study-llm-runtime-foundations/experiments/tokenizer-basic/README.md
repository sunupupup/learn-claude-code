# Tokenizer 最小观察实验

## 实验目标

使用 `deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B` 配套的真实 Tokenizer，观察：

```text
文本 → Token → Token ID → 解码文本
```

本实验只下载 Tokenizer 配置、词表和规则，不下载模型 Checkpoint，不需要 GPU。

## 固定环境

- Python：3.13.5
- Transformers：5.17.0
- Tokenizer 来源：`deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B`
- `add_special_tokens=False`：暂时排除 BOS、EOS 等特殊 Token，只观察原始文本切分。

## 观察输入

```text
ABC
 ABC
你好
print("hi")
```

运行时重点比较：

1. `ABC` 和 ` ABC` 的 Token 是否相同；
2. `你好` 有几个字符、几个 Token；
3. 代码中的英文、括号和引号怎样组合；
4. Token ID 解码后是否能还原原文。

## 安装依赖

在仓库根目录使用 PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pip install -r ".\learning-notes\work-pool\W-2026-002-study-llm-runtime-foundations\experiments\tokenizer-basic\requirements.txt"
```

## 运行实验

```powershell
.\.venv\Scripts\python.exe ".\learning-notes\work-pool\W-2026-002-study-llm-runtime-foundations\experiments\tokenizer-basic\tokenizer_demo.py"
```

首次运行会从 Hugging Face 下载 Tokenizer 文件，后续通常使用本机缓存。实际 Token 数和 Token ID 以运行输出为准。

## 代码中的关键 API

| API | 作用 |
| --- | --- |
| `AutoTokenizer.from_pretrained(...)` | 根据模型目录加载配套 Tokenizer，不加载神经网络权重 |
| `tokenizer(text, ...)` | 把文本编码为 Token ID |
| `convert_ids_to_tokens(...)` | 查看词表中的内部 Token 表示 |
| `decode(...)` | 把 Token ID 解码回文本 |
| `offset_mapping` | 查看每个 Token 对应原文中的字符范围 |

资料：[Hugging Face Tokenizers Quicktour](https://huggingface.co/docs/tokenizers/quicktour)、[Transformers Tokenizer API](https://huggingface.co/docs/transformers/main_classes/tokenizer)。
