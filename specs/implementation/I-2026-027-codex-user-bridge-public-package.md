# Codex 用户通信插件公开结构整理

- 日期：2026-10-20
- 对应变更：[C-2026-028](../changes/C-2026-028-codex-user-bridge-public-package.md)
- 版本：0.2.0；官方支持的 Codex 兼容布局。
- 根目录插件清单、相对 cwd MCP 配置、skills；src 源码；scripts 工具；pyproject 与 uv.lock；MIT LICENSE。
- 10 项检查通过，隔离配置安装、宿主工具发现与缓存副本真实收发通过。
- 公开扫描排除本地数据、虚拟环境和开发机路径。详细边界见[阶段验收](../../practice/codex-user-bridge/docs/validation.md)。
- 最终发布：[sunupupup/codex-user-bridge](https://github.com/sunupupup/codex-user-bridge)，PUBLIC，main=`2c2255f4688c2f4c5a009edc99381b45c2f5ed7e`，已用远端 ref 核验。
- 独立本地目录位于学习仓库之外，未使用 worktree；干净源码重新安装依赖、10 项检查及缓存副本收发通过。
- 学习仓库保留初始实战快照，并链接独立仓库作为主要来源。只提交当前插件及相关入口，不包含其他学习改动。
