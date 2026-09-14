"""Mock/教学追踪：仅使用标准库；不调用真实模型、GPU、Provider 或工具。"""

import math
import sys


VOCAB = ["<user>", "问", "<end>", "<assistant>", "你", "好", "<EOS>"]
EOS = 6


def main():
    # Windows 终端编码可能不同；统一为 UTF-8，保证中文教学输出可读。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(__doc__)
    messages = [{"role": "user", "content": "问"}]
    print("[Chat/API] messages =", messages)
    # 仅支持这条固定输入：控制标记独立成 Token，不模拟真实 BPE。
    pieces = ["<user>", messages[0]["content"], "<end>", "<assistant>"]
    print("[输入适配] Chat Template =", "".join(pieces))
    context = [VOCAB.index(piece) for piece in pieces]
    print("[输入适配] Tokenizer / Token ID =", context)
    # 人工二维查表代替学习得到的 Embedding；不执行 Attention 或位置编码。
    embedding = [(index / 10, -index / 10) for index in range(len(VOCAB))]
    print("[模型输入层] Token Embedding =", [embedding[i] for i in context])
    cache = []
    output = []
    pending = context[:]
    phase = "Prefill"
    # 固定分数剧本保证链路有限且可观察，不能说明模型如何学会回答。
    for target in [4, 5, EOS]:
        before = len(cache)
        print(f"[推理 Runtime] {phase}：处理 IDs={pending}")
        if phase == "Decode":
            print("[模型输入层] 新 Token Embedding =", [embedding[i] for i in pending])
        # 列表只记录已处理位置，绝不代表真实各层 K/V 张量。
        cache.extend(pending)
        print(f"[推理 Runtime] KV Cache 位置增长：{before} -> {len(cache)}")
        logits = [-4.0] * len(VOCAB)
        logits[target] = 4.0
        label = "首 Token Logits" if phase == "Prefill" else "下一 Token Logits"
        print(f"[Mock 模型输出] {label} = {logits}")
        # 减去最大分数保持概率不变，并避免指数溢出；Softmax 本身不选 Token。
        weights = [math.exp(value - max(logits)) for value in logits]
        probs = [value / sum(weights) for value in weights]
        chosen = max(range(len(probs)), key=probs.__getitem__)
        print("[推理 Runtime] Softmax =", [round(p, 4) for p in probs])
        print(f"[推理 Runtime] 采样/选择策略=Greedy（取最大值，无随机抽样）：{VOCAB[chosen]}")
        context.append(chosen)
        output.append(chosen)
        print(f"[推理 Runtime] 追加 Token：context={context}；缓存仍为 {len(cache)} 个位置")
        if chosen == EOS:
            print("[推理 Runtime] EOS（序列结束标记）：停止；EOS 不再送入前向计算")
            break
        pending = [chosen]
        phase = "Decode"
    # 这里只做整段反向查表并去除 EOS；真实流式输出可增量 Detokenize。
    text = "".join(VOCAB[i] for i in output if i != EOS)
    print("[输出适配] Detokenizer / 返回文本 =", text)
    print("[责任边界] 模型只产生分数；本例没有 Tool Call 或业务动作。")
    print("[若有 Tool Call] Agent Runtime：解析 -> Schema 校验 -> 权限判断 -> 执行工具 -> 回填 Tool Result")


if __name__ == "__main__":
    main()
