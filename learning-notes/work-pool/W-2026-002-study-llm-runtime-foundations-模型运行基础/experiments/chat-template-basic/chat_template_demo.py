"""第一步：观察结构化消息经过 Chat Template 后的文本。"""

import os
import sys

os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from transformers import AutoTokenizer


# 沿用已有分词实验的模型，加载它配套的模板，不手工拼接角色标记。
MODEL_ID = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
MESSAGES = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hi!"},
]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # 只加载 Tokenizer，不加载模型权重。首次运行可能下载分词器配置。
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if not tokenizer.chat_template:
        raise ValueError("该 Tokenizer 没有 Chat Template，请先检查配置。")

    print(f"Model: {MODEL_ID}")
    print("\n原始 messages：")
    for message in MESSAGES:
        print(message)

    # 本步先观察文本；开启生成前缀，观察模板如何追加助手回答的开头。
    rendered = tokenizer.apply_chat_template(
        MESSAGES, tokenize=False, add_generation_prompt=True
    )
    print("\n模板展开文本：")
    print(rendered)
    # repr 让换行等不可见字符也能被观察到。
    print("\n模板展开文本 repr：")
    print(repr(rendered))



if __name__ == "__main__":
    main()
