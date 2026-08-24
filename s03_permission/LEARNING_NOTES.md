# s03 Permission 学习笔记

> 学习进度：已完成（D1 核心验收通过）；运行实验与 Web 断线恢复属于后续巩固和生产扩展。

## 一、本章核心结论

模型生成 `tool_use`，只代表它**提出了一个工具调用请求**，不代表这个动作已经获准执行。Harness 必须在调用 Handler 之前执行权限判断。

当前教学代码的主流程是：

```text
模型生成 tool_use
        ↓
Harness 调用 check_permission()
        ↓
硬拒绝规则 ──命中──→ 不执行
        ↓ 未命中
上下文规则 ──命中──→ ask_user() 阻塞等待人工决定
        ↓ 未命中             ├─ deny → 不执行
        ↓                    └─ allow → 继续
调用 TOOL_HANDLERS 中的 Handler
        ↓
构造 tool_result 返回模型
```

权限相关逻辑要放在副作用发生之前。不能让模型通过 Prompt 自己决定是否有权执行。

## 二、与 s02 衔接的四层边界

| 层次 | 回答的问题 | 本章示例 |
|---|---|---|
| 结构 / Schema 校验 | 输入形状和类型是否正确 | `path`、`command` 是否为字符串 |
| 业务规则校验 | 操作是否符合业务状态和约束 | 已关闭任务是否允许修改 |
| 权限 / 策略判定 | 当前身份是否获准执行 | `allow`、`ask`、`deny` |
| 获准后的执行防护 | 即使获准，怎样限制真实副作用 | `safe_path`、沙箱、幂等、备份、回滚 |

参数合法不代表操作已经获得授权；获得授权也不代表可以移除执行防护。

## 三、我的原始理解

1. 路径规则是在“校验路径是否合法”。
2. Bash 规则是在“检验危险命令”。
3. `ask_user()` 是 tool call 过程中的一个环节；当前代码会同步阻塞，等待用户输入后再继续。
4. 返回 `Permission denied.` 可以理解成这次 tool call 没有成功执行。

## 四、已理解正确的部分

- `ask_user()` 的确位于一次工具请求的本地处理流程中。
- 当前 CLI 使用 `input()`，会阻塞当前 Python 线程和 Agent Loop。
- 用户选择 `allow` 后才会执行 Handler；选择 `deny` 时不会产生该工具的副作用。
- 即使工具没有执行，也必须返回与 `tool_use_id` 配对的 `tool_result`，让模型知道处理结果。
- `tool_use_id` 只负责协议配对，不是 session、用户或 tenant 的授权凭证。

## 五、需要校准的边界

### 5.1 路径规则是权限策略匹配，不是一般参数校验

```python
not (WORKDIR / args.get("path", "")).resolve().is_relative_to(WORKDIR)
```

这段表达式在路径位于工作区外时返回 `True`，含义是“命中需要审批的规则”。它不负责检查字段类型、必填项等 Schema 合法性。

### 5.2 Bash 关键词只是教学示意

```python
any(kw in command for kw in ["rm ", "> /etc/", "chmod 777"])
```

它只做字符串包含判断，用于触发 `ask`，不是可靠的危险命令识别器。命令变体、Shell 展开、间接脚本等都可能绕过字符串匹配。

### 5.3 `ask_user()` 不属于 `tool_use` block 内部

可以说：

> `ask_user()` 是 tool call 执行管线中的人工审批环节。

但不能说它是模型返回的 `tool_use` 协议块中的字段。模型已经生成 `tool_use` 后，本地 Harness 才进入权限判断并等待用户。

### 5.4 权限拒绝与执行异常不同

```text
权限拒绝：权限检查失败 → Handler 没有运行 → operation not executed
执行异常：权限检查通过 → Handler 已经运行 → execution error
```

二者都应通过 `tool_result` 告诉模型，但错误分类和恢复策略不同：权限拒绝不应盲目重试；执行异常可以根据错误类型决定修正参数、有限重试或换方案。

当前教学代码返回 `Permission denied.`，但没有设置 `is_error: true`。生产实现更适合返回明确、结构化的状态，例如 `permission_denied`、`approval_required` 或 `blocked_by_policy`。

## 六、修正后的伪代码

```text
收到 tool_use

先做结构和业务校验

permission = evaluate_policy(current_user, tenant, tool_name, tool_input)

if permission == DENY:
    不调用 Handler
    返回 tool_result(permission_denied)

if permission == ASK:
    暂停当前工具请求
    等待有权审批的人确认
    if rejected:
        不调用 Handler
        返回 tool_result(permission_denied)

执行获准后的防护检查
调用 Handler
返回 tool_result(success 或 execution_error)
```

## 七、当前代码中的真实工程边界

当前路径权限规则表示“写工作区外需要审批”，但 `run_write()` 和 `run_edit()` 随后仍会调用 `safe_path()`，而 `safe_path()` 会无条件拒绝工作区外路径。

因此当前实现中：

```text
工作区外路径 → 用户即使 allow → safe_path 仍拒绝 → 实际无法写入
```

这说明“审批”和“执行防护”是两个独立层次。审批通过不必、也不应该自动关闭底层安全边界。不过教学代码的提示语容易让人误以为审批后可以越出工作区，后续实验时需要注意这一点。

## 八、稍微扩展到生产环境

### 8.1 审批不能只保存一个布尔值

一次审批至少应绑定：

- 当前用户与租户；
- session、run 和具体工具；
- 工具参数摘要或哈希；
- 审批人、审批时间和过期时间；
- 最终决定及审计记录。

否则，旧审批可能被错误复用到另一个用户、另一组参数或另一次运行。

### 8.2 Web 服务通常不能一直阻塞线程

CLI Demo 可以通过 `input()` 同步等待。生产系统更常把任务状态改成 `WAITING_APPROVAL`，持久化当前状态并释放线程；用户之后在 UI 中审批，再由系统恢复执行。

### 8.3 权限判断后仍要保留执行防护

`allow` 只说明“这个身份在当前上下文中获准尝试执行”，不表示工具一定成功，也不表示可以移除：

- 参数与业务校验；
- `safe_path` 或沙箱；
- 超时、配额和资源限制；
- 幂等、备份与回滚；
- 日志和审计。

## 九、待验收问题

1. 为什么模型生成 `tool_use` 不等于操作已经获得授权？
2. `ask_user()` 是 `tool_use` 协议内容，还是 Harness 的本地控制步骤？
3. 为什么用户允许写工作区外后，当前代码仍然不能完成写入？
4. 权限拒绝和 Handler 执行异常在执行位置与恢复策略上有什么不同？
5. 为什么生产审批必须绑定用户、工具参数和有效期？

## 十、本章记忆句

```text
模型提出动作，Harness 决定是否获准，Handler 只执行获准动作；
权限通过以后，执行防护仍然有效。
```

## 十一、问答验收记录（2026-08-25）

### 11.1 总体评价

- 结果：D1 核心理解通过。
- 概念理解约 85 分：已经理解权限位于 Handler 前、`ask_user()` 会阻塞、拒绝也要回传结果，以及四层安全边界。
- 代码路径准确度约 65～70 分：`pwd`、`sudo`、工作区外写入以及 deny 结果来源存在判断错误。
- 综合评价约 75 分。这里评的是能否准确预测当前代码行为，不是否定对本章主线的理解。
- 掌握较好：四层边界、`ask_user()` 的阻塞作用、拒绝后仍需回传 `tool_result`、相同危险调用不应自动重试。
- 需要巩固：检查函数被调用不等于规则命中；硬拒绝和询问规则的优先级；`allow` 后仍会执行 `safe_path`；权限拒绝与执行异常的错误分类。

#### ❌ 本轮明确的理解错误

> 下面是需要复习时优先检查的错误，不是可选的生产扩展。

1. **错误：`pwd` 经过危险检查，所以需要 `ask_user()`。**
   - 修正：经过检查不代表规则命中；`pwd` 未命中任何规则，直接执行。
2. **错误：`sudo ls` 与 `rm temp.log` 都属于 `ask`。**
   - 修正：`sudo` 命中硬拒绝，直接 `deny`；只有 `rm temp.log` 命中询问规则。
3. **错误：工作区外写入在用户 `allow` 后可以正常写入。**
   - 修正：`allow` 只通过权限层，随后仍被 Handler 内的 `safe_path()` 拒绝。
4. **错误：工作区外写入的两个机制是“路径判断”和“工具返回值”。**
   - 修正：两个机制是权限策略 `check_rules()` 与执行防护 `safe_path()`；返回值只是结果表达。
5. **错误：`deny` 后由工具函数利用审批结果并返回失败。**
   - 修正：`deny` 时 Handler 根本不执行，失败 `tool_result` 由 Harness 构造。
6. **错误倾向：用户主动拒绝，所以不能算错误。**
   - 修正：它不是 Handler 执行异常，但这次工具请求仍是未执行的失败结果，应分类为 `permission_denied`。

第 4 题的四层分类全部正确，没有理解错误。

### 11.2 问题一：`pwd` 的执行路径

**我的回答摘要**：

> 经过命令危险关键词匹配，涉及 `chmod`、`rm` 等需要 `ask_user()`，用户确认后才调用 `run_bash()`。

**正确部分**：

- 知道 Bash 会先经过权限检查，再决定是否调用 `run_bash()`。
- 知道只有获准后才应进入真实 Handler。

**❌ 我的理解错误**：

检查函数会运行，但 `pwd` 不包含任何拒绝或询问关键词，因此规则不会命中，也不会调用 `ask_user()`。

**修正后的答案**：

```text
check_permission(block)
→ check_deny_list("pwd")：未命中
→ check_rules("bash", {"command": "pwd"})：未命中
→ check_permission 返回 True
→ 调用 run_bash("pwd")
```

### 11.3 问题二：三类 Bash 命令

**我的回答摘要**：

> `sudo` 和 `rm` 都碰到危险关键词，需要 ask；`ls -la` 直接 allow。

**正确部分**：

- `rm temp.log` 会命中 Bash 询问规则，需要用户审批。
- `ls -la` 不命中规则，直接执行。

**❌ 我的理解错误**：

`sudo` 位于 `DENY_LIST`，硬拒绝优先于询问规则，所以不会进入 `ask_user()`，用户也没有机会覆盖这个决定。

**修正后的答案**：

| 命令 | 决策 | 是否询问 | Handler |
|---|---|---|---|
| `sudo ls` | `deny` | 否 | 不执行 |
| `rm temp.log` | `ask` | 是 | 用户允许后才执行 |
| `ls -la` | `allow` | 否 | 直接执行 |

### 11.4 问题三：工作区外写入

**我的回答摘要**：

> 访问工作区外的文件需要用户确认；allow 后需要等待 `write_file` 的正确返回；两个机制是相对工作区的位置判断和工具返回值。

**正确部分**：

- 正确识别出 `../outside.txt` 解析后位于 `WORKDIR` 外，因此会触发审批。
- 知道不能仅凭用户选择 `allow` 就宣称副作用已经成功。

**❌ 我的理解错误**：

这里先后参与的两个机制不是“路径判断和工具返回值”，而是：

1. 权限策略：`check_rules()` 判断是否需要询问；
2. 执行防护：Handler 内的 `safe_path()` 强制限制文件系统边界。

当前代码中，即使用户选择 `allow`，`run_write()` 仍会调用 `safe_path()`。它会拒绝工作区外路径，所以文件不会写入。

**修正后的答案**：

```text
write_file("../outside.txt", "hello")
→ check_rules 命中工作区外规则
→ ask_user
→ 用户 allow
→ 调用 run_write
→ safe_path 拒绝越出工作区
→ run_write 返回 Error 文本
→ 实际没有写入文件
```

当前 `run_write()` 把异常转成字符串，而外层 `tool_result` 没有设置 `is_error: true`，这是教学实现的错误语义简化。

### 11.5 问题四：四层边界

**我的回答**：

| 场景 | 我的分类 | 评价 |
|---|---|---|
| `path` 应为字符串却传入整数 | Schema 校验 | 正确 |
| 普通用户修改生产配置需审批 | 权限判断 | 正确 |
| `safe_path` 阻止路径逃逸 | 获准后的执行保护 | 正确 |
| 已关闭订单不能修改 | 业务逻辑校验 | 正确 |

这题完全正确。

### 11.6 问题五：`ask_user()` 的协议与执行边界

**我的回答摘要**：

> 阻塞的是工具能不能执行到最终业务代码；`deny` 或 `allow` 不直接进入 message；拒绝后返回一个代表工具执行失败的 ID block。

**正确部分**：

- `ask_user()` 确实阻断了进入业务 Handler 的控制流。
- `allow` 时，通常不需要把单独的字符串 `allow` 发给模型，而是继续执行 Handler 并返回真实结果。
- `deny` 时需要给模型一个未执行结果。

**❌ 我的理解错误**：

- `input()` 直接阻塞的是当前 Python 线程和 Agent Loop；此时上一轮模型 API 调用已经结束，模型没有继续运行。
- `ask_user()` 是 Harness 的本地控制步骤，不是模型生成的 `tool_use` block 内部字段。
- `deny` 后 Handler 不会运行，`Permission denied.` 是 Harness 构造的，而不是工具函数返回的。
- 返回的是 `tool_result` content block，其中包含 `tool_use_id`；不能简称成“tool id block”。

**修正后的答案**：

```text
模型先返回 tool_use
→ 本地 Harness 进入 check_permission
→ ask_user 使用 input() 阻塞 Agent Loop
→ allow：调用 Handler，把 Handler 输出写入 tool_result
→ deny：不调用 Handler，由 Harness 构造 Permission denied 的 tool_result
```

### 11.7 问题六：权限拒绝的结果语义

**我的回答摘要**：

> 拒绝也是一个结果，需要正常返回 LLM；它是用户主动选择，不能算执行错误；模型不应重试刚才的工具。

**正确部分**：

- 即使未执行，也必须返回结果，闭合 `tool_use → tool_result` 协议。
- 模型不应使用相同参数盲目重试一个刚被用户拒绝的动作。
- 用户拒绝不是 Handler 抛出的执行异常。

**❌ 我的理解错误**：

“不是执行异常”不等于“这次工具请求是成功的”。对这次工具尝试而言，它属于未执行的失败结果，错误分类是 `permission_denied`。在本课程的生产化设计中，建议设置 `is_error: true`，同时用结构化错误码说明它不是系统异常。

`tool_result.tool_use_id` 必须等于对应的 `tool_use.id`。这个 ID 只做协议配对，不代表用户、会话或租户授权。

**修正后的答案**：

```text
权限拒绝
→ Handler 没有执行
→ 返回 tool_result(
     tool_use_id = 原 tool_use.id,
     is_error = true,
     error_code = permission_denied
   )
→ 模型应解释拒绝、请求新的明确授权或选择低风险替代方案
→ 不得偷偷用相同参数重复调用
```

### 11.8 下一步最小实验

运行当前 CLI，分别验证：

1. `pwd`：直接允许；
2. `rm temp.log`：询问后允许或拒绝；
3. `sudo ls`：硬拒绝且不询问；
4. 工作区外 `write_file`：询问允许后仍被 `safe_path` 拒绝。

## 十二、本章结业状态

### 12.1 已达到的学习目标

- [x] 能解释为什么模型生成 `tool_use` 不等于操作获得授权；
- [x] 能说明 deny list、上下文规则和人工审批的执行顺序；
- [x] 能解释 `ask_user()` 在工具执行管线中的位置；
- [x] 能区分 Schema 校验、业务规则、权限策略和执行防护；
- [x] 能写出 `allow / ask / deny` 的核心伪代码；
- [x] 能映射到真实代码中的 `check_permission()`、`check_rules()`、`ask_user()` 和 `safe_path()`；
- [x] 能说明拒绝后为什么仍需返回 `tool_result`；
- [x] 已明确记录本轮理解错误及修正答案。

### 12.2 不阻塞结业的后续巩固

- [ ] 实际运行四条权限路径并对照预测；
- [ ] 将简单字符串匹配替换成更可靠的策略或沙箱实验；
- [ ] 在真实前后端 Agent 中验证 `WAITING_FOR_USER` 的断线恢复设计。

### 12.3 最终结论

第三章核心目标已经完成，可以进入 `s04 Hooks`。未完成项属于运行验证或生产级扩展，不影响本章 D1 结业。

## 十三、工程化补充：业务 Tool 的统一执行 Pipeline

### 13.1 最终结论

业务 Agent 中必备的不是“每个 Tool 函数内部复制一整套流程”，而是：

> 每一次 Tool 调用都必须经过统一、不可绕过的执行 Pipeline。

典型流程是：

```text
tool_use
→ Tool 查找与注册校验
→ Schema / 参数校验
→ 业务规则校验
→ 身份、租户与权限策略判断
→ 必要时 ask_user / approval
→ 获准后的执行防护
→ 调用真实业务 Handler
→ 标准化 tool_result
→ 日志、Trace 与审计
```

不是所有 Tool 都必须弹出用户确认，但每个 Tool 都应经过 Pipeline，并明确得到 `allow`、`ask` 或 `deny` 等决策。

### 13.2 公共 Pipeline 与 Tool Handler 的职责边界

公共能力适合放在统一的 Tool Executor 或中间件中：

- Tool 是否存在；
- Schema 和通用参数校验；
- 当前用户、session、run 与 tenant 绑定；
- 权限策略和审批；
- 超时、取消、重试上限和配额；
- 统一异常分类与 `tool_result` 包装；
- 日志、Trace 和审计。

每个 Tool 只提供自身特有能力：

- Tool Schema；
- Tool 特有的业务校验；
- 风险等级和权限元数据；
- Tool 特有的执行防护；
- 最终业务 Handler。

可以抽象成：

```text
ToolSpec
├─ schema
├─ business_validator
├─ permission_policy / risk_level
├─ execution_guard
└─ handler

ToolExecutor
└─ 按统一顺序编排并调用 ToolSpec
```

### 13.3 为什么不能让每个 Handler 自己实现全部流程

如果 `create_order()`、`send_email()`、`delete_record()` 等 Handler 各自复制权限、审批和错误包装逻辑，容易出现：

- 某个新 Tool 忘记鉴权；
- 不同 Tool 对同一种错误返回不同语义；
- 审批逻辑和业务代码强耦合；
- 重试、审计或超时策略不一致；
- 安全修复需要修改所有 Tool；
- 某条调用路径绕过公共检查，直接调用 Handler。

因此真实业务 Handler 应尽量专注于已经校验、已经授权后的业务执行，同时保留必要的底层防御。例如 `safe_path()` 可以继续留在文件 Handler 附近，形成 Defense in Depth（纵深防御）。

### 13.4 本章代码对应关系

```text
公共权限 Pipeline：
agent_loop → check_permission → check_deny_list / check_rules → ask_user

Tool 特有执行防护：
run_write / run_edit → safe_path

真实业务执行：
file_path.write_text / subprocess.run

协议结果包装：
agent_loop → tool_result
```

### 13.5 工程记忆句

```text
每个 Tool 调用都经过统一 Pipeline；
公共能力放 Executor；
Tool 特有规则放 ToolSpec；
Handler 专注真实业务执行。
```
