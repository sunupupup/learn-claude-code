# pnpm list：原始输出与 RTK 输出

实验日期：2026-09-25；Windows；RTK 0.50.0；pnpm 10.29.2。以下输出保留当时捕获内容，字节统计来自原始 stdout，不包含 Markdown 包装。

[返回结果索引](../../result_pnpm_list.md)

| 输出 | 字节 | 行数 |
| --- | ---: | ---: |
| 普通 pnpm list | 552 | 28 |
| RTK | 487 | 25 |

减少 **11.78%**。


工作目录：web/。执行 pnpm list 和 rtk pnpm list，两者退出码均为 0，stderr 均为空。

### 普通输出（完整）

```text
Legend: production dependency, optional only, dev only

web@0.1.0 D:\code\third-party-labs\agent\learn-claude-code\web (PRIVATE)

dependencies:
diff 8.0.4
framer-motion 12.38.0
lucide-react 0.564.0
next 16.1.6
react 19.2.3
react-dom 19.2.3
rehype-highlight 7.0.2
rehype-raw 7.0.0
rehype-stringify 10.0.1
remark-gfm 4.0.1
remark-parse 11.0.0
remark-rehype 11.1.2
tsx 4.21.0
unified 11.0.5

devDependencies:
@tailwindcss/postcss 4.2.2
@types/diff 7.0.2
@types/node 20.19.37
@types/react 19.2.14
@types/react-dom 19.2.3
tailwindcss 4.2.2
typescript 5.9.3
```

### RTK 输出（完整）

```text
22 packages (15 prod / 7 dev)
[prod]
  web 0.1.0
  rehype-raw 7.0.0
  remark-parse 11.0.0
  diff 8.0.4
  next 16.1.6
  rehype-stringify 10.0.1
  react-dom 19.2.3
  rehype-highlight 7.0.2
  react 19.2.3
  lucide-react 0.564.0
  remark-gfm 4.0.1
  tsx 4.21.0
  framer-motion 12.38.0
  remark-rehype 11.1.2
  unified 11.0.5
[dev]
  @types/react 19.2.14
  @types/node 20.19.37
  @types/diff 7.0.2
  @types/react-dom 19.2.3
  @tailwindcss/postcss 4.2.2
  tailwindcss 4.2.2
  typescript 5.9.3
```

### 源码解释与统计口径

RTK v0.50.0 的 run_list 先执行 pnpm list --depth=... --json，解析 JSON 后重新排版，并以该 JSON 作为内部体积统计的输入；并非只把普通文本输出删几行。

额外执行 pnpm list --depth=0 --json，得到 7039 字节；JSON → RTK 的 487 字节减少 93.08%，但普通文本 → RTK 只减少 11.78%。分母不同，不能混用。本次未通过 rtk gain 核对其展示值，也不据此断言官网百分比使用了这一基线。

数量核验：package.json 与 pnpm JSON 均为 14 个生产依赖、7 个开发依赖，共 21 个直接依赖。RTK 的 22 packages（15 prod / 7 dev）包含根项目 web 0.1.0；collect_dependencies 从根节点开始收集，与这一观察一致。不能把 22 理解成直接依赖数。输出顺序也发生变化。


源码依据：[run_list](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/cmds/js/pnpm_cmd.rs#L381)、[collect_dependencies](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/cmds/js/pnpm_cmd.rs#L101)。

复测条件：需要恢复当时 web 的已安装依赖版本；仅使用相同 package.json 不能保证版本相同。版本清单见上方捕获输出。JSON 原始临时文件已清理，7039 字节为当时实测记录。
