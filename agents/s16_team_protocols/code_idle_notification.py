#!/usr/bin/env python3
"""
s16 补充演示：idle_notification 机制。

s16 code.py 的 idle loop 省略了 idle_notification。
真实 CC 在队友空闲时发 idle_notification 给 Lead，Lead 据此分配新任务或关机。

本文件用模拟工作（无 LLM 调用）展示完整的 idle_notification 生命周期：
  做完任务 → idle_notification → Lead 分配新任务 → 做完 → idle_notification → 无任务 → shutdown

Run:  python s16_team_protocols/code_idle_notification.py
"""

import json, time, random, threading, shutil, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

MAILBOX_DIR = Path.cwd() / ".mailboxes_idle_demo"
MAILBOX_DIR.mkdir(exist_ok=True)

SEP = "=" * 50


# ── MessageBus（同 s15/s16，最小版） ──

class MessageBus:
    def send(self, from_agent, to_agent, content, msg_type="message", metadata=None):
        msg = {
            "from": from_agent, "to": to_agent,
            "content": content, "type": msg_type,
            "metadata": metadata or {}, "ts": time.time(),
        }
        inbox = MAILBOX_DIR / f"{to_agent}.jsonl"
        with open(inbox, "a") as f:
            f.write(json.dumps(msg) + "\n")
        print(f"    [bus] {from_agent} -> {to_agent} ({msg_type}): {content[:60]}")

    def read_inbox(self, agent):
        inbox = MAILBOX_DIR / f"{agent}.jsonl"
        if not inbox.exists():
            return []
        msgs = [json.loads(l) for l in inbox.read_text().splitlines() if l.strip()]
        inbox.unlink()
        return msgs

BUS = MessageBus()


# ── Teammate 线程：做完工作 → idle_notification → 等分配或关机 ──

def teammate_thread(name, initial_task):
    """模拟队友：完成任务后发 idle_notification，等待 Lead 分配新工作或关机。"""

    def do_work(task):
        """模拟执行任务（真实场景是 LLM tool_use 循环）。"""
        print(f"    [{name}] working: {task}")
        time.sleep(1)
        BUS.send(name, "lead", f"Done: {task}", "result")

    do_work(initial_task)

    while True:
        # 关键行为：工作完成后通知 Lead 自己空闲了
        BUS.send(name, "lead",
                 f"{name} finished current work, available for new tasks.",
                 "idle_notification")

        # 进入 idle 轮询，等 Lead 发消息过来
        while True:
            time.sleep(0.5)
            inbox = BUS.read_inbox(name)
            if not inbox:
                continue

            for msg in inbox:
                if msg["type"] == "shutdown_request":
                    req_id = msg.get("metadata", {}).get("request_id", "")
                    BUS.send(name, "lead", "Shutdown approved.",
                             "shutdown_response",
                             {"request_id": req_id, "approve": True})
                    print(f"    [{name}] exiting")
                    return

                # 收到新任务消息 → 跳出 idle 回到工作循环
                do_work(msg["content"])

            break  # 回到外层，工作完成后再发 idle_notification


# ── Lead 主逻辑（模拟，无 LLM） ──

def lead_main():
    """模拟 Lead：收到 idle_notification 后决定分配新任务还是关机。"""

    # Lead 手里有一个待分配的任务队列
    task_queue = ["Write unit tests for schema", "Update README with API docs"]

    print(f"\n{SEP}")
    print("Lead: spawning alice (backend developer)")
    print(f"Lead: task queue = {task_queue}")
    print(SEP)

    t = threading.Thread(
        target=teammate_thread,
        args=("alice", "Create schema.sql"),
        daemon=True,
    )
    t.start()

    step = 0
    while True:
        time.sleep(0.8)
        inbox = BUS.read_inbox("lead")
        if not inbox:
            continue

        for msg in inbox:
            msg_type = msg["type"]

            if msg_type == "result":
                print(f"\n  [lead] got result from {msg['from']}: {msg['content']}")

            elif msg_type == "idle_notification":
                step += 1
                print(f"\n{SEP}")
                print(f"Step {step}: Lead received idle_notification from {msg['from']}")

                if task_queue:
                    next_task = task_queue.pop(0)
                    print(f"  [lead] assigning new task: {next_task}")
                    print(f"  [lead] remaining queue: {task_queue}")
                    print(SEP)
                    BUS.send("lead", msg["from"], next_task)
                else:
                    print(f"  [lead] no more tasks, requesting shutdown")
                    print(SEP)
                    req_id = f"req_{random.randint(0, 999999):06d}"
                    BUS.send("lead", msg["from"],
                             "No more work. Please shut down.",
                             "shutdown_request",
                             {"request_id": req_id})

            elif msg_type == "shutdown_response":
                approve = msg.get("metadata", {}).get("approve", False)
                print(f"\n  [lead] {msg['from']} shutdown {'approved' if approve else 'rejected'}")
                shutil.rmtree(MAILBOX_DIR, ignore_errors=True)
                print(f"\n{SEP}")
                print("Demo complete. Full lifecycle:")
                print("  initial task -> result -> idle -> new task -> result")
                print("  -> idle -> new task -> result -> idle -> shutdown")
                print(SEP)
                return


if __name__ == "__main__":
    print("s16: idle_notification demo (no LLM, simulated work)\n")
    lead_main()
