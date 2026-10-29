import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";
import test from "node:test";
import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
import { createModels } from "@earendil-works/pi-ai/models";
import { fauxAssistantMessage, fauxProvider, fauxToolCall } from "@earendil-works/pi-ai/providers/faux";
import { MemoryStorage, type ConversationId, type Harness } from "@earendil-works/pi-durable";
import { openNodeSqliteStorage } from "@earendil-works/pi-durable/storage/sqlite/node";
import { decideVideo, openVideoSession, parseParams, Videos } from "./video.ts";

const context = BACKGROUND_CONTEXT;
const model = { provider: "faux", modelId: "faux-1" };
const params = { prompt: "雨夜城市", duration: 5, resolution: "720p" as const };
function mockModels() {
  // 测试只调用 Pi 自带的模拟模型，不加载 .env，也不发起网络请求。
  const faux = fauxProvider({ tokensPerSecond: 10000 });
  faux.setResponses([
    fauxAssistantMessage(fauxToolCall("generate_video", params, { id: "call-video" }), { stopReason: "toolUse" }),
    fauxAssistantMessage("工具已处理，本次没有生成真实视频文件。"),
  ]);
  const models = createModels();
  models.setProvider(faux.provider);
  return models;
}
async function firstJob(harness: Harness, conversationId: ConversationId) {
  const root = await harness.root(context);
  assert.equal(root.id, conversationId);
  for (let i = 0; i < 150; i++) {
    const job = Object.values((await harness.snapshot(Videos, root.id, context))?.jobs ?? {})[0];
    if (job) return job;
    await sleep(20);
  }
  throw new Error("模拟模型未在限定时间内提出视频工具调用");
}

test("待确认状态跨 SQLite 重开保留；批准修改后的参数后完成，同一输入不重复执行", { timeout: 12000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), "pi-video-test-"));
  const path = join(directory, "agent.sqlite");
  const models = mockModels();
  let opened = await openVideoSession(await openNodeSqliteStorage(path), models, model, 1500);
  try {
    const input = { type: "input" as const, content: "生成视频", requestId: "video-request-1" };
    await opened.root.submit(input, context);
    const job = await firstJob(opened.harness, opened.root.id);
    assert.equal(job.status, "awaiting_confirmation");
    assert.equal(job.result, undefined);
    assert.equal((await opened.harness.getTask(job.taskId, context))?.state.status, "running");

    // 页面刷新等价于重新读取后端状态；不会批准任务，也不会新建任务。
    const refreshed = await opened.harness.snapshot(Videos, opened.root.id, context);
    assert.equal(refreshed?.jobs[job.id]?.decision, "pending");

    // 正常关闭 Harness 后重开同一数据库，验证持久化恢复；不声称等价于断电实验。
    await opened.harness.close(context);
    opened = await openVideoSession(await openNodeSqliteStorage(path), models, model, 1500);
    opened.harness.resume();
    await sleep(50);
    assert.equal((await opened.harness.snapshot(Videos, opened.root.id, context))?.jobs[job.id]?.status, "awaiting_confirmation");
    const approved = { ...params, duration: 10 };
    await decideVideo(opened.root, job.id, "approved", approved);
    await decideVideo(opened.root, job.id, "approved", approved);
    await assert.rejects(decideVideo(opened.root, job.id, "approved", params), /已经处理/);
    let generating = false;
    for (let i = 0; i < 100; i++) {
      generating = (await opened.harness.snapshot(Videos, opened.root.id, context))?.jobs[job.id]?.status === "generating";
      if (generating) break;
      await sleep(20);
    }
    assert.ok(generating, "批准后应进入生成阶段");
    const checkpoint = (await opened.harness.getTask(job.taskId, context))!.state.checkpoint;
    // 已批准后的生成阶段也需要恢复；不能再次要求确认或重新创建生成任务。
    await opened.harness.close(context);
    opened = await openVideoSession(await openNodeSqliteStorage(path), models, model, 1500);
    assert.deepEqual((await opened.harness.getTask(job.taskId, context))!.state.checkpoint, checkpoint);
    opened.harness.resume();
    await opened.root.waitForIdle(context);
    const jobs = (await opened.harness.snapshot(Videos, opened.root.id, context))!.jobs;
    assert.equal(Object.keys(jobs).length, 1);
    assert.equal(jobs[job.id]!.status, "completed");
    assert.equal(jobs[job.id]!.parameters.duration, 10);
    assert.equal(jobs[job.id]!.result?.mock, true);

    await (await opened.root.submit(input, context)).wait(context);
    const history = await opened.root.context(context);
    assert.equal(history.messages.filter((message) => message.role === "user").length, 1);
    assert.ok(history.messages.some((message) => message.role === "toolResult" && !message.isError));
  } finally {
    await opened.harness.close(context);
    // 仅删除 mkdtemp 创建的本次测试目录，并先核对绝对路径范围。
    assert.ok(resolve(directory).startsWith(`${resolve(tmpdir())}${sep}pi-video-test-`));
    await rm(directory, { recursive: true, force: true });
  }
});

test("拒绝后不会生成；无效参数不能得到批准", { timeout: 8000 }, async () => {
  const { harness, root } = await openVideoSession(new MemoryStorage(), mockModels(), model, 20);
  try {
    await root.submit({ type: "input", content: "生成视频" }, context);
    const job = await firstJob(harness, root.id);
    await assert.rejects(decideVideo(root, job.id, "approved", { ...params, duration: 999 }), /时长/);
    await decideVideo(root, job.id, "rejected", undefined);
    await root.waitForIdle(context);
    const rejected = (await harness.snapshot(Videos, root.id, context))!.jobs[job.id]!;
    assert.equal(rejected.status, "rejected");
    assert.equal(rejected.result, undefined);
    assert.throws(() => parseParams({ ...params, prompt: "" }), /提示词/);
  } finally { await harness.close(context); }
});
