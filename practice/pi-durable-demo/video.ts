import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
import { Type } from "@earendil-works/pi-ai";
import type { Models } from "@earendil-works/pi-ai/models";
import {
  createRegistry, defineDoc, defineExtension, defineTask, defineTool, Harness, section,
  type Conversation, type Storage, type TaskId,
} from "@earendil-works/pi-durable";

const context = BACKGROUND_CONTEXT;
export type VideoParams = { prompt: string; duration: number; resolution: "720p" | "1080p" };
type VideoResult = { jobId: string; status: "completed" | "rejected" };
export type VideoJob = {
  id: string;
  taskId: TaskId<VideoResult>;
  parameters: VideoParams;
  decision: "pending" | "approved" | "rejected";
  status: "awaiting_confirmation" | "generating" | "completed" | "rejected" | "cancelled";
  result?: { mock: true; videoId: string };
};

// 业务文档与 Task 都在同一份 SQLite；网页刷新后从此文档恢复确认卡片。
export const Videos = defineDoc<{ jobs: Record<string, VideoJob> }>({
  kind: "app.videos", version: 1, scope: "conversation", history: "latest", fork: "initial",
  initial: () => ({ jobs: {} }),
});

export class RequestError extends Error {
  readonly status: number;
  constructor(message: string, status = 400) { super(message); this.status = status; }
}

// 后端再次校验确认参数，不以浏览器表单校验作为执行依据。
export function parseParams(value: unknown): VideoParams {
  if (!value || typeof value !== "object") throw new RequestError("缺少视频参数");
  const params = value as Record<string, unknown>;
  if (typeof params.prompt !== "string" || !params.prompt.trim() || params.prompt.length > 1000
    || (params.duration !== 5 && params.duration !== 10)
    || (params.resolution !== "720p" && params.resolution !== "1080p")) {
    throw new RequestError("提示词为 1～1000 字；时长只能是 5 或 10 秒；分辨率为 720p 或 1080p");
  }
  return { prompt: params.prompt.trim(), duration: params.duration, resolution: params.resolution };
}

export async function decideVideo(root: Conversation, jobId: string, decision: unknown, parameters: unknown) {
  if (decision !== "approved" && decision !== "rejected") throw new RequestError("无效的确认操作");
  const finalParams = decision === "approved" ? parseParams(parameters) : undefined;
  return root.commit(async (tx) => {
    const job = (await tx.doc(Videos, root.id)).jobs[jobId];
    if (!job) throw new RequestError("找不到这个视频任务", 404);
    // 重复确认同一份参数返回原状态；不同决定或不同参数必须拒绝，不能覆盖旧批准。
    if (job.decision !== "pending") {
      if (job.decision !== decision || (finalParams && JSON.stringify(job.parameters) !== JSON.stringify(finalParams))) {
        throw new RequestError("该任务已经处理，请刷新查看最新状态", 409);
      }
      return job.status;
    }
    if (job.status !== "awaiting_confirmation") throw new RequestError("任务已不在等待确认", 409);
    if (finalParams) job.parameters = finalParams;
    job.decision = decision;
    return job.status;
  }, context);
}

export async function openVideoSession(
  storage: Storage, models: Models, model: { provider: string; modelId: string }, mockMs = 4000,
) {
  type Checkpoint = { phase: "awaiting_confirmation" } | { phase: "generating"; readyAt: number };
  const VideoTask = defineTask<{ jobId: string }, Checkpoint, VideoResult>({
    name: "demo.video", version: 1,
    initial: () => ({ phase: "awaiting_confirmation" }),
    phases: {
      awaiting_confirmation: async (task, runtime, ctx) => {
        // 这里只等待已持久化的用户决定，不返回 toolResult，不让模型越过确认关卡。
        // 500ms 轮询只是最小 Demo 的唤醒方式；重启后仍读取同一个业务文档。
        for (;;) {
          const job = (await runtime.snapshot(Videos, runtime.conversationId, ctx))?.jobs[task.input.jobId];
          if (!job) throw new Error("视频任务的业务状态丢失");
          if (job.decision === "rejected") {
            await runtime.commit(async (tx) => {
              (await tx.doc(Videos, runtime.conversationId)).jobs[job.id]!.status = "rejected";
              return { status: "terminal", outcome: { status: "completed", result: { jobId: job.id, status: "rejected" } } };
            }, ctx);
            return;
          }
          if (job.decision === "approved") {
            // 生成阶段和业务状态一起提交；模型的建议不能代替用户的批准。
            await runtime.commit(async (tx) => {
              (await tx.doc(Videos, runtime.conversationId)).jobs[job.id]!.status = "generating";
              return { status: "running", checkpoint: { phase: "generating", readyAt: Date.now() + mockMs } };
            }, ctx);
            return;
          }
          await runtime.sleep(Date.now() + 500, ctx);
        }
      },
      generating: async (task, runtime, ctx) => {
        // Mock 无外部服务和扣费：只按持久化截止时间等待，再写一个模拟结果。
        await runtime.sleep(task.state.checkpoint.readyAt, ctx);
        await runtime.commit(async (tx) => {
          const job = (await tx.doc(Videos, runtime.conversationId)).jobs[task.input.jobId]!;
          job.status = "completed";
          job.result = { mock: true, videoId: `mock-${job.id}` };
          return { status: "terminal", outcome: { status: "completed", result: { jobId: job.id, status: "completed" } } };
        }, ctx);
      },
    },
    abort: async (task, runtime, ctx) => {
      await runtime.commit(async (tx) => {
        const job = (await tx.doc(Videos, runtime.conversationId)).jobs[task.input.jobId];
        if (job && job.status !== "completed" && job.status !== "rejected") job.status = "cancelled";
        return { status: "terminal", outcome: { status: "aborted" } };
      }, ctx);
    },
  });

  const generateVideo = defineTool({
    name: "generate_video",
    description: "提出视频参数并等待用户在网页确认；确认后才模拟生成，不产生真实视频文件。",
    parameters: Type.Object({
      prompt: Type.String({ minLength: 1, maxLength: 1000 }),
      duration: Type.Union([Type.Literal(5), Type.Literal(10)]),
      resolution: Type.Union([Type.Literal("720p"), Type.Literal("1080p")]),
    }),
    // 安全来自下面的业务去重：恢复同一工具调用时找到原子任务，而不是再创建一份。
    replay: "safe",
    executionMode: "sequential",
    execute: async (args, api, ctx) => {
      const jobId = `video-${api.taskId}`;
      const taskId = await api.commit(async (tx) => {
        const doc = await tx.doc(Videos, api.conversationId);
        if (doc.jobs[jobId]) return doc.jobs[jobId]!.taskId;
        const taskId = await tx.createTask(VideoTask, { jobId }, { ownership: { kind: "task", taskId: api.taskId } });
        // 原子提交任务与待确认参数，避免留下只有确认卡片、却没有任务的半份状态。
        doc.jobs[jobId] = {
          id: jobId, taskId, parameters: parseParams(args), decision: "pending", status: "awaiting_confirmation",
        };
        return taskId;
      }, ctx);
      api.output("参数已保存，等待用户在网页确认。\n");
      await api.waitForTask(taskId, ctx);
      const job = (await api.snapshot(Videos, api.conversationId, ctx))?.jobs[jobId];
      if (!job) throw new Error("视频任务不存在");
      api.output(`当前状态：${job.status}\n`);
      return {
        content: [{ type: "text", text: JSON.stringify(job) }],
        isError: job.status !== "completed",
      };
    },
  });

  const registry = createRegistry();
  registry.install(defineExtension({
    name: "video-demo", tasks: [VideoTask], tools: [generateVideo],
    sections: [section("video_rules", () =>
      "你是映语，一个友好自然的中文对话助手。默认正常聊天、解释问题、帮助写作，直接回答用户。" +
      "只有用户明确要求实际生成或制作一段视频时，才调用 generate_video；不要只口头承诺。" +
      "问候、普通问答、讨论视频原理、写视频文案、询问你的能力，都不要调用视频工具，也不必主动推销视频。" +
      "明确的视频生成请求未指定参数时，默认 5 秒、720p。工具会等待网页确认，无需用户再发聊天消息批准。" +
      "用户可以在网页修改参数，以工具返回的最终批准参数为准；不要把用户修改时长或分辨率误报为生成错误。" +
      "用户说继续不等于网页批准。用户拒绝后不要自行重试。视频结果是 Mock，必须说明没有真实视频文件。", { tag: false })],
  }));
  const harness = await Harness.open(storage, {
    models, registry,
    settings: { stream: { timeoutMs: 60_000, maxRetries: 0 }, retry: { enabled: false }, compaction: { enabled: false } },
  }, context);
  const root = await harness.root(context, { agent: { model, thinkingLevel: "off" } });
  await root.commit(async (tx) => { await tx.doc(Videos, root.id); }, context);
  return { harness, root };
}
