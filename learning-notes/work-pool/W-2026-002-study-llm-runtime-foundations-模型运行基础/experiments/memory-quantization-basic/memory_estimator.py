"""显存与量化入门：只做算术，不加载模型、不分配权重、不测量 GPU。

阅读路线：先看文件底部的 main()，再按调用顺序阅读各个函数。
默认流程：读取命令行参数 → 比较四种格式的纯权重大小 → 结束。
选择 --mode all 后：继续计算量化辅助数据 → 累加运行显存的教学账本。

这里的“参数”有两种含义：
- 模型参数：训练得到的权重数字，本实验只知道它们的个数。
- 命令行参数：运行脚本时提供的选项，例如 --params 1024。
即使指定 70 亿个模型参数，程序也只计算几个数字，不创建 70 亿个权重。
"""

import argparse
import sys


# Windows 终端编码可能不同；统一为 UTF-8，保证中文教学输出可读。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def size_text(size):
    """把同一个字节数换成三种单位，方便比较；不会改变实际大小。"""
    # ** 是乘方；GB 按十进制换算，GiB 按二进制换算，两者数值不同。
    # f 字符串中的 :, 添加千位分隔符，:.9f 表示保留 9 位小数。
    return f"{size:,} bytes = {size / 10**9:.9f} GB = {size / 2**30:.9f} GiB"


def show_weight_sizes(parameter_count):
    """第一步：参数个数不变，只改变每个参数占多少 bit（二进制位）。"""
    print("\n[1] 纯权重大小：先不计量化辅助数据")
    print("权重理论大小 = 参数量 × 每参数字节数 = N × bit / 8")
    # 每一项由“格式名称、每个参数的位数”组成；循环逐个取出并计算。
    formats = [("FP32", 32), ("BF16 / FP16", 16), ("INT8", 8), ("4bit", 4)]
    for name, bits_per_parameter in formats:
        bytes_per_parameter = bits_per_parameter / 8
        theoretical_bytes = parameter_count * bytes_per_parameter

        # 两个 4bit 权重可以合放进 1 byte；单个 4bit 权重也至少占 1 byte。
        # // 是整除：总位数加 7 后再除以 8，得到向上取整的字节数。
        total_bits = parameter_count * bits_per_parameter
        packed_bytes = (total_bits + 7) // 8
        print(f"{name}: {parameter_count:,} × {bytes_per_parameter:g}"
              f" = {theoretical_bytes:,.1f} bytes"
              f"；整字节打包后 {size_text(packed_bytes)}")


def show_quantization_overhead(parameter_count, group_size):
    """第二步：给 4bit 纯权重加上辅助数据，返回合计字节数。"""
    # 量化后的数字需要辅助信息来解释：scale 表示刻度间隔，zero-point 表示零点偏移。
    # “分组”表示一批权重共用辅助信息，而不是每个权重单独保存一份。
    # 这是自定义教学布局，不代表任何真实量化格式。
    # 例如 129 个参数，每组最多 128 个，需要 2 组；不足一组也按一组计。
    groups = (parameter_count + group_size - 1) // group_size
    weight_bytes = (parameter_count * 4 + 7) // 8
    scale_bytes = groups * 2
    zero_point_bytes = groups * 1
    group_metadata_bytes = groups * 1
    quantized_bytes = weight_bytes + scale_bytes + zero_point_bytes + group_metadata_bytes
    fp16_bytes = parameter_count * 2

    print("\n[2] 量化辅助数据：假定每组 scale（缩放因子）2 bytes、")
    print("zero-point（零点偏移）1 byte、额外分组描述 1 byte。")
    print("实际格式可能省略零点或隐式描述分组；这里仅演示开销。")
    print(f"每组最多 {group_size} 个参数；组数 = ceil(N / group_size) = {groups:,}")
    print(f"4bit 数据 {weight_bytes:,} + scale {scale_bytes:,} + zero-point {zero_point_bytes:,}"
          f" + 分组描述 {group_metadata_bytes:,} = {size_text(quantized_bytes)}")
    # :.2% 把比例显示成百分数，并保留两位小数。
    print(f"含上述辅助数据 / FP16 纯权重 = {quantized_bytes / fp16_bytes:.2%}，不必等于 25%。")
    print("尚未计入文件头、对齐填充、未量化张量；这不是实际文件大小预测。")
    return quantized_bytes


def show_runtime_memory(quantized_bytes):
    """第三步：权重只是运行显存的一部分；把其他项目也列入账本。"""
    # KV Cache：保存历史 token 的 K/V，供后续生成使用。
    # 中间激活：模型计算途中产生的数值；临时工作区：运算额外需要的暂存空间。
    # 框架与分配器：运行程序及管理显存的组件，也会带来额外占用。
    # 故意使用独立的小常数，不把其他运行开销假装成由参数量决定的比例。
    extras = {"KV Cache（历史键值缓存）": 4096, "中间激活": 2048,
              "临时工作区": 1024, "框架与分配器额外开销": 1024}
    print("\n[3] 总运行显存账本：假设权重以紧凑格式驻留 GPU，其他项仅为任意教学数值。")
    print("各项假设同时存活且不重复计数；不代表真实峰值或推荐预留量。")
    for name, size in extras.items():
        print(f"{name}: {size:,} bytes（人为假设）")
    # 字典把“项目名”对应到“字节数”；values() 取出数字，sum() 将它们相加。
    extra_bytes = sum(extras.values())
    total_bytes = quantized_bytes + extra_bytes
    print(f"假设总量 = 权重及量化辅助数据 + 上述四项 = {size_text(total_bytes)}")
    print("7B 模式也沿用这些玩具常数，只用于演示加法，不能作为部署容量预算。")
    print("只量化权重不会自动缩小 KV Cache；缓存还取决于架构、长度、并发与缓存位宽。")
    print("\n量化减少权重存储 / 显存；是否加速取决于硬件、推理内核和实际瓶颈。")
    print("位宽不能直接推出速度倍数或质量分数；本实验不执行量化、不评测速度或质量。")


def read_arguments():
    """读取并检查命令行选项；没传选项时使用 default 指定的默认值。"""
    # argparse 是 Python 自带的命令行解析工具，不需要安装第三方库。
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--params", type=int, default=1024,
                        help="参数个数；7B 数量级可传 7000000000，仅做算术")
    parser.add_argument("--group-size", type=int, default=128, help="教学分组大小")
    parser.add_argument("--mode", choices=["weights", "all"], default="weights",
                        help="默认只比较权重；all 展示元数据与运行显存账本")
    # type=int 把输入转成整数；choices 限定允许的模式。
    # --group-size 中的连字符会转成下划线，因此代码里使用 args.group_size。
    args = parser.parse_args()
    # 必须先检查，避免用零作除数，或计算没有意义的负数大小。
    if args.params <= 0 or args.group_size <= 0:
        parser.error("参数个数和分组大小必须为正整数")
    return args


def main():
    """总流程：先读这里，再进入每个函数看细节。"""
    args = read_arguments()

    print("理论 / 教学估算；不是模型文件实测或 GPU 观测。")
    print("1 byte = 8 bit；1 GB = 10^9 bytes；1 GiB = 2^30 bytes。")
    print(f"参数量 N = {args.params:,}；假设所有权重采用同一位宽。")

    show_weight_sizes(args.params)
    # 默认在第一步停下，便于先完成手算核对；return 表示结束当前函数。
    if args.mode == "weights":
        return

    # 第二步返回的合计字节数，正是第三步账本中的权重部分。
    quantized_bytes = show_quantization_overhead(args.params, args.group_size)
    show_runtime_memory(quantized_bytes)


# 直接运行本文件时才开始实验；被其他 Python 文件导入时不自动运行。
if __name__ == "__main__":
    main()
