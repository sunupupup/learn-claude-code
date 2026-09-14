"""输入 Token Embedding 教学：默认看表，手算后用 --lookup 验证。

只用 Python 标准库；不下载模型、不需要 GPU、不写文件。
中文主笔记沿用 ../../词嵌入与模型文件学习笔记.md。
"""

import argparse
import sys


# 人工编写的教学权重表，不是真实模型权重，也没有经过训练。
# 形状为 [vocab_size, hidden_size] = [5, 3]：5 行，每行 3 个数。
# Token ID 只是从 0 开始的行号；ID 数值接近不代表语义接近。
WEIGHTS = [
    [0.1, 0.2, 0.3],    # ID 0
    [-0.4, 0.8, 0.1],   # ID 1
    [0.7, -0.2, 0.5],   # ID 2：沿用中文主笔记中的教学数值。
    [0.0, 0.6, -0.9],   # ID 3
    [-0.3, 0.4, 0.9],   # ID 4
]
TOKEN_IDS = [2, 4, 2]


def lookup(token_ids):
    vectors = []
    for token_id in token_ids:
        # 禁止负数，避免 Python 将 -1 解释成最后一行，掩盖无效 ID。
        if type(token_id) is not int or not 0 <= token_id < len(WEIGHTS):
            raise ValueError("Token ID 必须是 0 到 4 的整数。")
        # 直接按行号取向量，不把 ID 乘入向量；同一张表中相同 ID 查相同行。
        vectors.append(WEIGHTS[token_id])
    return vectors


def main():
    # Windows 终端编码可能不同；统一为 UTF-8，保证中文教学输出可读。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lookup", action="store_true", help="手算后再显示查表结果")
    args = parser.parse_args()
    print("教学权重表（人工数值，未训练）")
    print("[vocab_size, hidden_size] = [5, 3]")
    for token_id, row in enumerate(WEIGHTS):
        print(f"ID {token_id}: {row}")
    print("Token ID 只是从 0 开始的行号；编号接近不代表语义接近。")
    print("本实验：LLM 输入 Token Embedding，每个 ID 查出一个向量。")
    print("RAG（检索增强生成）文本 Embedding：将文本编码成检索向量；本实验不实现它。")
    print(f"输入 Token IDs: {TOKEN_IDS}")
    if args.lookup:
        vectors = lookup(TOKEN_IDS)
        for token_id, vector in zip(TOKEN_IDS, vectors):
            print(f"查询 ID {token_id} -> {vector}")
        print(f"输出形状 [token_count, hidden_size] = [{len(vectors)}, {len(vectors[0])}]")
        print(f"第一个与第三个向量相同: {vectors[0] == vectors[2]}")
        print("只验证输入查表；不包含位置编码、Attention、训练或上下文表示。")
    else:
        print("先手算这三个 ID 对应的向量，贴回你的答案；暂不运行 --lookup。")


if __name__ == "__main__":
    main()
