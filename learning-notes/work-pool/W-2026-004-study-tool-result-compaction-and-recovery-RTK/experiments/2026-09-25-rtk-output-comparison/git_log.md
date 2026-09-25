# git log：原始输出与 RTK 输出

实验日期：2026-09-25；Windows；RTK 0.50.0；pnpm 10.29.2。以下输出保留当时捕获内容，字节统计来自原始 stdout，不包含 Markdown 包装。

[返回结果索引](../../result_pnpm_list.md)

| 输出 | 字节 | 行数 |
| --- | ---: | ---: |
| 普通 git log | 3615 | 119 |
| RTK | 1656 | 20 |

减少 **54.19%**。


工作目录：仓库根目录。固定提交 e306786e42927b7f463ba26547f4f7a3c3ed9021，两边均取同样的 20 条提交。

```text
git --no-pager log -n 20 e306786e42927b7f463ba26547f4f7a3c3ed9021
rtk git log -n 20 e306786e42927b7f463ba26547f4f7a3c3ed9021
```

RTK 保留短 Hash、主题、相对时间、作者；实际比文档的 Hash + author + subject 多了相对时间。省略完整 Hash、邮箱、精确日期及空行等。相对时间随运行日期变化。

### 普通输出（完整）

```text
commit e306786e42927b7f463ba26547f4f7a3c3ed9021
Author: ant sun <2293261394@qq.com>
Date:   Thu Sep 24 01:13:10 2026 +0800

    docs: record RTK source walkthrough and tool output compression

commit 2d027c98f0c48b84a62583d551f3885bfad88ef7
Author: ant sun <2293261394@qq.com>
Date:   Thu Sep 24 01:12:53 2026 +0800

    docs: activate RTK study and repair task references

commit a24842707eba80f6b26469d799a7cd1efe09e1c8
Author: ant sun <2293261394@qq.com>
Date:   Thu Sep 24 01:11:22 2026 +0800

    docs: add observability glossary

commit fad614c9d4977d3a151474102eb3d785c8b18023
Author: ant sun <2293261394@qq.com>
Date:   Thu Sep 24 01:08:42 2026 +0800

    docs: add PIR observability learning notes

commit 62a30d5e3a153e7e1eaf9caca8ff2ce2cde9f0d8
Author: ant sun <2293261394@qq.com>
Date:   Wed Sep 23 23:07:42 2026 +0800

    docs: note personal assistant agent memory layers

commit 572fe52110547de6000cf919660930e65e208f24
Author: ant sun <2293261394@qq.com>
Date:   Wed Sep 23 22:59:28 2026 +0800

    docs: summarize specialist models workflows and fine-tuning

commit 5e1d572fa7ce7f8f1913d273699b4387c8ba4c04
Author: ant sun <2293261394@qq.com>
Date:   Wed Sep 23 22:56:37 2026 +0800

    docs: add self-evolution glossary and DeepSeek RSI notes

commit 37b774a424ea867b06cd60ede3d3ac8b34bc88bf
Author: ant sun <2293261394@qq.com>
Date:   Wed Sep 23 19:26:27 2026 +0800

    docs: define work pool learning start rules

commit a1cf4cbb13ae67b797c5500e148691bbb9c77829
Author: ant sun <2293261394@qq.com>
Date:   Mon Sep 21 02:14:06 2026 +0800

    docs: expand self-evolution work pool learning scope

commit b5b6a6ce5a56bbf3045486d8829b0f68d5d77252
Author: ant sun <2293261394@qq.com>
Date:   Mon Sep 21 02:13:53 2026 +0800

    docs: add agent self-evolution research and learning notes

commit e0482032c448f502f14a75d955ecfbbfc48b8e71
Author: ant sun <2293261394@qq.com>
Date:   Sun Sep 20 19:51:12 2026 +0800

    docs: activate W-016 learning change and update references

commit fae7186d1481b8ca843098c1ac27d76170935d45
Author: ant sun <2293261394@qq.com>
Date:   Sun Sep 20 19:50:43 2026 +0800

    docs: record agent control flow and Codex plan mode study

commit 85399a5a27b28ffe75eef090e283dc58aa096678
Author: ant sun <2293261394@qq.com>
Date:   Sun Sep 20 19:50:06 2026 +0800

    docs: track AI hallucination learning change

commit 627cdcb8df4054f796ed238cad5e76d3e4612175
Author: ant sun <2293261394@qq.com>
Date:   Sun Sep 20 19:49:45 2026 +0800

    docs: record AI hallucination learning notes

commit a6e0320e4991c80185113b39059c7e5acc32e2ec
Author: ant sun <2293261394@qq.com>
Date:   Sun Sep 20 17:58:19 2026 +0800

    docs: rename learning directories and sync notes

commit f63f486e19f31e5b9c1bec38c9d2eea3c7dcee75
Author: ant sun <2293261394@qq.com>
Date:   Sun Sep 20 17:46:03 2026 +0800

    docs: add concise Jev learning note

commit 1f2883d8e2dcba1e727cafb6a8aea3c2d93dc309
Author: ant sun <2293261394@qq.com>
Date:   Sun Sep 20 17:44:56 2026 +0800

    docs: require chapter knowledge maps and direct main updates

commit 8cbca20ee7f3f08f2cbc9618ac6b27d184e68e93
Author: ant sun <2293261394@qq.com>
Date:   Sun Sep 20 17:01:21 2026 +0800

    docs(spec): close W-2026-025 learning chapter

commit 70e65d5d318bd2e3484bceae9fb8612d96e781c2
Author: ant sun <2293261394@qq.com>
Date:   Sun Sep 20 16:59:58 2026 +0800

    docs(rag): archive knowledge management notes and teaching demos

commit 13af6cfe040fb34c3d941ccda0f6b36e648e4fda
Author: ant sun <2293261394@qq.com>
Date:   Sat Sep 19 23:41:57 2026 +0800

    docs: 完善 Work Pool 学习笔记规则与完成标准
```

### RTK 输出（完整）

```text
e306786 docs: record RTK source walkthrough and tool output compression (2 days ago) <ant sun>
2d027c9 docs: activate RTK study and repair task references (2 days ago) <ant sun>
a248427 docs: add observability glossary (2 days ago) <ant sun>
fad614c docs: add PIR observability learning notes (2 days ago) <ant sun>
62a30d5 docs: note personal assistant agent memory layers (2 days ago) <ant sun>
572fe52 docs: summarize specialist models workflows and fine-tuning (2 days ago) <ant sun>
5e1d572 docs: add self-evolution glossary and DeepSeek RSI notes (2 days ago) <ant sun>
37b774a docs: define work pool learning start rules (2 days ago) <ant sun>
a1cf4cb docs: expand self-evolution work pool learning scope (5 days ago) <ant sun>
b5b6a6c docs: add agent self-evolution research and learning notes (5 days ago) <ant sun>
e048203 docs: activate W-016 learning change and update references (5 days ago) <ant sun>
fae7186 docs: record agent control flow and Codex plan mode study (5 days ago) <ant sun>
85399a5 docs: track AI hallucination learning change (5 days ago) <ant sun>
627cdcb docs: record AI hallucination learning notes (5 days ago) <ant sun>
a6e0320 docs: rename learning directories and sync notes (5 days ago) <ant sun>
f63f486 docs: add concise Jev learning note (5 days ago) <ant sun>
1f2883d docs: require chapter knowledge maps and direct main updates (5 days ago) <ant sun>
8cbca20 docs(spec): close W-2026-025 learning chapter (5 days ago) <ant sun>
70e65d5 docs(rag): archive knowledge management notes and teaching demos (5 days ago) <ant sun>
13af6cf docs: 完善 Work Pool 学习笔记规则与完成标准 (6 days ago) <ant sun>
```

### Git 自带精简格式的对照

| 格式（同样 20 条提交） | 字节 | 相对普通 git log 减少 |
| --- | ---: | ---: |
| git log --oneline | 1196 | 66.92% |
| git log --format=%h %an %s | 1356 | 62.49% |
| rtk git log | 1656 | 54.19% |

oneline 不含作者；fields 不含相对时间。信息量不同，不能只比长度认定优劣。本样本中 Git 原生格式化已经有效。

所有命令退出码为 0。RTK 首次运行在 stderr 输出 78 字节的未安装 Hook 提示；主表仅比较 stdout。若将这条提示也算入，RTK 总计 1734 字节，减少 52.03%。不是执行失败。
