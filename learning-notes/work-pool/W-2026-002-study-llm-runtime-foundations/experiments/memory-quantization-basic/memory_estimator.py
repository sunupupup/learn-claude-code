"""标准库教学估算：只做算术，不加载模型、不分配权重、不测量 GPU。"""

import argparse
import sys


# Windows 终端编码可能不同；统一为 UTF-8，保证中文教学输出可读。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def size_text(size):
    return f"{size:,} bytes = {size / 10**9:.9f} GB = {size / 2**30:.9f} GiB"


def estimate(params, group_size, mode):
    print("理论 / 教学估算；不是模型文件实测或 GPU 观测。")
    print("1 byte = 8 bit；1 GB = 10^9 bytes；1 GiB = 2^30 bytes。")
    print(f"参数量 N = {params:,}；假设所有权重采用同一位宽。")
    print("权重理论大小 = 参数量 × 每参数字节数 = N × bit / 8")
    for name, bits in [("FP32", 32), ("BF16 / FP16", 16), ("INT8", 8), ("4bit", 4)]:
        # 低位权重按位紧密打包；奇数个 4bit 权重仍需向上取整到整字节。
        packed = (params * bits + 7) // 8
        print(f"{name}: {params:,} × {bits / 8:g} = {params * bits / 8:,.1f} bytes"
              f"；整字节打包后 {size_text(packed)}")
    if mode == "weights":
        return

    # 这是自定义教学布局，不代表任何真实量化格式；尾组也占一组元数据。
    groups = (params + group_size - 1) // group_size
    payload = (params * 4 + 7) // 8
    scale = groups * 2
    zero_point = groups * 1
    group_metadata = groups * 1
    quantized = payload + scale + zero_point + group_metadata
    print("\n量化辅助数据：假定每组 scale（缩放因子）2 bytes、")
    print("zero-point（零点偏移）1 byte、额外分组描述 1 byte。")
    print("实际格式可能省略零点或隐式描述分组；这里仅演示开销。")
    print(f"每组最多 {group_size} 个参数；组数 = ceil(N / group_size) = {groups:,}")
    print(f"4bit 数据 {payload:,} + scale {scale:,} + zero-point {zero_point:,}"
          f" + 分组描述 {group_metadata:,} = {size_text(quantized)}")
    print(f"含上述辅助数据 / FP16 纯权重 = {quantized / (params * 2):.2%}，不必等于 25%。")
    print("尚未计入文件头、对齐填充、未量化张量；这不是实际文件大小预测。")

    # 故意使用独立的小常数，不把其他运行开销假装成由参数量决定的比例。
    extras = {"KV Cache（历史键值缓存）": 4096, "中间激活": 2048,
              "临时工作区": 1024, "框架与分配器额外开销": 1024}
    print("\n总运行显存账本：假设权重以紧凑格式驻留 GPU，其他项仅为任意教学数值。")
    print("各项假设同时存活且不重复计数；不代表真实峰值或推荐预留量。")
    for name, size in extras.items():
        print(f"{name}: {size:,} bytes（人为假设）")
    print(f"假设总量 = 权重及量化辅助数据 + 上述四项 = {size_text(quantized + sum(extras.values()))}")
    print("7B 模式也沿用这些玩具常数，只用于演示加法，不能作为部署容量预算。")
    print("只量化权重不会自动缩小 KV Cache；缓存还取决于架构、长度、并发与缓存位宽。")
    print("\n量化减少权重存储 / 显存；是否加速取决于硬件、推理内核和实际瓶颈。")
    print("位宽不能直接推出速度倍数或质量分数；本实验不执行量化、不评测速度或质量。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--params", type=int, default=1024,
                        help="参数个数；7B 数量级可传 7000000000，仅做算术")
    parser.add_argument("--group-size", type=int, default=128, help="教学分组大小")
    parser.add_argument("--mode", choices=["weights", "all"], default="weights",
                        help="默认只比较权重；all 展示元数据与运行显存账本")
    args = parser.parse_args()
    if args.params <= 0 or args.group_size <= 0:
        parser.error("参数个数和分组大小必须为正整数")
    estimate(args.params, args.group_size, args.mode)
