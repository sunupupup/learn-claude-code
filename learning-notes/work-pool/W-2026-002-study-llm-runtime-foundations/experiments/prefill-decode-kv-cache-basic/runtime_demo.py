"""Prefill、Decode 与 KV Cache：两个不需要 GPU 的教学实验。

阅读顺序：先看 timeline() 的三个阶段，再看 capacity() 的容量计算。
运行方式：python runtime_demo.py timeline（时间线）
          python runtime_demo.py capacity（理论容量）
注意：输出 Token 和耗时都是预先设定的，不调用真实模型。
"""

import argparse  # Python 标准库：读取命令后面的 timeline / capacity 参数。
import sys


# Windows 终端编码可能不同；保留 UTF-8 设置，保证中文输出可读。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def timeline():
    """按顺序观察：准备输入 → Prefill → 两次 Decode。"""
    # P 表示 Prompt（输入），O 表示 Output（输出）。标签不是实际 Token ID。
    prompt_tokens = ["P1", "P2", "P3", "P4"]
    planned_output_tokens = ["O1", "O2", "O3"]

    # 只记录哪些 Token 已被处理，不保存真正的 Key/Value 数值。
    # 真实 KV Cache 保存的是模型各层产生的 K/V 张量（多维数值数组）。
    cached_tokens = []
    elapsed_ms = 0

    print("教学模拟：4 个输入 Token → 3 个输出 Token")
    print("所有 ms 都是人为设定的虚拟时间，不代表真实 GPU 性能。")

    # 第 1 步：请求可能先排队，并完成输入准备，此时还没有模型缓存。
    preparation_ms = 5
    elapsed_ms += preparation_ms
    print(f"\n[1. 排队及输入准备] 0 → {elapsed_ms} 虚拟 ms")

    # 第 2 步：Prefill 处理已知的整个 Prompt，并建立输入对应的缓存。
    # extend 把列表中的多个元素依次加入另一个列表。
    # 真实模型根据最后一个输入位置的预测选择首个输出；这里直接用预设标签。
    prefill_ms = 8
    start_ms = elapsed_ms
    cached_tokens.extend(prompt_tokens)
    elapsed_ms += prefill_ms
    current_output_token = planned_output_tokens[0]  # 下标 0 表示第一个元素。

    print(f"\n[2. Prefill：处理已知输入] {start_ms} → {elapsed_ms} 虚拟 ms")
    print(f"本次处理：{prompt_tokens}")
    print(f"选出输出：{current_output_token}")
    print(f"缓存对应：{cached_tokens}，共 {len(cached_tokens)} 个位置")
    print(f"模拟 TTFT（首 Token 延迟）={elapsed_ms} ms")
    print("本例 TTFT = 输入准备 + Prefill；选 Token 和传输耗时设为 0。")

    # 第 3 步：把刚选出的 Token 作为下一次输入，利用已有缓存预测后续 Token。
    # [1:] 表示从第二个元素开始，所以循环依次选出 O2、O3。
    # append 每次只加入一个元素：每轮新处理一个 Token，缓存也新增一个位置。
    decode_ms = 2
    decode_step = 0
    for next_output_token in planned_output_tokens[1:]:
        decode_step += 1
        start_ms = elapsed_ms
        input_token = current_output_token
        cached_tokens.append(input_token)
        elapsed_ms += decode_ms
        current_output_token = next_output_token

        print(f"\n[3. Decode 第 {decode_step} 轮] {start_ms} → {elapsed_ms} 虚拟 ms")
        print(f"本次处理：{input_token}（复用此前的 KV Cache）")
        print(f"选出输出：{current_output_token}")
        print(f"缓存对应：{cached_tokens}，共 {len(cached_tokens)} 个位置")

    # “选出 Token”与“把 Token 送入模型计算”是两个动作。
    # 选出 O3 后就停止，未处理 O3，因此缓存长度为 4 + 2，而不是 4 + 3。
    print("\n结束：已输出 O1、O2、O3；O3 未再次送入模型，所以缓存有 6 个位置。")
    print("这是单条序列的顺序依赖；推理引擎仍可同时批处理多条请求。")


def capacity():
    """固定模型尺寸，每次改变一个条件，观察 KV Cache 理论占用。"""
    # 这些是教学假设，不对应某个已加载的模型。
    key_value_copies = 2  # 每个位置保存 Key 和 Value，共两份。
    layers = 32          # 模型有多少层需要保存 KV。
    kv_heads = 8         # 每层 KV 头数；不能直接用查询头数代替。
    head_dim = 128       # 每个头的 K 或 V 向量有多少个数。

    # 每个字典代表一组条件。用字段名标出含义，避免靠元组顺序猜变量。
    # tokens 包含已经缓存的输入和输出位置；所有并发序列假设等长且不共享。
    cases = [
        {"name": "基线", "tokens": 1024, "concurrent_sequences": 1, "bytes_per_element": 2},
        {"name": "上下文翻倍", "tokens": 2048, "concurrent_sequences": 1, "bytes_per_element": 2},
        {"name": "并发翻倍", "tokens": 1024, "concurrent_sequences": 2, "bytes_per_element": 2},
        {"name": "元素改为 1 字节", "tokens": 1024, "concurrent_sequences": 1, "bytes_per_element": 1},
    ]

    print("KV Cache 理论容量：仅计算数值，不实际分配内存。")
    print("公式：2 × layers × tokens × kv_heads × head_dim × bytes_per_element × concurrent_sequences")

    for case in cases:
        tokens = case["tokens"]
        concurrent_sequences = case["concurrent_sequences"]
        bytes_per_element = case["bytes_per_element"]

        # 从小到大计算，便于理解公式的每一项来自哪里。
        elements_per_token_per_layer = key_value_copies * kv_heads * head_dim
        bytes_per_token = elements_per_token_per_layer * layers * bytes_per_element
        bytes_per_sequence = bytes_per_token * tokens
        total_bytes = bytes_per_sequence * concurrent_sequences

        # ** 表示乘方：1 MiB = 2^20 字节，1 GiB = 2^30 字节。
        total_mib = total_bytes / (2 ** 20)
        total_gib = total_bytes / (2 ** 30)

        print(f"\n[{case['name']}]")
        print(f"  K/V 份数                = {key_value_copies}")
        print(f"  layers（层数）          = {layers}")
        print(f"  tokens（每条缓存长度）  = {tokens}")
        print(f"  kv_heads（KV 头数）     = {kv_heads}")
        print(f"  head_dim（每头维度）    = {head_dim}")
        print(f"  bytes_per_element      = {bytes_per_element} 字节/元素")
        print(f"  concurrent_sequences   = {concurrent_sequences} 条并发序列")
        print(f"  单 Token 跨所有层       = {bytes_per_token:,} 字节")
        print(f"  单条序列               = {bytes_per_sequence:,} 字节")
        print(f"  合计                   = {total_bytes:,} 字节 = {total_mib:.2f} MiB = {total_gib:.3f} GiB")

    print("\n边界：只估算标准稠密 KV，不含权重、中间激活、框架开销或量化元数据。")
    print("不同架构、缓存共享和内存分配方式可能改变实际占用。")


def main():
    """程序入口：读取用户选的模式，只运行对应的一个实验。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=["timeline", "capacity"],
        help="timeline：生成时间线；capacity：KV Cache 理论容量",
    )
    args = parser.parse_args()

    if args.mode == "timeline":
        timeline()
    else:
        capacity()


# 直接运行这个文件才启动实验；其他文件 import 它时，不自动执行。
if __name__ == "__main__":
    main()
