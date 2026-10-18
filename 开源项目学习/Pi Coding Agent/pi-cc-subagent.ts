/**
 * subagent.ts — Claude Code 风格的 subagent extension for pi
 *
 * 复刻 Claude Code 的 Agent tool 体系：
 *   - `agent` 工具：LLM 可调用，派生自治子 agent（子进程 `pi --mode json`）
 *   - 内置 agent 类型：general-purpose / explore / plan（对应 Claude Code 同名 agent）
 *   - 自定义 agent：~/.pi/agent/agents/*.md、.pi/agents/*.md，
 *     并兼容 Claude Code 的 ~/.claude/agents/*.md 与 .claude/agents/*.md
 *   - 触发方式：LLM 依据描述自动委派 / 用户点名 / 并行多发 / 后台运行 + 完成通知
 *   - `agent_output` 工具：轮询后台 agent
 *   - resume：子 agent 会话落盘，可凭 agentId 继续对话（对应 Claude Code 的 SendMessage）
 *   - `/agents` 命令：查看可用 agent 类型
 *
 * 安装：复制/软链到 ~/.pi/agent/extensions/（全局）或 .pi/extensions/（项目），
 * 或 `pi -e ./subagent.ts` 临时加载。
 */

import {
  type ExtensionAPI,
  type ExtensionContext,
  truncateHead,
  DEFAULT_MAX_BYTES,
  DEFAULT_MAX_LINES,
} from "@earendil-works/pi-coding-agent";
import { Text } from "@earendil-works/pi-tui";
import { Type } from "typebox";
import { execFileSync, spawn } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { basename, join } from "node:path";

// ---------------------------------------------------------------------------
// Agent 定义与发现
// ---------------------------------------------------------------------------

interface AgentDef {
  name: string;
  description: string;
  /** pi 内置工具名列表；undefined 表示默认工具集 */
  tools?: string[];
  /** 模型覆盖，如 "anthropic/claude-haiku-4-5"；undefined 继承父会话模型 */
  model?: string;
  /** 追加到系统提示词的角色设定（markdown 正文） */
  systemPrompt?: string;
  source: string;
}

const ALL_TOOLS = ["read", "bash", "edit", "write", "grep", "find", "ls"];
const READONLY_TOOLS = ["read", "grep", "find", "ls", "bash"];

const BUILTIN_AGENTS: AgentDef[] = [
  {
    name: "general-purpose",
    description:
      "General-purpose agent for researching complex questions, searching for code, and executing multi-step tasks. Has full tool access (read, bash, edit, write, grep, find, ls).",
    tools: ALL_TOOLS,
    source: "builtin",
    systemPrompt: "",
  },
  {
    name: "explore",
    description:
      "Read-only search agent for broad fan-out codebase exploration — locating files, symbols, usages, and answering \"where/how is X done\" questions when only the conclusion is needed, not the file dumps. It locates code; it doesn't review or audit it. Specify search breadth in the prompt (e.g. \"medium\" or \"very thorough\").",
    tools: READONLY_TOOLS,
    source: "builtin",
    systemPrompt: [
      "You are an exploration agent: a fast, READ-ONLY search agent for codebase and filesystem questions.",
      "Find the relevant files, symbols, and facts. Report code locations as `path:line`.",
      "Read excerpts rather than whole files when possible; prefer grep/find over reading everything.",
      "You MUST NOT modify anything: no file writes, no state-changing shell commands (only read-only commands like ls, cat, git log, git show, rg).",
      "Answer with the conclusion plus minimal supporting evidence.",
    ].join("\n"),
  },
  {
    name: "plan",
    description:
      "Software architect agent for designing implementation plans. Use when you need to plan the implementation strategy for a task. Returns step-by-step plans, identifies critical files, and considers architectural trade-offs. Read-only.",
    tools: READONLY_TOOLS,
    source: "builtin",
    systemPrompt: [
      "You are a software architect agent. Investigate the codebase (READ-ONLY: no file writes, no state-changing commands) and design an implementation plan for the given task.",
      "Your plan must include: step-by-step changes, critical files and functions as `path:line`, architectural trade-offs considered, risks, and a verification/testing strategy.",
      "Do NOT implement anything. The plan is your only deliverable.",
    ].join("\n"),
  },
];

/** 极简 frontmatter 解析（key: value 行，够用于 agent 定义文件） */
function parseFrontmatter(raw: string): { meta: Record<string, string>; body: string } {
  const meta: Record<string, string> = {};
  if (!raw.startsWith("---")) return { meta, body: raw };
  const end = raw.indexOf("\n---", 3);
  if (end === -1) return { meta, body: raw };
  const header = raw.slice(3, end);
  for (const line of header.split("\n")) {
    const m = line.match(/^([A-Za-z][\w-]*)\s*:\s*(.*)$/);
    if (m) meta[m[1].toLowerCase()] = m[2].trim().replace(/^["']|["']$/g, "");
  }
  return { meta, body: raw.slice(end + 4).replace(/^\n+/, "") };
}

function loadAgentFile(path: string, source: string): AgentDef | undefined {
  try {
    const { meta, body } = parseFrontmatter(readFileSync(path, "utf8"));
    const name = meta["name"] || basename(path).replace(/\.md$/, "");
    if (!meta["description"]) return undefined; // 与 skills 一致：无 description 不加载
    const tools = meta["tools"]
      ? meta["tools"].split(/[,\s]+/).map((t) => t.trim()).filter(Boolean)
      : undefined;
    return {
      name,
      description: meta["description"],
      tools,
      model: meta["model"] && meta["model"] !== "inherit" ? meta["model"] : undefined,
      systemPrompt: body.trim(),
      source,
    };
  } catch {
    return undefined;
  }
}

function loadAgentDir(dir: string, source: string, into: Map<string, AgentDef>) {
  if (!existsSync(dir)) return;
  let files: string[] = [];
  try {
    files = readdirSync(dir).filter((f) => f.endsWith(".md"));
  } catch {
    return;
  }
  for (const f of files) {
    const def = loadAgentFile(join(dir, f), source);
    if (def) into.set(def.name, def); // 后加载的覆盖先加载的
  }
}

/** 发现顺序（后者覆盖前者）：builtin < ~/.claude < ~/.pi/agent < 项目 .claude < 项目 .pi */
function discoverAgents(cwd: string): Map<string, AgentDef> {
  const agents = new Map<string, AgentDef>();
  for (const def of BUILTIN_AGENTS) agents.set(def.name, def);
  loadAgentDir(join(homedir(), ".claude", "agents"), "user (claude)", agents);
  loadAgentDir(join(homedir(), ".pi", "agent", "agents"), "user", agents);
  loadAgentDir(join(cwd, ".claude", "agents"), "project (claude)", agents);
  loadAgentDir(join(cwd, ".pi", "agents"), "project", agents);
  return agents;
}

// ---------------------------------------------------------------------------
// 子 agent 运行（子进程 pi --mode json）
// ---------------------------------------------------------------------------

const SUBAGENT_PROTOCOL = [
  "",
  "## Subagent protocol",
  "You are a subagent spawned by a parent agent. Work fully autonomously — you cannot ask the user questions.",
  "Your FINAL message is returned verbatim to the parent agent as a tool result; it is not shown to the user.",
  "Return the concrete deliverable (findings, raw data, file paths with line numbers, conclusions) with no conversational padding.",
].join("\n");

interface WorktreeInfo {
  repo: string;
  dir: string;
  branch: string;
  baseSha: string;
  kept?: boolean;
  commits?: string;
  diffStat?: string;
  statusShort?: string;
  error?: string;
}

interface TaskRecord {
  id: string;
  type: string;
  description: string;
  status: "running" | "done" | "error" | "cancelled";
  agentId?: string; // 子会话 uuid，可用于 resume
  activity: string[]; // 最近的工具调用行
  turns: number;
  toolCalls: number;
  cost: number;
  startedAt: number;
  finalText: string;
  error?: string;
  worktree?: WorktreeInfo;
  runCwd?: string; // 实际运行目录；resume 必须回到同一目录，否则 pi 会弹跨项目 fork 提示
  kill?: () => void;
  exited?: Promise<void>;
  onDone?: (t: TaskRecord) => void;
}

function git(args: string[], cwd: string): string {
  return execFileSync("git", args, { cwd, encoding: "utf8" });
}

/** 为子 agent 建立独立 git worktree（基于当前 HEAD 的干净签出） */
function createWorktree(repoCwd: string, type: string, taskId: string): WorktreeInfo {
  const repo = git(["rev-parse", "--show-toplevel"], repoCwd).trim();
  const baseSha = git(["rev-parse", "HEAD"], repoCwd).trim();
  const suffix = Math.random().toString(36).slice(2, 6);
  const branch = `agent/${type}-${taskId.replace(/^agent-/, "")}-${suffix}`;
  const dir = join(tmpdir(), `pi-subagent-${branch.replace(/\//g, "-")}`);
  git(["worktree", "add", "-b", branch, dir, "HEAD"], repo);
  return { repo, dir, branch, baseSha };
}

/** 任务结束后：无改动 → 删除 worktree 和分支；有改动 → 保留并收集摘要 */
function finalizeWorktree(task: TaskRecord): void {
  const w = task.worktree;
  if (!w || w.kept !== undefined) return;
  try {
    const statusShort = git(["status", "--porcelain"], w.dir).trim();
    const headNow = git(["rev-parse", "HEAD"], w.dir).trim();
    const committed = headNow !== w.baseSha;
    if (!statusShort && !committed) {
      git(["worktree", "remove", "--force", w.dir], w.repo);
      git(["branch", "-D", w.branch], w.repo);
      w.kept = false;
      return;
    }
    w.kept = true;
    w.statusShort = statusShort || undefined;
    if (committed) w.commits = git(["log", "--oneline", `${w.baseSha}..HEAD`], w.dir).trim();
    w.diffStat = git(["diff", "--stat", w.baseSha], w.dir).trim() || undefined;
  } catch (err: any) {
    w.kept = true; // 保守起见：出错时不删
    w.error = String(err?.message ?? err);
  }
}

function formatToolLine(toolName: string, args: any): string {
  let detail = "";
  if (toolName === "bash") detail = String(args?.command ?? "");
  else if (toolName === "read" || toolName === "ls") detail = String(args?.path ?? "");
  else if (toolName === "grep") detail = String(args?.pattern ?? "");
  else if (toolName === "find") detail = String(args?.pattern ?? args?.path ?? "");
  else if (toolName === "edit" || toolName === "write") detail = String(args?.path ?? "");
  detail = detail.replace(/\s+/g, " ").trim();
  if (detail.length > 60) detail = detail.slice(0, 57) + "...";
  return detail ? `${toolName}: ${detail}` : toolName;
}

function buildSpawnArgs(def: AgentDef, opts: {
  prompt: string;
  model?: string;
  thinking?: string;
  resume?: string;
  description: string;
}): string[] {
  const args = ["--mode", "json", "--no-extensions"];
  if (opts.resume) {
    args.push("--session", opts.resume);
  } else {
    args.push("--name", `agent:${def.name}: ${opts.description}`.slice(0, 80));
  }
  if (def.tools?.length) args.push("--tools", def.tools.join(","));
  if (opts.model) args.push("--model", opts.model);
  if (opts.thinking) args.push("--thinking", opts.thinking);
  const persona = (def.systemPrompt ?? "").trim();
  args.push("--append-system-prompt", (persona ? persona + "\n" : "") + SUBAGENT_PROTOCOL);
  // 以 "-" 开头的 prompt 会被 pi CLI 当作选项、以 "@" 开头会被当作文件引用；前置空格保持其为普通消息
  args.push(/^[-@]/.test(opts.prompt) ? ` ${opts.prompt}` : opts.prompt);
  return args;
}

/** 优先复用当前 pi 的入口脚本，保证版本一致；否则回退到 PATH 里的 pi */
function piCommand(): { cmd: string; prefixArgs: string[] } {
  const entry = process.argv[1];
  if (entry && existsSync(entry)) return { cmd: process.execPath, prefixArgs: [entry] };
  return { cmd: "pi", prefixArgs: [] };
}

function runSubagent(
  task: TaskRecord,
  def: AgentDef,
  spawnArgs: string[],
  cwd: string,
  signal: AbortSignal | undefined,
  onProgress: (t: TaskRecord) => void,
): Promise<TaskRecord> {
  return new Promise((resolve) => {
    const { cmd, prefixArgs } = piCommand();
    // detached: 子进程自成进程组，kill 时能连同其派生的 bash 孙进程一起终止
    const proc = spawn(cmd, [...prefixArgs, ...spawnArgs], {
      cwd,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
      detached: process.platform !== "win32",
    });

    let stdoutBuf = "";
    let stderrTail = "";
    let rawTail = ""; // 非 JSON 的 stdout 行（如 "No session found matching ..."），用于诊断

    const finish = (status: TaskRecord["status"], error?: string) => {
      if (task.status !== "running") return;
      task.status = status;
      if (error) task.error = error;
      task.onDone?.(task);
      resolve(task);
    };

    const killTree = (sig: NodeJS.Signals) => {
      try {
        if (process.platform !== "win32" && proc.pid) process.kill(-proc.pid, sig);
        else proc.kill(sig);
      } catch {
        try {
          proc.kill(sig);
        } catch {}
      }
    };
    task.kill = () => {
      killTree("SIGTERM");
      setTimeout(() => killTree("SIGKILL"), 3000).unref?.();
    };
    task.exited = new Promise<void>((res) => proc.on("close", () => res()));
    // abort 时只发 kill，不立即结算；等 close 事件（子进程真正退出）后再 finalize worktree，
    // 避免与仍在写文件的子进程竞争
    const onAbort = () => task.kill?.();
    if (signal?.aborted) onAbort();
    else signal?.addEventListener("abort", onAbort, { once: true });

    const handleEvent = (ev: any) => {
      switch (ev.type) {
        case "session":
          task.agentId = ev.id;
          break;
        case "turn_start":
          task.turns++;
          break;
        case "tool_execution_start":
          task.toolCalls++;
          task.activity.push(formatToolLine(ev.toolName, ev.args));
          if (task.activity.length > 5) task.activity.shift();
          break;
        case "message_end": {
          const msg = ev.message;
          if (msg?.role === "assistant") {
            const text = (msg.content ?? [])
              .filter((b: any) => b?.type === "text")
              .map((b: any) => b.text)
              .join("");
            if (text.trim()) task.finalText = text;
            const c = msg.usage?.cost?.total;
            if (typeof c === "number") task.cost += c;
            if (msg.errorMessage) task.error = String(msg.errorMessage);
          }
          break;
        }
      }
      onProgress(task);
    };

    proc.stdout.on("data", (chunk: Buffer) => {
      stdoutBuf += chunk.toString("utf8");
      let idx: number;
      while ((idx = stdoutBuf.indexOf("\n")) !== -1) {
        const line = stdoutBuf.slice(0, idx).trim();
        stdoutBuf = stdoutBuf.slice(idx + 1);
        if (!line) continue;
        try {
          handleEvent(JSON.parse(line));
        } catch {
          rawTail = (rawTail + line + "\n").slice(-500);
        }
      }
    });
    proc.stderr.on("data", (chunk: Buffer) => {
      stderrTail = (stderrTail + chunk.toString("utf8")).slice(-2000);
    });

    proc.on("error", (err) => {
      finalizeWorktree(task);
      finish("error", `Failed to spawn pi: ${err.message}`);
    });
    proc.on("close", (code) => {
      signal?.removeEventListener("abort", onAbort);
      finalizeWorktree(task); // 子进程已退出，此时盘点/清理 worktree 无竞争；也保证 onDone 通知时状态已定
      if (signal?.aborted) return finish("cancelled", "Aborted by parent");
      if (!task.agentId) {
        // 连 session 头事件都没有：pi 根本没跑起来（如 "No session found matching ..." 或跨项目 fork 提示被拒）
        const detail = [rawTail.trim(), stderrTail.trim()].filter(Boolean).join("\n");
        return finish("error", `pi produced no session events (exit code ${code})${detail ? `:\n${detail}` : ""}`);
      }
      if (code !== 0) {
        let msg = `pi exited with code ${code}${stderrTail ? `: ${stderrTail.trim()}` : ""}`;
        if (task.finalText) msg += `\nLast assistant text before failure:\n${task.finalText.slice(0, 2000)}`;
        return finish("error", msg);
      }
      if (task.error && !task.finalText) return finish("error", task.error);
      finish("done");
    });
  });
}

// ---------------------------------------------------------------------------
// Extension 入口
// ---------------------------------------------------------------------------

export default function (pi: ExtensionAPI) {
  const agents = discoverAgents(process.cwd());
  const tasks = new Map<string, TaskRecord>();
  const byAgentId = new Map<string, TaskRecord>(); // 子会话 uuid → 任务记录，供 resume 恢复类型与 worktree
  let bgCounter = 0;

  const agentListText = () =>
    [...agents.values()]
      .map((a) => `- ${a.name}: ${a.description}`)
      .join("\n");

  const updateStatus = (ctx: ExtensionContext) => {
    const running = [...tasks.values()].filter((t) => t.status === "running").length;
    ctx.ui.setStatus("subagent", running > 0 ? `⚒ ${running} subagent${running > 1 ? "s" : ""} running` : undefined);
  };

  const taskDetails = (t: TaskRecord, elapsedMs: number) => ({
    id: t.id,
    type: t.type,
    description: t.description,
    status: t.status,
    agentId: t.agentId,
    turns: t.turns,
    toolCalls: t.toolCalls,
    cost: t.cost,
    activity: [...t.activity],
    finalText: t.finalText,
    error: t.error,
    worktree: t.worktree ? { ...t.worktree } : undefined,
    elapsedMs,
  });

  function startTask(
    def: AgentDef,
    params: {
      prompt: string;
      description: string;
      model?: string;
      resume?: string;
      isolation?: string;
      priorWorktree?: WorktreeInfo;
      priorRunCwd?: string;
    },
    ctx: ExtensionContext,
    signal: AbortSignal | undefined,
    onProgress: (t: TaskRecord) => void,
  ): { task: TaskRecord; promise: Promise<TaskRecord> } {
    const model =
      params.model ??
      def.model ??
      (ctx.model ? `${(ctx.model as any).provider}/${(ctx.model as any).id}` : undefined);
    const thinking = pi.getThinkingLevel?.();
    const task: TaskRecord = {
      id: `agent-${++bgCounter}`,
      type: def.name,
      description: params.description,
      status: "running",
      activity: [],
      turns: 0,
      toolCalls: 0,
      cost: 0,
      startedAt: Date.now(),
      finalText: "",
    };
    tasks.set(task.id, task);
    updateStatus(ctx);

    let runCwd = ctx.cwd;
    if (params.resume && params.priorWorktree?.kept && existsSync(params.priorWorktree.dir)) {
      // resume 一个 worktree 隔离的任务：回到原 worktree 续跑；kept 置回 undefined，结束后重新盘点改动
      task.worktree = {
        repo: params.priorWorktree.repo,
        dir: params.priorWorktree.dir,
        branch: params.priorWorktree.branch,
        baseSha: params.priorWorktree.baseSha,
      };
      runCwd = task.worktree.dir;
    } else if (params.resume && params.priorRunCwd && existsSync(params.priorRunCwd)) {
      // resume 回到原任务的运行目录，避免 pi 的跨项目 fork 提示（headless 下会静默失败）
      runCwd = params.priorRunCwd;
    } else if (params.isolation === "worktree" && !params.resume) {
      try {
        task.worktree = createWorktree(ctx.cwd, def.name, task.id);
        runCwd = task.worktree.dir;
      } catch (err: any) {
        task.status = "error";
        task.error = String(err?.message ?? err);
        updateStatus(ctx);
        throw new Error(`Failed to create git worktree (is this a git repo with at least one commit?): ${task.error}`);
      }
    }
    task.runCwd = runCwd;

    const spawnArgs = buildSpawnArgs(def, {
      prompt: params.prompt,
      model,
      thinking: thinking && thinking !== "off" ? thinking : undefined,
      resume: params.resume,
      description: params.description,
    });
    const wrappedProgress = (t: TaskRecord) => {
      if (t.agentId) byAgentId.set(t.agentId, t);
      onProgress(t);
    };
    const promise = runSubagent(task, def, spawnArgs, runCwd, signal, wrappedProgress).finally(() =>
      updateStatus(ctx),
    );
    return { task, promise };
  }

  function worktreeReport(t: TaskRecord): string {
    const w = t.worktree;
    if (!w) return "";
    if (w.kept) {
      let text = `\n\n---\nWorktree (isolated run): changes kept at ${w.dir}\nBranch: ${w.branch} (base ${w.baseSha.slice(0, 7)})`;
      if (w.commits) text += `\nCommits:\n${w.commits}`;
      if (w.diffStat) text += `\nDiff stat:\n${w.diffStat}`;
      if (w.statusShort) text += `\nUncommitted/untracked:\n${w.statusShort}`;
      if (w.error) text += `\nWorktree inspection error: ${w.error}`;
      text += `\nReview: git diff ${w.baseSha.slice(0, 7)}..${w.branch} · Merge: git merge ${w.branch} · Discard: git worktree remove --force ${w.dir} && git branch -D ${w.branch}`;
      return text;
    }
    if (w.kept === false) return `\n\n---\nWorktree (isolated run): agent made no changes — worktree removed.`;
    return `\n\n---\nWorktree (isolated run): ${w.dir} on branch ${w.branch} (not finalized yet).`;
  }

  function resumeFooter(t: TaskRecord): string {
    if (!t.agentId) return "";
    return `\n\n---\nagentId: ${t.agentId} (pass resume: "${t.agentId}" to continue this agent with its context intact; its agent type and worktree are restored automatically)`;
  }

  function taskResultText(t: TaskRecord): string {
    if (t.status === "error") {
      throw new Error(`${t.error ?? "Subagent failed"}${worktreeReport(t)}${resumeFooter(t)}`);
    }
    if (t.status === "cancelled") {
      return `[Subagent cancelled]${worktreeReport(t)}${resumeFooter(t)}`;
    }
    const truncation = truncateHead(t.finalText || "[Subagent returned no text]", {
      maxLines: DEFAULT_MAX_LINES,
      maxBytes: DEFAULT_MAX_BYTES,
    });
    let text = truncation.content;
    if (truncation.truncated) text += "\n\n[Subagent output truncated]";
    return text + worktreeReport(t) + resumeFooter(t);
  }

  // ------------------------------------------------------------------
  // agent 工具（对应 Claude Code 的 Agent/Task tool）
  // ------------------------------------------------------------------
  pi.registerTool({
    name: "agent",
    label: "Agent",
    description: [
      "Launch a new agent to handle complex, multi-step tasks autonomously.",
      "",
      "Available agent types (subagent_type):",
      agentListText(),
      "",
      "When to use:",
      "Reach for this when the task matches an available agent type, when you have independent work to run in parallel, or when answering would mean reading across several files — delegate it and you keep the conclusion, not the file dumps. For a single-fact lookup where you already know the file, symbol, or value, search directly. Once you've delegated a search, don't also run it yourself — wait for the result.",
      "",
      "Usage notes:",
      "- IMPORTANT: For any non-trivial exploration, research, or review task, DECOMPOSE it into 2-5 independent slices and launch one agent per slice IN PARALLEL (multiple agent calls in a single message). Examples: one agent per subsystem/directory, one per review dimension (bugs/security/performance), one per research question. Only use a single agent when the task is genuinely indivisible.",
      "- The agent's final message is returned as the tool result; it is NOT shown to the user — relay what matters in your response.",
      "- Each invocation starts a fresh agent with no shared context. Include full context in the prompt and specify exactly what the agent should return.",
      "- Pass resume with an agentId from a previous result to continue that agent with its context intact; its original agent type (tools/persona) and worktree are restored automatically.",
      '- isolation: "worktree" gives the agent its own git worktree (a clean checkout of HEAD). It is auto-removed if the agent made no changes; otherwise it is kept and the branch/diff info is included in the result for you to review and merge. Use ONLY when multiple agents mutate files in parallel, or for risky changes that must not touch the working tree. Requires a git repo; the parent\'s uncommitted changes are NOT visible to the agent.',
      "- Set run_in_background: true for long tasks; you get a notification message when it completes, and can poll with agent_output.",
      "- Subagents cannot spawn further subagents and cannot ask the user questions.",
    ].join("\n"),
    promptSnippet: "Delegate multi-step tasks to autonomous subagents (explore, plan, general-purpose, custom types)",
    promptGuidelines: [
      "Use the agent tool to delegate complex searches or multi-step subtasks. When a task has independent slices (multiple subsystems, review dimensions, research questions), split it and issue multiple agent calls in ONE message so they run in parallel — do not run them one after another.",
      'Prefer agent with subagent_type "explore" for broad codebase searches where you only need conclusions, and "plan" for implementation planning.',
    ],
    parameters: Type.Object({
      description: Type.String({ description: "A short (3-5 word) description of the task" }),
      prompt: Type.String({ description: "The task for the agent to perform, with all necessary context" }),
      subagent_type: Type.Optional(
        Type.String({
          description: `The type of agent to use (default "general-purpose"). One of: ${[...agents.keys()].join(", ")}`,
        }),
      ),
      model: Type.Optional(
        Type.String({ description: 'Optional model override, e.g. "anthropic/claude-haiku-4-5". Defaults to the parent model.' }),
      ),
      resume: Type.Optional(
        Type.String({ description: "agentId of a previously finished agent to continue with its context intact" }),
      ),
      isolation: Type.Optional(
        Type.String({
          description: 'Set to "worktree" to run the agent in an isolated git worktree (auto-cleaned if unchanged)',
        }),
      ),
      run_in_background: Type.Optional(
        Type.Boolean({ description: "Run in the background and return immediately (default false)" }),
      ),
    }),
    async execute(_toolCallId, params, signal, onUpdate, ctx) {
      let typeName = params.subagent_type ?? "general-purpose";
      let priorTask: TaskRecord | undefined;
      if (params.resume) {
        priorTask = byAgentId.get(params.resume);
        // resume 时沿用原任务的 agent 类型，避免只读 agent 续跑时拿到写权限或换人设
        if (priorTask) typeName = priorTask.type;
        if (priorTask?.status === "running") {
          throw new Error(`Agent ${params.resume} is still running; wait for it to finish before resuming.`);
        }
        if (priorTask?.worktree && priorTask.worktree.kept === false) {
          throw new Error(
            `Cannot resume agent ${params.resume}: its isolated worktree was removed because the agent made no changes. Launch a fresh agent instead.`,
          );
        }
        if (priorTask?.runCwd && !existsSync(priorTask.runCwd)) {
          throw new Error(
            `Cannot resume agent ${params.resume}: its working directory ${priorTask.runCwd} no longer exists. Launch a fresh agent instead.`,
          );
        }
      }
      const def = agents.get(typeName);
      if (!def) {
        throw new Error(`Unknown subagent_type "${typeName}". Available: ${[...agents.keys()].join(", ")}`);
      }
      if (params.isolation && params.isolation !== "worktree") {
        throw new Error(`Invalid isolation "${params.isolation}". Only "worktree" is supported.`);
      }
      const runParams = { ...params, priorWorktree: priorTask?.worktree, priorRunCwd: priorTask?.runCwd };

      const onProgress = (t: TaskRecord) => {
        onUpdate?.({
          content: [{ type: "text", text: `${t.type}: turn ${t.turns}, ${t.toolCalls} tool calls` }],
          details: taskDetails(t, Date.now() - t.startedAt),
        });
      };

      if (params.run_in_background) {
        const { task, promise } = startTask(def, runParams, ctx, undefined, () => {});
        task.onDone = (t) => {
          const header =
            t.status === "done"
              ? `Background agent ${t.id} (${t.type}, "${t.description}") completed:`
              : `Background agent ${t.id} (${t.type}, "${t.description}") ${t.status}: ${t.error ?? ""}`;
          let body = "";
          try {
            body = t.status === "done" ? taskResultText(t) : "";
          } catch {
            body = "";
          }
          pi.sendMessage(
            { customType: "subagent-notification", content: `${header}\n\n${body}`.trim(), display: true },
            { deliverAs: "steer", triggerTurn: true },
          );
        };
        void promise;
        return {
          content: [
            {
              type: "text",
              text: `Launched background agent ${task.id} (${def.name}). You will be notified when it completes; poll with agent_output({ agent_id: "${task.id}" }) if needed.`,
            },
          ],
          details: taskDetails(task, 0),
        };
      }

      const { task, promise } = startTask(def, runParams, ctx, signal, onProgress);
      const done = await promise;
      return {
        content: [{ type: "text", text: taskResultText(done) }],
        details: taskDetails(done, Date.now() - done.startedAt),
      };
    },
    renderCall(args: any, theme) {
      const type = args?.subagent_type ?? "general-purpose";
      let s = theme.fg("toolTitle", theme.bold("agent")) + theme.fg("muted", `(${type})`);
      if (args?.run_in_background) s += theme.fg("warning", " [bg]");
      if (args?.isolation === "worktree") s += theme.fg("warning", " [worktree]");
      if (args?.resume) s += theme.fg("dim", ` resume:${String(args.resume).slice(0, 8)}`);
      if (args?.description) s += " " + theme.fg("dim", String(args.description));
      return new Text(s, 0, 0);
    },
    renderResult(result: any, { expanded, isPartial }, theme) {
      const d = result?.details;
      if (!d) {
        const raw = (result?.content ?? [])
          .filter((b: any) => b?.type === "text")
          .map((b: any) => b.text)
          .join("\n");
        return new Text(raw || "(no output)", 0, 0);
      }
      const secs = Math.round((d.elapsedMs ?? 0) / 1000);
      const stats = `${d.turns} turns · ${d.toolCalls} tools · ${secs}s${d.cost ? ` · $${d.cost.toFixed(4)}` : ""}`;
      if (isPartial || d.status === "running") {
        let s = theme.fg("warning", `⚒ ${d.type} working… `) + theme.fg("dim", stats);
        for (const line of d.activity ?? []) s += "\n  " + theme.fg("dim", line);
        return new Text(s, 0, 0);
      }
      if (d.status === "error") {
        return new Text(theme.fg("error", `✗ ${d.type} failed: ${d.error ?? "unknown error"}`), 0, 0);
      }
      if (d.status === "cancelled") {
        return new Text(theme.fg("warning", `⊘ ${d.type} cancelled · ${stats}`), 0, 0);
      }
      let s = theme.fg("success", `✓ ${d.type} done`) + " " + theme.fg("dim", stats);
      const finalText: string = d.finalText ?? "";
      const lines = finalText.split("\n");
      const shown = expanded ? lines : lines.slice(0, 8);
      for (const line of shown) s += "\n" + line;
      if (!expanded && lines.length > 8) s += "\n" + theme.fg("dim", `… ${lines.length - 8} more lines (expand to view)`);
      if (d.worktree) {
        s +=
          "\n" +
          (d.worktree.kept
            ? theme.fg("warning", `worktree kept: ${d.worktree.branch} @ ${d.worktree.dir}`)
            : theme.fg("dim", "worktree: no changes, removed"));
      }
      if (d.agentId) s += "\n" + theme.fg("dim", `agentId: ${d.agentId}`);
      return new Text(s, 0, 0);
    },
  });

  // ------------------------------------------------------------------
  // agent_output 工具（对应 Claude Code 的 TaskOutput）
  // ------------------------------------------------------------------
  pi.registerTool({
    name: "agent_output",
    label: "Agent Output",
    description:
      "Get the status and output of a background agent launched with the agent tool (run_in_background: true). Pass the agent_id returned at launch.",
    parameters: Type.Object({
      agent_id: Type.String({ description: 'Background agent id, e.g. "agent-1"' }),
    }),
    async execute(_toolCallId, params) {
      const t = tasks.get(params.agent_id);
      if (!t) {
        throw new Error(
          `No such agent "${params.agent_id}". Known: ${[...tasks.keys()].join(", ") || "(none)"}`,
        );
      }
      let text = `Agent ${t.id} (${t.type}, "${t.description}") status: ${t.status}\n`;
      text += `Progress: ${t.turns} turns, ${t.toolCalls} tool calls\n`;
      if (t.status === "running" && t.activity.length) {
        text += `Recent activity:\n${t.activity.map((a) => `  ${a}`).join("\n")}`;
      } else if (t.status === "done") {
        text += `\n${taskResultText(t)}`;
      } else if (t.error) {
        text += `Error: ${t.error}`;
      }
      return {
        content: [{ type: "text", text }],
        details: taskDetails(t, Date.now() - t.startedAt),
      };
    },
  });

  // ------------------------------------------------------------------
  // /agents 命令（对应 Claude Code 的 /agents）
  // ------------------------------------------------------------------
  pi.registerCommand("agents", {
    description: "List available subagent types",
    getArgumentCompletions: (prefix: string) => {
      const items = [...agents.keys()]
        .filter((n) => n.startsWith(prefix))
        .map((n) => ({ value: n, label: n }));
      return items.length > 0 ? items : null;
    },
    handler: async (args, ctx) => {
      if (!ctx.hasUI) return;
      const name = args?.trim();
      const show = (def: AgentDef) => {
        ctx.ui.notify(
          [
            `${def.name} [${def.source}]`,
            def.description,
            `tools: ${def.tools?.join(", ") ?? "(default)"}`,
            `model: ${def.model ?? "(inherit)"}`,
          ].join("\n"),
          "info",
        );
      };
      if (name && agents.has(name)) return show(agents.get(name)!);
      const labels = [...agents.values()].map(
        (a) => `${a.name} — ${a.description.slice(0, 70)}${a.description.length > 70 ? "…" : ""}`,
      );
      const choice = await ctx.ui.select("Subagent types:", labels);
      if (!choice) return;
      const def = agents.get(choice.split(" — ")[0]);
      if (def) show(def);
    },
  });

  // 后台完成通知的自定义渲染
  pi.registerMessageRenderer("subagent-notification", (message: any, _options, theme) => {
    const firstLine = String(message.content ?? "").split("\n")[0];
    return new Text(theme.fg("accent", "◈ ") + theme.fg("muted", firstLine), 0, 0);
  });

  // 会话结束：终止仍在运行的子进程，等它们退出后收尾 worktree（无改动即删除，不留残留）
  pi.on("session_shutdown", async () => {
    const running = [...tasks.values()].filter((t) => t.status === "running");
    for (const t of running) t.kill?.();
    if (running.length > 0) {
      await Promise.race([
        Promise.all(running.map((t) => t.exited ?? Promise.resolve())),
        new Promise((resolve) => setTimeout(resolve, 5000)),
      ]);
    }
    for (const t of tasks.values()) finalizeWorktree(t); // 幂等：已 finalize 的直接跳过
  });
}