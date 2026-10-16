# 实操 04：PR 越界自动评论，并阻止合并

> **具体防护场景：** 防止国际化人员把组件或业务代码的越界改动直接合入主分支。通过检查 PR 的完整改动文件列表，自动发布告警 comment，并把角色范围检查设为合并前必须通过；需要人工审阅时再结合代码负责人规则。

## 场景

国际化用户 A 只应修改 `i18n/` 翻译资源。A 或她的 Agent 提交 PR 后，发现修改组件等范围外文件时，自动评论警告，并产生失败的必需检查。

## 配置代码

使用 **GitHub Actions + GitHub Check + 分支规则**。不依赖模型决定是否报警，不需要 GitHub MCP。这里按 PR 发起人分配责任；机器人代建 PR 时不能直接套用，需要另行记录真实委托人。

**文件：业务仓库的 `.github/workflows/role-scope.yml`**。先替换下面两个示例 GitHub 数字用户 ID；不是 Git name，也不是邮箱。

```yaml
name: Role Scope Gate

on:
  pull_request_target:
    types: [opened, synchronize, reopened, ready_for_review]

permissions:
  contents: read
  pull-requests: write
  checks: write

concurrency:
  group: role-scope-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  scope-gate:
    runs-on: ubuntu-latest
    steps:
      # 使用目标分支受信任的工作流；绝不 checkout / 执行 PR 的代码。
      - uses: actions/github-script@v9
        with:
          script: |
            const { owner, repo } = context.repo;
            const pull_number = context.payload.pull_request.number;
            const { data: pr } = await github.rest.pulls.get({ owner, repo, pull_number });
            const sha = pr.head.sha;
            const authorId = String(pr.user.id);

            // 管理员配置的授权表：12345678 仅翻译；87654321 为完整开发权限。
            // 未登记用户默认失败，不能把“查不到身份”当作全权限。
            const policies = {
              "12345678": "i18n-only",
              "87654321": "developer"
            };
            const role = policies[authorId];
            const marker = "<!-- role-scope-check -->";
            const { data: check } = await github.rest.checks.create({
              owner, repo, name: "role-scope", head_sha: sha,
              status: "in_progress"
            });

            let conclusion = "failure";
            let summary = "范围检查未完成。";
            let invalid = [];
            try {
              const files = await github.paginate(github.rest.pulls.listFiles, {
                owner, repo, pull_number, per_page: 100
              });
              // API 最多返回 3000 个文件；文件列表不完整时拒绝判定通过。
              if (files.length !== pr.changed_files) {
                throw new Error("未取得完整文件列表，需负责人人工检查。");
              }
              if (!role) throw new Error("PR 发起人尚未登记修改权限。");

              function allowed(name) {
                if (role === "developer") return true;
                // 包含 i18n 的所有子目录，只接受明确的翻译资源扩展名。
                return name.startsWith("i18n/") &&
                  !name.split("/").includes("..") &&
                  /\.(json|ya?ml|po|properties)$/i.test(name);
              }
              for (const file of files) {
                // 重命名必须同时检查原路径和新路径，不能靠改名搬出代码。
                for (const name of [file.filename, file.previous_filename].filter(Boolean)) {
                  if (!allowed(name)) invalid.push(name);
                }
              }
              invalid = [...new Set(invalid)];
              const { data: latest } = await github.rest.pulls.get({ owner, repo, pull_number });
              if (latest.head.sha !== sha || latest.base.sha !== pr.base.sha) {
                throw new Error("检查期间 PR 版本发生变化，请重新运行。");
              }
              conclusion = invalid.length ? "failure" : "success";
              summary = invalid.length
                ? "警告！当前角色修改了允许范围外的文件，请代码负责人确认。"
                : "当前 PR 的全部改动文件符合角色允许范围。";
            } catch (error) {
              summary = String(error.message);
            }

            // 文件名按文本转义；评论只展示前 100 个，检查本身处理全部文件。
            const shown = invalid.slice(0, 100).map(name =>
              "- " + JSON.stringify(name).replace(/</g, "&lt;").replace(/`/g, "\\`")
            );
            const body = [
              marker, "### Agent 修改范围检查", summary,
              "用户 ID：" + authorId,
              "检查版本：" + sha,
              "允许范围：" + (role === "developer" ? "完整开发权限" : "i18n/ 翻译资源"),
              ...shown,
              ...(invalid.length > 100 ? ["其余越界文件见检查记录。"] : [])
            ].join("\n\n");

            // 重复推送更新同一条机器人评论，不修改其他人的评论。
            const comments = await github.paginate(github.rest.issues.listComments, {
              owner, repo, issue_number: pull_number, per_page: 100
            });
            const old = comments.find(comment =>
              comment.user.login === "github-actions[bot]" &&
              comment.body?.startsWith(marker)
            );
            if (old) {
              await github.rest.issues.updateComment({ owner, repo, comment_id: old.id, body });
            } else {
              await github.rest.issues.createComment({ owner, repo, issue_number: pull_number, body });
            }
            await github.rest.checks.update({
              owner, repo, check_run_id: check.id, status: "completed", conclusion,
              output: { title: "角色修改范围", summary: body }
            });
            if (conclusion === "failure") core.setFailed(summary);
```

必须在仓库规则中启用：**Require a pull request before merging** 和 **Require status checks to pass**，将 `role-scope` 设为必需检查，并限制 bypass。仅放工作流而不设置必需检查，不能阻止合并。

如果还需要负责人批准，增加 **`.github/CODEOWNERS`**，替换组织和团队名，并开启 **Require review from Code Owners**：

```text
# 所有文件由开发团队审阅；翻译资源交国际化负责人。
*                       @YOUR-ORG/developers
/i18n/                  @YOUR-ORG/localization-leads
# 工作流和权限表由治理负责人负责，不能由受限用户自行放宽。
/.github/               @YOUR-ORG/governance-admins
```

## 能起到的作用

- A 修改组件时自动报警，`role-scope` 失败；强制分支规则负责阻止合并。
- 翻译资源合规时通过；重命名、删除等文件变更都会进入范围判断。
- 只读 GitHub API 数据，不执行 PR 中的脚本；仍需保护工作流、检查来源和 bypass 权限，强要求可改用独立 GitHub App 产生检查。
- 未部署或运行。依据：[GitHub Script](https://github.com/actions/github-script)、[必需检查](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)、[PR 文件 API](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests-files)。

## 我的笔记

