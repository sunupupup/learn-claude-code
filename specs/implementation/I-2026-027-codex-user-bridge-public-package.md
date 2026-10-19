# Codex 用户通信插件公开结构整理

- 日期：2026-10-20
- 对应变更：[C-2026-028](../changes/C-2026-028-codex-user-bridge-public-package.md)
- 版本：0.2.0；官方支持的 Codex 兼容布局。
- 根目录插件清单、相对 cwd MCP 配置、skills；src 源码；scripts 工具；pyproject 与 uv.lock；MIT LICENSE。
- 10 项检查通过，隔离配置安装、宿主工具发现与缓存副本真实收发通过。
- 公开扫描排除本地数据、虚拟环境和开发机路径。详细边界见[阶段验收](../../practice/codex-user-bridge/docs/validation.md)。
- 发布目标：现有公开 sunupupup/learn-claude-code 的 main；只提交当前插件及相关目录、Spec 入口，不包含其他学习改动。
