// 以用户消息为边界组装展示组；模型消息和工具记录仍保持原样，只调整前端呈现。
// 纯函数也用于验证刷新重建、历史结果和流式续写能落到同一回复区。
export function projectConversation(view, jobs = {}) {
  const textOf = (message) => typeof message.content === "string" ? message.content
    : (message.content ?? []).filter((part) => part.type === "text").map((part) => part.text).join("");
  const live = view.docs["pi.live"] ?? {};
  const results = new Map();
  for (const entry of view.entries) for (const message of entry.model ?? []) {
    if (message.role !== "toolResult") continue;
    let job;
    try { job = JSON.parse(textOf(message)); } catch { /* 非视频工具结果不包含业务 JSON。 */ }
    results.set(message.toolCallId, { message, job });
  }
  const items = [];
  let userId = "history";
  let reply;
  const ensureReply = () => {
    if (!reply) { reply = { id: `reply-${userId}`, role: "assistant", parts: [] }; items.push(reply); }
    return reply;
  };
  const toolProgress = (call) => {
    const result = results.get(call.id);
    const slot = live.tools?.find((tool) => tool.callId === call.id);
    const job = jobs[result?.job?.id] ?? (slot?.taskId !== undefined ? jobs[`video-${slot.taskId}`] : undefined);
    let status = job?.status ?? (result ? result.message.isError ? "failed" : "completed" : "preparing");
    if (status === "awaiting_confirmation" && job.decision === "approved") status = "approved";
    if (status === "awaiting_confirmation" && job.decision === "rejected") status = "rejected";
    const labels = {
      preparing: "正在准备视频参数", awaiting_confirmation: "等待你确认视频参数", approved: "参数已确认，准备生成",
      generating: "正在模拟生成视频", completed: "视频任务已完成（Mock）", rejected: "已拒绝，本次未生成",
      cancelled: "视频任务已取消", failed: "视频任务未完成",
    };
    // 将同一工具调用关联的业务状态带到原来的对话位置，刷新后也能重建确认表单。
    return { id: `tool-${call.id}`, kind: "tool", status, text: labels[status] ?? status, job };
  };
  for (const entry of view.entries) (entry.model ?? []).forEach((message, index) => {
    if (message.role === "user") {
      userId = `${entry.id}-${index}`;
      items.push({ id: userId, role: "user", parts: [{ id: userId, kind: "text", text: textOf(message) }] });
      reply = undefined;
    } else if (message.role === "assistant" && message.stopReason !== "aborted") {
      const text = message.stopReason === "error" ? "这次回复未能完成，请稍后重试。" : textOf(message);
      if (text) ensureReply().parts.push({ id: `text-${entry.id}-${index}`, kind: "text", text });
      for (const call of Array.isArray(message.content) ? message.content : []) {
        if (call.type === "toolCall" && call.name === "generate_video") ensureReply().parts.push(toolProgress(call));
      }
    }
  });
  const partial = live.generation?.message;
  if (partial && textOf(partial)) ensureReply().parts.push({ id: "live-response", kind: "text", text: textOf(partial), streaming: true });
  else if (live.generation) ensureReply().parts.push({ id: "thinking", kind: "text", text: "···", thinking: true });
  return items;
}

function startPage() {
const byId = (id) => document.getElementById(id);
const input = byId("message");
const messageNodes = new Map();
let currentState;
let connected = false;
let sending = false;
let scrollOnUpdate = false;

function showError(text) { byId("error").textContent = text; byId("error").hidden = !text; }
function jumpToVideo() {
  const blocks = [...document.querySelectorAll(".inline-video-job")];
  const target = blocks.find((block) => block.dataset.status === "awaiting_confirmation") ?? blocks.at(-1);
  if (!target) { byId("activity").textContent = "还没有视频任务；确认参数会直接显示在对话中。"; return; }
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  const field = target.querySelector("textarea");
  if (field && !field.disabled && !field.closest("[hidden]")) field.focus({ preventScroll: true });
}
function updateActivity() {
  const pending = Object.values(currentState?.jobs ?? {}).some((job) => job.decision === "pending" && job.status === "awaiting_confirmation");
  const busy = Boolean(currentState?.view.docs["pi.live"]?.run);
  // 连接异常时允许点击并说明原因，不把用户永远困在一个没有解释的灰色按钮上。
  byId("send").disabled = busy || sending || !input.value.trim();
  byId("send").title = !input.value.trim() ? "先输入一条消息" : pending ? "请先确认或拒绝视频参数" : busy ? "助手正在回复" : "发送消息";
  byId("activity").textContent = !connected ? "服务未连接" : pending ? "等待你确认视频参数" : busy ? "正在回复…" : "对话会自动保存";
  byId("connection").classList.toggle("connected", connected);
  byId("connection").querySelector("span").textContent = connected ? "已连接" : "未连接";
}
function resizeInput() { input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 150)}px`; updateActivity(); }
function renderText(element, text) {
  const fragment = document.createDocumentFragment();
  // 只解析常用强调和代码，所有内容仍以文本节点写入，避免执行模型输出中的 HTML。
  for (const part of text.split(/(```[\s\S]*?```)/g)) {
    if (part.startsWith("```") && part.endsWith("```")) {
      const block = document.createElement("pre");
      block.textContent = part.slice(3, -3).replace(/^[\w-]*\n/, "");
      fragment.append(block);
      continue;
    }
    for (const inline of part.split(/(\*\*[^*\n]+\*\*|`[^`\n]+`)/g)) {
      if (inline.startsWith("**") && inline.endsWith("**")) {
        const strong = document.createElement("strong"); strong.textContent = inline.slice(2, -2); fragment.append(strong);
      } else if (inline.startsWith("`") && inline.endsWith("`")) {
        const code = document.createElement("code"); code.textContent = inline.slice(1, -1); fragment.append(code);
      } else fragment.append(document.createTextNode(inline));
    }
  }
  element.replaceChildren(fragment);
  element.dataset.raw = text;
}
function renderMessages(view, jobs) {
  const area = byId("scroll-area");
  const nearBottom = area.scrollHeight - area.scrollTop - area.clientHeight < 120;
  const items = projectConversation(view, jobs);

  byId("welcome").hidden = items.length > 0;
  const retained = new Set();
  const chat = byId("chat");
  items.forEach((item, index) => {
    retained.add(item.id);
    let node = messageNodes.get(item.id);
    if (!node) {
      node = document.createElement("article");
      node.className = `message ${item.role}`;
      const avatar = document.createElement("span");
      avatar.className = `avatar ${item.role === "user" ? "user-avatar" : "assistant-avatar"}`;
      avatar.textContent = item.role === "user" ? "你" : "✳";
      const body = document.createElement("div");
      body.className = "message-body";
      const meta = document.createElement("div");
      meta.className = "message-meta";
      meta.textContent = item.role === "user" ? "你" : "映语";
      const content = document.createElement("div");
      content.className = "message-content";
      body.append(meta, content); node.append(avatar, body);
      messageNodes.set(item.id, node);
    }
    const content = node.querySelector(".message-content");
    let badge = node.querySelector(".request-badge");
    const hasTool = item.parts.some((part) => part.kind === "tool");
    if (hasTool && !badge) {
      badge = document.createElement("span"); badge.className = "request-badge"; badge.textContent = "同一次任务";
      node.querySelector(".message-meta").append(badge);
    }
    // 每段内容有稳定 ID：工具进度和后续流式正文都留在原助手节点内部。
    const oldParts = new Map([...content.children].map((part) => [part.dataset.id, part]));
    const retainedParts = new Set();
    item.parts.forEach((part, position) => {
      retainedParts.add(part.id);
      let element = oldParts.get(part.id);
      if (!element) { element = document.createElement("div"); element.dataset.id = part.id; }
      const inlineJob = part.kind === "tool" && part.job?.parameters;
      element.className = part.kind === "tool" ? inlineJob ? "message-part inline-video-block" : "message-part tool-progress" : "message-part";
      element.classList.toggle("streaming", Boolean(part.streaming));
      element.classList.toggle("thinking-dots", Boolean(part.thinking));
      if (inlineJob) {
        renderVideoJob(element, part.job);
      } else if (part.kind === "tool") {
        element.dataset.status = part.status;
        element.textContent = `${part.status === "completed" ? "✓" : part.status === "rejected" || part.status === "cancelled" ? "—" : "◌"}  ${part.text}`;
      } else if (element.dataset.raw !== part.text) renderText(element, part.text);
      if (content.children[position] !== element) content.insertBefore(element, content.children[position] ?? null);
    });
    for (const [id, element] of oldParts) if (!retainedParts.has(id)) element.remove();
    if (chat.children[index] !== node) chat.insertBefore(node, chat.children[index] ?? null);
  });
  for (const [id, node] of messageNodes) if (!retained.has(id)) { node.remove(); messageNodes.delete(id); }
  if (nearBottom || scrollOnUpdate) { area.scrollTop = area.scrollHeight; scrollOnUpdate = false; }
}

async function post(path, body) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: AbortSignal.timeout(15000) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error ?? "请求失败，请重试");
  return data;
}
function renderVideoJob(element, job) {
    // SSE 的正文更新不应覆盖正在编辑的表单；仅后端保存的任务状态变化时重建卡片。
    const signature = JSON.stringify(job);
    if (element.dataset.jobSignature === signature) return;
    const firstAppearance = !element.dataset.jobSignature;
    element.dataset.jobSignature = signature;
    const node = byId("approval-template").content.cloneNode(true);
    const card = node.querySelector(".job");
    card.classList.add("inline-video-job");
    card.dataset.jobId = job.id;
    card.dataset.status = job.status;
    const statuses = { awaiting_confirmation: "等待你确认参数", generating: "正在模拟生成…", completed: "模拟生成完成", rejected: "已拒绝，未生成", cancelled: "任务已取消" };
    node.querySelector(".job-status").textContent = job.status === "awaiting_confirmation" && job.decision !== "pending"
      ? job.decision === "approved" ? "参数已确认，准备生成" : "已拒绝，正在结束" : statuses[job.status];
    const form = node.querySelector("form");
    form.elements.prompt.value = job.parameters.prompt;
    form.elements.duration.value = String(job.parameters.duration);
    form.elements.resolution.value = job.parameters.resolution;
    const pending = job.decision === "pending" && job.status === "awaiting_confirmation";
    for (const field of form.elements) field.disabled = !pending;
    node.querySelector(".actions").hidden = !pending;
    node.querySelector(".approval-note").hidden = !pending;
    // 批准后原地变成只读参数摘要和进度，后续助手正文接在这个块后面。
    form.hidden = !pending;
    const summary = node.querySelector(".job-summary");
    summary.hidden = pending;
    summary.querySelector(".summary-prompt").textContent = job.parameters.prompt;
    summary.querySelector(".summary-params").textContent = `${job.parameters.duration} 秒 · ${job.parameters.resolution}`;
    node.querySelector(".job-description").textContent = job.status === "completed" ? "Mock 结果已保存。此次演示没有生成真实视频文件。" : "";
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const decision = event.submitter?.value ?? "approved";
      for (const button of form.querySelectorAll("button")) button.disabled = true;
      showError("");
      try {
        await post("/api/decisions", { jobId: job.id, decision,
          parameters: { prompt: form.elements.prompt.value, duration: Number(form.elements.duration.value), resolution: form.elements.resolution.value } });
      } catch (error) {
        showError(error.message);
        for (const button of form.querySelectorAll("button")) button.disabled = false;
      }
    });
    element.replaceChildren(node);
    if (firstAppearance && pending) scrollOnUpdate = true;
}
function render(state) {
  currentState = state;
  byId("model").textContent = state.model;
  renderMessages(state.view, state.jobs);
  byId("task-count").textContent = String(Object.keys(state.jobs).length);
  byId("saved-state").textContent = JSON.stringify({ sessionId: state.sessionId, jobs: state.jobs, live: state.view.docs["pi.live"] }, null, 2);
  updateActivity();
}

byId("message-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (byId("send").disabled) return;
  if (!connected) { showError("后端尚未连接。请启动 start.cmd，并通过 http://127.0.0.1:8787/ 使用助手。"); return; }
  const message = input.value.trim();
  let pending;
  try { pending = JSON.parse(sessionStorage.getItem("pending-message") ?? "null"); } catch { pending = null; }
  if (!pending || pending.message !== message) pending = { message, requestId: crypto.randomUUID() };
  try { sessionStorage.setItem("pending-message", JSON.stringify(pending)); } catch { /* 存储被禁用时仍允许聊天。 */ }
  sending = true; scrollOnUpdate = true; updateActivity(); showError("");
  try {
    await post("/api/messages", pending);
    try { sessionStorage.removeItem("pending-message"); } catch { /* 不影响已提交消息。 */ }
    input.value = ""; resizeInput(); input.focus();
  } catch (error) { showError(error.message); }
  finally { sending = false; updateActivity(); }
});
input.addEventListener("input", resizeInput);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); byId("message-form").requestSubmit(); }
});
for (const button of document.querySelectorAll("[data-prompt]")) button.addEventListener("click", () => { input.value = button.dataset.prompt; resizeInput(); input.focus(); });
byId("toggle-tasks").onclick = jumpToVideo;
byId("tasks-nav").onclick = jumpToVideo;
byId("chat-nav").onclick = () => { input.focus(); };
byId("toggle-debug").onclick = () => { byId("debug-panel").hidden = !byId("debug-panel").hidden; };
byId("close-debug").onclick = () => { byId("debug-panel").hidden = true; };

function showConnectionNotice(title, text) {
  byId("connection-notice").hidden = false;
  byId("notice-title").textContent = title;
  byId("notice-text").textContent = text;
}
if (location.protocol === "file:") {
  // 直接打开 HTML 时也能加载相对路径样式，并明确提示缺少后端，而非永远等连接。
  showConnectionNotice("还没有连接后端", "请先双击 Demo 目录里的 start.cmd，再通过本地服务页面使用助手。");
  // 用户仍在旧 HTML 标签页刷新时，直接切到同一应用的 HTTP 入口。
  location.replace("http://127.0.0.1:8787/");
} else {
  byId("open-service").href = location.origin;
  const events = new EventSource("/api/events");
  const timer = setTimeout(() => { if (!connected) showConnectionNotice("服务尚未连接", "请检查启动窗口是否有错误；页面会自动重连。"); }, 4000);
  events.addEventListener("state", (event) => {
    try {
      connected = true; clearTimeout(timer); byId("connection-notice").hidden = true;
      render(JSON.parse(event.data));
    } catch { showError("页面状态读取失败，请刷新页面。"); }
  });
  events.onerror = () => {
    connected = false; updateActivity();
    showConnectionNotice("连接暂时断开", "页面会自动重连，后台已保存的对话和视频任务不会因此丢失。");
  };
}
resizeInput();
}

if (typeof document !== "undefined") startPage();
