"""四候选教学实验：默认只展示 Greedy，其余阶段按学习进度运行。"""

import argparse  # Python 标准库：读取命令行里的 --stage、--seed 等参数。
import math  # 数学工具：本实验用 exp 计算指数，用 isfinite 检查数值是否合法。
import random  # 伪随机数工具：按概率抽取候选 Token。
import sys  # 读取 Python 版本、设置终端输出编码。


# 人工缩小的词表与固定分数，不是从真实模型提取的输出。
# 两个元组按位置一一对应：TOKENS[0] 是“猫”，LOGITS[0] 是它的分数 2.0。
# 这里的下标 0、1、2、3 只是实验编号，不是真实模型的 Token ID。
TOKENS = ("猫", "狗", "鱼", "<EOS>")
LOGITS = (2.0, 1.0, 0.0, 0.5)


def softmax(logits, temperature=1.0):
    """接收一组分数，返回同顺序的概率列表；不传温度时默认用 1.0。"""
    # isfinite 排除无穷大和 NaN（无效数值）；raise 会报错并中止本次调用。
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("Softmax 的温度必须是有限正数；0 由选择逻辑单独处理。")
    # 先减最大值，避免指数溢出；公共平移不改变最终概率。
    peak = max(logits)
    # 列表推导式：[计算式 for value in logits] 表示逐个取分数、计算并组成列表。
    # math.exp(x) 就是 e 的 x 次方，得到正数权重，此时还没有归一化。
    weights = [math.exp((value - peak) / temperature) for value in logits]
    total = sum(weights)
    # 每个权重除以权重总和，得到总和约为 1 的概率（浮点数可能有微小误差）。
    return [weight / total for weight in weights]


def nucleus(probs, threshold):
    """Top-p 筛选：返回保留的候选下标，以及它们重新归一化后的概率。"""
    if not 0 < threshold <= 1:
        raise ValueError("Top-p 必须在 (0, 1] 内。")
    kept, cumulative = [], 0.0
    # kept 是保存下标的空列表；cumulative 是已保留候选的累计概率。
    # 从高到低保留，包含使累计概率首次达到阈值的那个候选。
    # range(len(probs)) 产生下标；lambda i: probs[i] 指定按概率排序。
    # reverse=True 表示降序；排序后的内容仍然是下标，不是概率值。
    for index in sorted(range(len(probs)), key=lambda i: probs[i], reverse=True):
        kept.append(index)
        cumulative += probs[index]
        # append 把下标加入列表；+= 累加概率；break 立刻结束当前循环。
        if cumulative >= threshold:
            break
    return kept, [probs[index] / cumulative for index in kept]


def choose(rng, temperature, top_p):
    """选出一个候选的下标。rng 是随机数生成器，top_p 是累计概率阈值。"""
    # 本 Demo 约定 T=0 直接 Greedy，不进入除法或随机采样。
    if temperature == 0:
        return max(range(len(LOGITS)), key=lambda i: LOGITS[i])
    kept, weights = nucleus(softmax(LOGITS, temperature), top_p)
    # 先算 Softmax，再做 Top-p；两个返回值分别放进 kept 和 weights。
    # choices 按 weights 抽样，k=1 表示抽一次，返回如 [2] 的列表。
    # [0] 取出列表中的唯一结果，例如下标 2；不是强制选择第 0 个候选。
    return rng.choices(kept, weights=weights, k=1)[0]


def show(probs):
    # zip 将三个序列按位置配对，每轮取出一个 Token、一个分数和一个概率。
    for token, score, probability in zip(TOKENS, LOGITS, probs):
        print(f"{token}: logit={score:.1f}, probability={probability:.6f}")
        # f 字符串把花括号中的变量填进文本；.1f / .6f 表示保留 1 / 6 位小数。
    print(f"概率和: {sum(probs):.6f}")


def main():
    # main 是本脚本组织执行流程的普通函数，文件末尾会调用它。
    # stdout 是终端输出；hasattr 检查它是否支持 reconfigure，再设置 UTF-8 显示中文。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    # ArgumentParser 创建“命令行参数解析器”，parser 是我们给这个对象起的变量名。
    # 它负责把命令中的文字（如 --stage softmax）转换成程序可以读取的设置。
    # description 是帮助说明；__doc__ 就是本文件最上面的三引号文字。
    # 执行 python sampling_demo.py --help 可以查看自动生成的使用说明。
    parser = argparse.ArgumentParser(description=__doc__)
    # add_argument 声明程序接受什么参数，此时还没有读取命令行。
    # --stage 用来选择实验；choices 限定允许值，default 是没有传该参数时的默认值。
    parser.add_argument("--stage", choices=("greedy", "softmax", "temperature", "top-p", "eos"), default="greedy")
    # --seed 设置随机种子；type=int 将输入文本转换成整数，不填时使用 7。
    parser.add_argument("--seed", type=int, default=7)
    # parse_args 真正读取并检查命令行，将结果保存在 args 对象的属性中。
    # 例如：python sampling_demo.py --stage softmax --seed 42
    # 解析后 args.stage == "softmax"，args.seed == 42；无效参数会显示错误。
    args = parser.parse_args()
    # sys.version 包含版本及构建信息；split()[0] 只取第一个空白分隔项，即版本号。
    print(f"Python: {sys.version.split()[0]}; stage={args.stage}")
    if args.stage == "greedy":
        # if / elif / else 根据 stage 只执行一个实验分支。
        for token, score in zip(TOKENS, LOGITS):
            print(f"{token}: logit={score:.1f}")
        # 正温度 Softmax 保持排序，因此可直接找最大 Logit；并列取首个。
        index = max(range(len(LOGITS)), key=lambda i: LOGITS[i])
        # max 比较 key 指定的分数，返回对应下标；TOKENS[index] 再用下标找到 Token。
        print(f"Greedy 选择: {TOKENS[index]}")
    elif args.stage == "softmax":
        # 嵌套调用从里面开始：先算 softmax(LOGITS)，再把结果交给 show 打印。
        show(softmax(LOGITS))
    elif args.stage == "temperature":
        for temperature in (0.5, 1.0, 2.0):
            print(f"\nTemperature={temperature}")
            show(softmax(LOGITS, temperature))
        print("Temperature=0 直接选择:", TOKENS[choose(random.Random(args.seed), 0, 1)])
    elif args.stage == "top-p":
        probs = softmax(LOGITS)
        show(probs)
        kept, weights = nucleus(probs, 0.8)
        print("Top-p=0.8 保留及重新归一化:", [(TOKENS[i], round(p, 6)) for i, p in zip(kept, weights)])
        # 每次运行创建独立随机源；同版本、参数及调用顺序下可复现。
        rng = random.Random(args.seed)
        # Random(seed) 创建带起始种子的伪随机数生成器；k=10 连续抽十次，可重复选中。
        print(f"seed={args.seed}; 10 次独立抽样（不是生成循环）:", rng.choices([TOKENS[i] for i in kept], weights=weights, k=10))
    else:
        rng = random.Random(args.seed)
        print(f"seed={args.seed}; T=1; Top-p=1; 最多 30 步")
        # 为隔离停止机制，每步复用固定分数；真实模型会随上下文重新计算。
        for step in range(1, 31):
            # range 包含起点、不包含终点，所以这里的步数是 1 到 30。
            token = TOKENS[choose(rng, 1.0, 1.0)]
            print(f"step={step}: {token}")
            if token == "<EOS>":
                print("停止原因: EOS；由推理程序结束循环。")
                break
        else:
            # 这是 for 的 else：只有循环自然走完、没有执行 break 时才运行。
            print("停止原因: 达到步数上限；不代表选中了 EOS。")


# 直接运行这个文件时 __name__ 是 "__main__"，于是调用 main 开始实验。
# 被其他 Python 文件 import 时不自动运行实验，便于单独使用上面的函数。
if __name__ == "__main__":
    main()
