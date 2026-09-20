"""观察真实 Tokenizer 如何把文本转换成 Token 和 Token ID。"""

from __future__ import annotations

import os
import sys

# 这个实验只使用 Tokenizer。隐藏缺少 PyTorch、匿名下载和 Windows 缓存方式等
# 非关键提示，让输出集中展示本节需要观察的编码结果。
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from transformers import AutoTokenizer


# 固定模型 ID，确保本实验使用和 DeepSeek-R1-Distill-Qwen-1.5B 配套的 Tokenizer。
MODEL_ID = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"

SAMPLES = [
    # "ABC",
    # " ABC",
    # "你好",

    # print("hi") 被切成 print、("、hi、")，是因为分词器按照已经固定的词表和切分规则，把这段文本编码成了这四个 Token。
    # 这些规则的形成与分词器训练文本中的频率统计有关，常见组合更有机会成为 Token。但具体切分还受预处理规则和合并顺序影响，不能仅凭结果就断定“这四段出现得最多”。
    # 'print("hi")',

    # '(((((',
    # '((((((',

    # 特殊 token 是一个整体
    '<｜begin▁of▁sentence｜>You are a helpful assistant.<｜User｜>Hello!<｜Assistant｜>Hi!<｜end▁of▁sentence｜>'
    #------------------------------------------------------------
    # {'input_ids': [151646, 2610, 525, 264, 10950, 17847, 13, 151644, 9707, 0, 151645,     13048, 0, 151643], 'attention_mask': [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],    'offset_mapping': [(0, 21), (21, 24), (24, 28), (28, 30), (30, 38), (38, 48), (48,     49), (49, 57), (57, 62), (62, 63), (63, 76), (76, 78), (78, 79), (79, 98)]}
    # 原文 repr : '<｜begin▁of▁sentence｜>You are a helpful assistant.  <｜User｜>Hello!<｜Assistant｜>Hi!<｜end▁of▁sentence｜>'
    # 字符数    : 98
    # Token 数  : 14
    # Token     : ['<｜begin▁of▁sentence｜>', 'You', 'Ġare', 'Ġa', 'Ġhelpful',  'Ġassistant', '.', '<｜User｜>','Hello', '!', '<｜Assistant｜>', 'Hi', '!',  '<｜end▁of▁sentence｜>']
    # Token ID  : [151646, 2610, 525, 264, 10950, 17847, 13, 151644, 9707, 0, 151645,   13048, 0, 151643]
    # 字符区间  : [(0, 21), (21, 24), (24, 28), (28, 30), (30, 38), (38, 48), (48, 49),     (49, 57), (57, 62), (62, 63), (63, 76), (76, 78), (78, 79), (79, 98)]
    # 解码结果  : '<｜begin▁of▁sentence｜>You are a helpful assistant.  <｜User｜>Hello!<｜Assistant｜>Hi!<｜end▁of▁sentence｜>'
    # 往返一致  : True
]


def inspect_text(tokenizer, text: str) -> None:
    """打印一次编码中最需要观察的四类结果。"""
    # 暂时关闭特殊 Token，避免 BOS/EOS 干扰对原始文本切分的观察。
    encoded = tokenizer(
        text,
        add_special_tokens=False,
        return_offsets_mapping=True,
    )
    token_ids = encoded["input_ids"]
    # 解码
    tokens = tokenizer.convert_ids_to_tokens(token_ids)
    offsets = encoded["offset_mapping"]
    decoded = tokenizer.decode(
        token_ids,
        skip_special_tokens=False,
        clean_up_tokenization_spaces=False,
    )

    print("-" * 60)
    print(encoded)
    # {'input_ids': [25411], 'attention_mask': [1], 'offset_mapping': [(0, 3)]}
    # 编码出来的结果，有个 input_ids
    # repr() 会把开头空格显示出来，便于比较 "ABC" 和 " ABC"。
    print(f"原文 repr : {text!r}")
    print(f"字符数    : {len(text)}")
    print(f"Token 数  : {len(token_ids)}")
    print(f"Token     : {tokens}")
    print(f"Token ID  : {token_ids}")
    # 字符区间，代表了 一个 token_id 对应的 token， 对应着原文里面的字符区间 [start,end)
    print(f"字符区间  : {offsets}")
    print(f"解码结果  : {decoded!r}")
    print(f"往返一致  : {decoded == text}")


def main() -> None:
    # Windows 终端可能不是 UTF-8；主动设置后，中文 Token 和结果更容易观察。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(f"正在加载 Tokenizer：{MODEL_ID}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    # 一些特殊token
    print(tokenizer.convert_ids_to_tokens([151664]))  # '<|file_sep|>'
    print(tokenizer.convert_ids_to_tokens([151644]))  # '<｜User｜>'
    print(f"Tokenizer 类：{tokenizer.__class__.__name__}")
    print(f"词表大小：{len(tokenizer)}")

    for sample in SAMPLES:
        inspect_text(tokenizer, sample)


if __name__ == "__main__":
    main()
