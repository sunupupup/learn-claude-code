# RTK 实验结果索引：git log / pnpm list

2026-09-25 · Windows · RTK 0.50.0 · pnpm 10.29.2。

## 对比结果

| 实验记录（点击查看命令及完整前后输出） | 普通输出 | RTK 输出 | 字节减少 |
| --- | ---: | ---: | ---: |
| [git log：同样 20 条提交](experiments/2026-09-25-rtk-output-comparison/git_log.md) | 3615 B / 119 行 | 1656 B / 20 行 | **54.19%** |
| [pnpm list：web 项目](experiments/2026-09-25-rtk-output-comparison/pnpm_list.md) | 552 B / 28 行 | 487 B / 25 行 | **11.78%** |

口径：直接比较命令 stdout 的原始字节，减少比例 = 1 − RTK 字节 / 普通输出字节。不是 token 或整次任务费用；stderr 差异见具体实验记录。

## 学到了什么

- 本样本没有达到[官网](https://www.rtk-ai.app/docs/resources/what-rtk-covers/)所列的 git log 80–92%、pnpm list 70–90%。
- git log 主要省掉详细元数据与空行，实际仍保留相对时间；Git 原生精简格式也有效，详见 Git 对比。
- pnpm 的普通列表本来就短；以内部 JSON 为基线可得到 93.08%，但与普通列表相比只有 11.78%。不能混用分母，也未核验官网采用何种具体样本。
- RTK 把根项目 web 计入包数：显示 22，其中直接依赖实际为 21。

## 环境与清理

使用[官方 Windows 便携包](https://github.com/rtk-ai/rtk/releases/tag/v0.50.0)，下载 SHA256 已核对。没有启用 Hook、修改 PATH 或安装项目依赖；RTK 程序、安装包与临时数据库均已删除。

本实验仅保留本索引和上面链接的两份对比记录。每份记录集中保存命令、条件、完整前后输出、指标及解释；不保留空 stderr、重复原始日志和零散指标 JSON。
