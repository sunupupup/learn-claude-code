# 实操 03：用短期身份凭证替代 Agent 长期密钥

> **具体防护场景：** 防止负责上传前端预览包的 Agent 拿到长期 AWS 密钥，并进一步访问其他业务资源。通过 Cursor 签发的短期身份令牌换取专用角色凭证，只授予指定 S3 桶 previews/ 前缀的上传权限。

## 场景

Cursor Cloud Agent 需要上传一个前端预览包到 S3，但不应持有长期 AWS 密钥，也不应获得其他目录的访问权限。

## 配置代码

这里用 **Cursor Cloud Agent 的 OIDC + AWS STS**，不是本地 Cursor Hook。需要管理员有 AWS IAM 配置权限；Agent 环境已有 Python 3、curl、AWS CLI。

**管理员先注册 OIDC Provider**（已存在时不要重复创建）：

```bash
aws iam create-open-id-connect-provider \
  --url https://api.cursor.com \
  --client-id-list sts.amazonaws.com
```

**文件一：`trust.json`**。把示例 AWS 账号和 `user:42` 换成实际值；`42` 是稳定用户 ID，不是邮箱。

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/api.cursor.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "api.cursor.com:aud": "sts.amazonaws.com",
          "api.cursor.com:sub": "user:42"
        }
      }
    }
  ]
}
```

**文件二：`upload-permissions.json`**。将 `replace-with-your-bucket` 换成已经存在的桶名；角色只授予该前缀的写入权限。

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": ["arn:aws:s3:::replace-with-your-bucket/previews/*"]
    }
  ]
}
```

**管理员创建专用角色并绑定权限**：

```bash
aws iam create-role \
  --role-name CursorPreviewUploader \
  --assume-role-policy-document file://trust.json

aws iam put-role-policy \
  --role-name CursorPreviewUploader \
  --policy-name UploadPreviewsOnly \
  --policy-document file://upload-permissions.json
```

**文件三：Agent 环境内的 `upload_preview.py`**。

```python
import json
import os
import subprocess
import sys
from pathlib import Path


def capture(command):
    # 捕获输出，不把身份令牌或 STS 临时凭证打印到会话。
    result = subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=60
    )
    return json.loads(result.stdout)


def main():
    if len(sys.argv) != 2:
        raise ValueError("用法：python3 upload_preview.py ./preview.zip")
    source = Path(sys.argv[1]).resolve(strict=True)
    if not source.is_file():
        raise ValueError("上传源必须是文件")
    role_arn = os.environ["PREVIEW_ROLE_ARN"]
    bucket = os.environ["PREVIEW_BUCKET"]
    socket_path = os.environ["CURSOR_AGENT_SOCKET"]

    # 当前任务通过宿主本地 socket 获取有签名、短期有效的身份令牌。
    token_response = capture([
        "curl", "--fail", "--silent", "--show-error", "--max-time", "15",
        "--unix-socket", socket_path,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"aud": "sts.amazonaws.com"}),
        "http://cursor-agent/v1/tokens/oidc",
    ])
    credentials = capture([
        "aws", "sts", "assume-role-with-web-identity",
        "--role-arn", role_arn,
        "--role-session-name", "cursor-preview",
        "--web-identity-token", token_response["token"],
        "--duration-seconds", "900",
        "--output", "json", "--no-cli-pager",
    ])["Credentials"]

    # 只传给上传子进程，不写 ~/.aws/credentials，不修改父进程环境。
    upload_env = os.environ.copy()
    upload_env.update({
        "AWS_ACCESS_KEY_ID": credentials["AccessKeyId"],
        "AWS_SECRET_ACCESS_KEY": credentials["SecretAccessKey"],
        "AWS_SESSION_TOKEN": credentials["SessionToken"],
        "AWS_PAGER": "",
    })
    subprocess.run([
        "aws", "s3api", "put-object", "--bucket", bucket,
        "--key", "previews/" + source.name, "--body", str(source),
    ], env=upload_env, check=True, capture_output=True, timeout=120)
    print("预览文件已上传到 previews/ 前缀。")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, OSError, subprocess.SubprocessError):
        # 不打印异常命令，避免其中的 --web-identity-token 进入日志。
        print("上传未完成，请检查角色、身份、桶权限和网络；未输出凭证。", file=sys.stderr)
        sys.exit(1)
```

在 Cloud Agent 的终端配置目标并调用：

```bash
export PREVIEW_ROLE_ARN=arn:aws:iam::123456789012:role/CursorPreviewUploader
export PREVIEW_BUCKET=replace-with-your-bucket
python3 upload_preview.py ./preview.zip
```

## 能起到的作用

- AWS 验证 Cursor 身份，只允许指定用户申请这个角色；实际权限限定为预览前缀的 `PutObject`。
- Cursor OIDC 令牌当前有效期 5 分钟；此例向 STS 申请 15 分钟凭证，两者不是同一个期限。
- 代码不打印或持久化凭证；STS 调用仍会短暂通过子进程参数传令牌。SSE-KMS 桶等额外要求需另配。
- 代码未执行，没有创建云资源。依据：[Cursor OIDC 与 AWS 示例](https://cursor.com/docs/cloud-agent/identity)、[AWS Provider 命令](https://docs.aws.amazon.com/cli/latest/reference/iam/create-open-id-connect-provider.html)。

## 我的笔记

