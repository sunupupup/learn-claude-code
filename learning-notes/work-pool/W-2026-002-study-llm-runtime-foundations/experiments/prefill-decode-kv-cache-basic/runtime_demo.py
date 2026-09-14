"""标准库教学模拟：虚拟时间和 KV 理论容量，不执行模型或测量 GPU。"""

import argparse
import sys


# Windows 终端编码可能不同；统一为 UTF-8，保证中文教学输出可读。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def timeline():
    # 数字是人为设定的虚拟毫秒；累加而非 sleep，避免被误认成实测。
    now = 0
    cached = []
    print("教学模拟；P1..P4 / O1..O3 是假定的 Token 标签。")
    stages = [
        ("排队及输入准备", 5, [], None),
        ("Prefill", 8, ["P1", "P2", "P3", "P4"], "O1"),
        ("Decode 1", 2, ["O1"], "O2"),
        ("Decode 2", 2, ["O2"], "O3"),
    ]
    for phase, duration, inputs, output in stages:
        start = now
        now += duration
        # 列表只代表每层缓存对应的位置，不是真实 Key/Value 张量。
        cached.extend(inputs)
        print(f"{start:2} -> {now:2} 虚拟 ms | {phase} | "
              f"处理={inputs} | 输出={output} | 已缓存位置={len(cached)}")
        if output == "O1":
            print(f"模拟 TTFT={now} ms（选择 Token 和传输在本例设为 0）")
    # 最后一个输出若不再送入模型，就没有它自身的 K/V。
    print("达到 3 个输出后停止；O3 尚未被前向处理，缓存对应 6 个位置。")


def capacity():
    print("标准稠密 KV 理论估算；不是总显存，也不实际分配内存。")
    print("bytes = 2 × layers × tokens × kv_heads × head_dim × bytes_per_element × concurrent_sequences")
    # 每组只改变一个变量；tokens 是每条序列已缓存的总长度。
    cases = [
        ("基线", 1024, 1, 2),
        ("上下文翻倍", 2048, 1, 2),
        ("并发翻倍", 1024, 2, 2),
        ("元素改为 1 字节", 1024, 1, 1),
    ]
    for label, tokens, sequences, element_bytes in cases:
        layers, kv_heads, head_dim = 32, 8, 128
        size = 2 * layers * tokens * kv_heads * head_dim * element_bytes * sequences
        print(f"\n{label}: K/V份数=2, layers={layers}, tokens={tokens}, "
              f"kv_heads={kv_heads}, head_dim={head_dim}, "
              f"bytes_per_element={element_bytes}, concurrent_sequences={sequences}")
        print(f"理论占用={size:,} bytes = {size / 2**20:.2f} MiB = {size / 2**30:.3f} GiB")
    print("假设等长序列、各层尺寸相同且不共享前缀；量化元数据、分配粒度和架构会带来差异。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["timeline", "capacity"])
    args = parser.parse_args()
    if args.mode == "timeline":
        timeline()
    else:
        capacity()
