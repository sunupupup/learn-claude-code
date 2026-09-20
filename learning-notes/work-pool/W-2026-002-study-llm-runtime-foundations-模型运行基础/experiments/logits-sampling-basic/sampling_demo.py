"""下一 Token 选择：Greedy 或随机采样；选完后统一检查 EOS。"""

import argparse  # 读取运行命令里的参数，例如 --strategy sample。
import math  # exp(x) 计算 e 的 x 次方。
import random  # 按概率抽样，固定种子用于复现。
import sys  # 设置终端的中文输出编码。

# 假设前文是“我喜欢养”，模型正在预测紧接着的一个 Token。
# 这里不调用模型：四个分数是手写的，代替模型根据同一前文算出的本轮 Logits。
# 四个候选竞争同一个位置，不是后续四个位置；真实模型通常给整个词表打分。
# 元组按位置对应：“猫”的分数是 2.0。下标只是实验编号，不是真实 Token ID。
TOKENS = ("猫", "狗", "鱼", "<EOS>")
LOGITS = (2.0, 1.0, 0.0, 0.5)


def greedy(logits):
    """策略一：直接找最高分的候选，返回它的下标，不抽样。"""
    best_index = 0
    for index in range(1, len(logits)):
        # 只有严格更大才替换，因此并列最高时取第一个。
        if logits[index] > logits[best_index]:
            best_index = index
    return best_index


def softmax(scores):
    """采样流程中的概率转换步骤，不是独立选择策略。"""
    # 所有分数减去同一个最大值，不改变 Softmax 结果，并避免指数溢出。
    peak = max(scores)
    weights = []
    for score in scores:
        weights.append(math.exp(score - peak))
    total = sum(weights)
    probabilities = []
    for weight in weights:
        probabilities.append(weight / total)
    return probabilities


def filter_top_p(probabilities, top_p):
    """筛选步骤：保留累计概率达到阈值的最小前缀，再重新归一化。"""
    # 下标按对应概率降序排列；lambda 表示用 probabilities[index] 作为排序依据。
    order = sorted(range(len(probabilities)),
                   key=lambda index: probabilities[index], reverse=True)
    kept = []
    cumulative = 0.0
    for index in order:
        kept.append(index)
        cumulative += probabilities[index]
        # 包含使累计概率首次达到阈值的候选；p=1 时明确保留全部。
        if top_p < 1.0 and cumulative >= top_p:
            break
    weights = []
    for index in kept:
        weights.append(probabilities[index] / cumulative)
    return kept, weights


def sample(logits, temperature, top_p, rng):
    """策略二：温度调节 → Softmax → Top-p → 按概率抽取。"""
    # 第一步：温度调节分数。此函数只接收正温度，温度 0 在 main 中走 Greedy。
    scores = []
    for logit in logits:
        scores.append(logit / temperature)
    print("  1. 温度调节后的分数:", scores)

    # 第二步：把调整后的分数转换成概率，此时还没选 Token。
    probabilities = softmax(scores)
    print("  2. Softmax 概率（Token 顺序不变）:", probabilities)

    # 第三步：只筛选候选并重新归一化，此时依然还没抽取 Token。
    kept, weights = filter_top_p(probabilities, top_p)
    print("  3. Top-p 保留的候选及新概率:")
    # zip 将下标与对应概率逐项配对。
    for index, probability in zip(kept, weights):
        print(f"     {TOKENS[index]}: {probability:.6f}")

    # 第四步：按概率抽一个。choices 返回列表，例如 [2]；[0] 取出唯一结果。
    # 不是在剩余候选中等概率抽签，也不是固定选概率最高的候选。
    print("  4. 按上述概率随机抽取")
    return rng.choices(kept, weights=weights, k=1)[0]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    # ArgumentParser 创建命令行参数解析器；parser 是给这个对象起的名字。
    # add_argument 声明参数，parse_args 才真正读取命令并将结果放入 args。
    # choices 是允许的取值，default 是未填写时的值，type 指定数值转换方式。
    parser = argparse.ArgumentParser(description=__doc__)
    # 这里只列两种真正的选择策略，不再把处理步骤、停止标记混成同级选项。
    parser.add_argument("--strategy", choices=("greedy", "sample"), default="greedy",
                        help="greedy 直接选最高分；sample 按概率抽样")
    parser.add_argument("--temperature", type=float, default=1.0,
                        help="仅采样使用：越低越集中；0 在本 Demo 中转为 Greedy")
    parser.add_argument("--top-p", type=float, default=1.0,
                        help="仅采样使用：累计概率阈值，1 表示不筛掉候选")
    parser.add_argument("--seed", type=int, default=7, help="采样的随机种子")
    parser.add_argument("--max-tokens", type=int, default=1,
                        help="最多选择几次；增大可观察 EOS 停止")
    args = parser.parse_args()
    # 如 --strategy sample --top-p 0.8，解析后 args.strategy 为 'sample'，args.top_p 为 0.8。
    # 参数名中的短横线会变成属性名中的下划线。
    if not math.isfinite(args.temperature) or args.temperature < 0:
        parser.error("temperature 必须是有限的非负数")
    if not 0 < args.top_p <= 1:
        parser.error("top-p 必须在 (0, 1] 内")
    if args.max_tokens < 1:
        parser.error("max-tokens 必须至少为 1")

    strategy = args.strategy
    if strategy == "sample" and args.temperature == 0:
        # 这是运行时约定，不能把 0 代入除法公式。
        print("temperature=0：改走 Greedy，不进行除法或抽样。")
        strategy = "greedy"
    if strategy == "greedy":
        print("策略：Greedy；temperature、top-p、seed 不参与选择。")
    else:
        print(f"策略：随机采样；temperature={args.temperature}, top-p={args.top_p}, seed={args.seed}")

    # 同一 Python 版本、种子及调用顺序下可以复现；固定种子不等于 Greedy。
    # 随机源在循环外创建一次，不要每轮重置种子。
    rng = random.Random(args.seed)
    print("候选顺序:", TOKENS)
    print("原始 Logits:", LOGITS)
    print("教学简化：每轮复用固定 Logits；真实模型会随新增前文重新计算分数。")

    # range 不包含终点，因此这里是第 1 次至第 max_tokens 次。
    for step in range(1, args.max_tokens + 1):
        print(f"\n第 {step} 次选择：")
        # 两个分支对应两种选择策略；采样内部的步骤按顺序执行。
        if strategy == "greedy":
            index = greedy(LOGITS)
        else:
            index = sample(LOGITS, args.temperature, args.top_p, rng)

        token = TOKENS[index]
        print("选中:", token)
        # EOS 是两种策略共用的停止检查，不是第三种选择算法。
        if token == "<EOS>":
            print("停止原因: EOS")
            break
        # 真实生成会把这个 Token ID 追加到前文，交给模型算下一轮 Logits。
    else:
        # for 的 else 只在没有 break、次数耗尽时执行。
        print("停止原因: 达到 max-tokens 上限（不是 EOS）")


# 直接运行此文件才调用 main；import 时不会自动开始实验。
if __name__ == "__main__":
    main()
