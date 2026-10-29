import assert from "node:assert/strict";
import test from "node:test";
import { projectConversation } from "./public/app.js";

const user = (text) => ({ role: "user", content: text });
const assistant = (text, calls = []) => ({ role: "assistant", content: [{ type: "text", text }, ...calls] });
const call = { type: "toolCall", id: "call-1", name: "generate_video" };
const view = (messages, live = {}) => ({ entries: messages.map((message, id) => ({ id, model: [message] })), docs: { "pi.live": live } });

test("工具前后的助手消息展示在同一个回复区，刷新重建保持一致", () => {
  const input = view([
    user("生成视频"), assistant("我先整理参数。", [call]),
    { role: "toolResult", toolCallId: "call-1", content: [{ type: "text", text: JSON.stringify({ id: "video-7" }) }] },
    assistant("模拟生成已完成。"),
  ]);
  const jobs = { "video-7": { id: "video-7", status: "completed", parameters: { prompt: "雨夜", duration: 5, resolution: "720p" } } };
  const projected = projectConversation(input, jobs);
  assert.deepEqual(projected.map((item) => item.role), ["user", "assistant"]);
  assert.deepEqual(projected[1].parts.map((part) => part.kind), ["text", "tool", "text"]);
  assert.equal(projected[1].parts[1].status, "completed");
  assert.deepEqual(projected[1].parts[1].job.parameters, jobs["video-7"].parameters);
  assert.deepEqual(projectConversation(JSON.parse(JSON.stringify(input)), jobs), projected);
});

test("待确认状态和后续流式正文都沿用同一个回复 ID", () => {
  const messages = [user("生成视频"), assistant("等待确认。", [call])];
  const jobs = { "video-7": { id: "video-7", status: "awaiting_confirmation", decision: "pending", parameters: { prompt: "雨夜", duration: 5, resolution: "720p" } } };
  const pendingView = view(messages, { tools: [{ callId: "call-1", taskId: 7 }] });
  const pending = projectConversation(pendingView, jobs);
  const streaming = projectConversation(view(messages, { generation: { message: assistant("已完成，") } }));
  assert.equal(pending[1].parts[1].status, "awaiting_confirmation");
  assert.equal(pending[1].parts[1].job.id, "video-7");
  assert.deepEqual(projectConversation(JSON.parse(JSON.stringify(pendingView)), jobs), pending);
  assert.equal(streaming[1].id, pending[1].id);
  assert.equal(streaming[1].parts.at(-1).streaming, true);
  assert.equal(streaming.length, 2);
});

test("不同用户消息分别展示，普通聊天不凭空增加工具进度", () => {
  const projected = projectConversation(view([user("你好"), assistant("你好！"), user("解释一下"), assistant("解释内容。") ]));
  assert.deepEqual(projected.map((item) => item.role), ["user", "assistant", "user", "assistant"]);
  assert.notEqual(projected[1].id, projected[3].id);
  assert.ok(projected.every((item) => item.parts.every((part) => part.kind === "text")));
});
