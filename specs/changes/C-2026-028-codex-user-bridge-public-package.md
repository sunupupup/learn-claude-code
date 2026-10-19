# 整理 Codex 用户通信插件的公开发布结构

- 状态：done
- 日期：2026-10-20
- 用户授权：整理为规整插件项目、提交并推送到用户 GitHub，公开发布。
- 保留已验证的 Codex 兼容 manifest；根目录放 .codex-plugin、.mcp.json、skills，源码放 src，工具脚本放 scripts。
- 发布配置不能绑定开发机目录；从安装缓存运行并验证两工具发现及收发。
- 增加依赖锁定、独立 marketplace、许可证与快速开始；公开前检查不包含密钥、运行记录、数据库和虚拟环境。
- 最终用户选择：独立公开仓库 [sunupupup/codex-user-bridge](https://github.com/sunupupup/codex-user-bridge)。已推送并核验 main 的 `2c2255f4688c2f4c5a009edc99381b45c2f5ed7e`。
- 用户选择到达前，初始快照已推送到学习仓库 `4992d39`；该快照保留，后续主要源码以独立仓库为准。原学习仓库其余改动保持原状。
- 实现与验证：[I-2026-027](../implementation/I-2026-027-codex-user-bridge-public-package.md)。
