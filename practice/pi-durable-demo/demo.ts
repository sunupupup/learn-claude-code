import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { spawn } from "node:child_process";
import { loadEnvFile } from "node:process";
import { fileURLToPath } from "node:url";
import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
import { createModels } from "@earendil-works/pi-ai/models";
import { deepseekProvider } from "@earendil-works/pi-ai/providers/deepseek";
import { openNodeSqliteStorage } from "@earendil-works/pi-durable/storage/sqlite/node";
import { decideVideo, openVideoSession, RequestError, Videos } from "./video.ts";

const context = BACKGROUND_CONTEXT;
// 只在后端加载配置；已有环境变量优先，其次本 Demo .env，再其次仓库根 .env。
for (const path of ["./.env", "../../.env"]) {
  const file = fileURLToPath(new URL(path, import.meta.url));
  if (existsSync(file)) loadEnvFile(file);
}
const key = process.env.DEEPSEEK_API_KEY;
if (!key) throw new Error("请在仓库根 .env 配置 DEEPSEEK_API_KEY");
const modelId = process.env.DEEPSEEK_MODEL ?? "deepseek-flash";
const models = createModels();
models.setProvider(deepseekProvider());
if (!models.getModel("deepseek", modelId)) throw new Error("DEEPSEEK_MODEL 不在当前 Pi 模型目录中");

const port = Number(process.env.VIDEO_DEMO_PORT ?? 8787);
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("VIDEO_DEMO_PORT 必须在 1024～65535 之间");
const database = fileURLToPath(new URL(process.env.VIDEO_DEMO_DATABASE ?? "./.state/video.sqlite", import.meta.url));
const storage = await openNodeSqliteStorage(database);
const { harness, root } = await openVideoSession(storage, models, { provider: "deepseek", modelId });

// 一个本地共享会话。每个重连客户端先接收当前完整快照，再接收后续更新。
const viewWatch = await root.watch(context);
const videoWatch = await harness.watchDoc(Videos, root.id, context);
if (!videoWatch) throw new Error("视频状态初始化失败");
let view = viewWatch.value;
let videos = videoWatch.value;
const clients = new Set<ServerResponse>();
const blocked = new WeakSet<ServerResponse>();
const dirty = new WeakSet<ServerResponse>();
const encode = (value: unknown) => JSON.stringify(value).replaceAll(key, "[已隐藏]");
const state = () => ({ sessionId: root.id, model: modelId, view, jobs: videos?.jobs ?? {} });
const awaitDrain = (res: ServerResponse) => {
  blocked.add(res);
  res.once("drain", () => {
    blocked.delete(res);
    // 等可写后只补最新状态，不无限堆积流式快照。
    if (dirty.has(res)) { dirty.delete(res); push(res); }
  });
};
const push = (res: ServerResponse) => {
  if (res.destroyed || res.writableEnded) { clients.delete(res); return; }
  if (blocked.has(res)) { dirty.add(res); return; }
  // write(false) 只表示背压，当前帧仍已入队；大快照也会触发，不能因此断开正常连接。
  if (!res.write(`event: state\ndata: ${encode(state())}\n\n`)) awaitDrain(res);
};
const broadcast = () => { for (const client of clients) push(client); };
viewWatch.start(async (value) => { view = value; broadcast(); });
videoWatch.start(async (value) => { videos = value; broadcast(); });

async function readBody(req: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = [];
  let bytes = 0;
  for await (const chunk of req) {
    bytes += chunk.length;
    if (bytes > 16_384) throw new RequestError("请求过大", 413);
    chunks.push(chunk);
  }
  try {
    // 合并字节后再解码，避免中文字符刚好跨网络分块时被破坏。
    const value: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    if (value && typeof value === "object" && !Array.isArray(value)) return value as Record<string, unknown>;
  } catch { /* 对外只返回简短格式错误，不回显原请求或环境信息。 */ }
  throw new RequestError("请求必须是 JSON 对象");
}

const files: Record<string, [string, string]> = {
  "/": ["index.html", "text/html; charset=utf-8"],
  "/index.html": ["index.html", "text/html; charset=utf-8"],
  "/app.js": ["app.js", "text/javascript; charset=utf-8"],
  "/style.css": ["style.css", "text/css; charset=utf-8"],
};
const json = (res: ServerResponse, status: number, body: unknown) => {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
  res.end(encode(body));
};

const server = createServer((req, res) => {
  void (async () => {
    const path = new URL(req.url ?? "/", `http://127.0.0.1:${port}`).pathname;
    if (req.method === "GET" && files[path]) {
      const [name, type] = files[path]!;
      res.writeHead(200, { "Content-Type": type, "Cache-Control": "no-store" });
      res.end(await readFile(new URL(`./public/${name}`, import.meta.url)));
    } else if (req.method === "GET" && path === "/api/state") {
      json(res, 200, state());
    } else if (req.method === "GET" && path === "/api/events") {
      res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive" });
      clients.add(res);
      res.on("close", () => clients.delete(res));
      push(res);
    } else if (req.method === "POST") {
      // 本地 Demo 只接受本页面发起的写入，不向任意网站开放密钥支持的请求。
      if (req.headers.origin && ![`http://127.0.0.1:${port}`, `http://localhost:${port}`].includes(req.headers.origin)) {
        throw new RequestError("来源不允许", 403);
      }
      const body = await readBody(req);
      if (path === "/api/messages") {
        if (typeof body.message !== "string" || !body.message.trim() || body.message.length > 2000
          || typeof body.requestId !== "string" || !/^[a-zA-Z0-9-]{1,80}$/.test(body.requestId)) {
          throw new RequestError("请输入 1～2000 字消息和有效 requestId");
        }
        // 只提交，不等待回答；工具可能正在等待用户批准，HTTP 请求不能一直挂住。
        const submission = await root.submit({
          type: "input", content: body.message.trim(), requestId: body.requestId, whenBusy: "reject",
        }, context);
        json(res, 202, { submissionId: submission.id });
      } else if (path === "/api/decisions") {
        if (typeof body.jobId !== "string") throw new RequestError("缺少任务编号");
        await decideVideo(root, body.jobId, body.decision, body.parameters);
        json(res, 200, { ok: true });
      } else json(res, 404, { error: "接口不存在" });
    } else json(res, 404, { error: "页面不存在" });
  })().catch((error: unknown) => {
    if (res.headersSent) { res.end(); return; }
    // 不把厂商原始异常或请求头送到前端；忙碌时客户端可刷新查看当前任务。
    json(res, error instanceof RequestError ? error.status : 409, {
      error: error instanceof RequestError ? error.message : "请求未受理，请查看当前任务；模型异常请查看执行记录。",
    });
  });
});

const heartbeat = setInterval(() => {
  for (const client of clients) {
    if (client.destroyed || client.writableEnded) { clients.delete(client); continue; }
    if (!blocked.has(client) && !client.write(": heartbeat\n\n")) awaitDrain(client);
  }
}, 15_000);
heartbeat.unref();

let closing = false;
async function close() {
  if (closing) return;
  closing = true;
  clearInterval(heartbeat);
  for (const client of clients) client.end();
  server.close();
  await Promise.all([viewWatch.stop(), videoWatch!.stop()]);
  // 服务关闭只停止本进程，不调用任务取消；下次启动保留待确认和生成检查点。
  await harness.close(context);
}
process.once("SIGINT", () => void close());
process.once("SIGTERM", () => void close());
server.once("error", () => { console.error("启动失败：端口不可用"); process.exitCode = 1; void close(); });
server.listen(port, "127.0.0.1", () => {
  console.log(`视频审批 Demo：http://127.0.0.1:${port}`);
  console.log(`数据库：${database}；PID=${process.pid}`);
  // 页面是否连接不影响后端恢复；SSE 重连会重新获取当前快照。
  harness.resume();
  // 双击 start.cmd 时，在服务已就绪后打开页面，避免误用 file:// 静态预览。
  if (process.env.VIDEO_DEMO_OPEN_BROWSER === "1" && process.platform === "win32") {
    spawn("cmd.exe", ["/c", "start", "", `http://127.0.0.1:${port}/`], { windowsHide: true, stdio: "ignore" });
  }
});
