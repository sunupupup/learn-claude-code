# screenshot-to-code

将截图、设计稿和录屏等输入转换为网页代码的开源应用，前端使用 React/Vite，后端使用 FastAPI。
当前源码包含 Agent 工具调用循环与渲染截图反馈，可用于学习页面生成、预览与视觉检查的衔接；实际生成效果待运行验证。

- 官方仓库：https://github.com/abi/screenshot-to-code
- 个人 fork：https://github.com/sunupupup/screenshot-to-code
- 学习对象：应用本体及其 Harness（模型外围的执行与支撑程序），不是某个框架插件。
- 本次研究范围：开源 `main` 分支的截图生成路径，涉及 `frontend/src`、`backend/routes`、`backend/prompts` 与 `backend/agent`。
- 本地源码：[临时源码目录](源码/README.md)；按本次学习要求放在项目目录内，已通过本地 Git 排除规则避免纳入学习仓库版本管理。
- 许可证：根目录 `LICENSE` 已核验为 MIT；源码版本与证据状态见模块笔记。

## 学习模块

- [工作流阅读地图](工作流.md)：先按上传、请求准备、生成、预览的顺序看源码，再深入 Agent Loop。
- [截图到代码与视觉反馈](截图到代码与视觉反馈.md)：上传一张截图后，代码如何生成并显示在预览里？已初始化。
