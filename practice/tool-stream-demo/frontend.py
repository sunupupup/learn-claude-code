"""终端前端：通过管道与独立后端通信，不导入后端执行逻辑。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from model import ROOT
from state import empty, reduce, stable


class Client:
    def __init__(self, session, data_dir=None, fault=None, delay=0.4):
        self.directory = Path(data_dir or ROOT / "data")
        self.session = session
        args = [sys.executable, "-u", str(ROOT / "backend.py"), "--session", session,
                "--data-dir", str(self.directory), "--delay", str(delay)]
        if fault:
            args += ["--fault", fault]
        self.process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, encoding="utf-8")
        self.state, self.events, self.last_seq = empty(), [], 0

    def send(self, **command):
        self.process.stdin.write(json.dumps(command) + "\n")
        self.process.stdin.flush()

    def receive(self):
        line = self.process.stdout.readline()
        if not line:
            return None
        event = json.loads(line)
        if event["sessionId"] != self.session or event["seq"] <= self.last_seq:
            raise ValueError("事件会话或顺序不匹配")
        self.last_seq = event["seq"]
        self.events.append(event)
        if event["type"] in ("session_ready", "restored"):
            self.state = event["state"]
        else:
            reduce(self.state, event)
        return event

    def close(self):
        if self.process.poll() is None:
            try:
                self.send(command="quit")
            except OSError:
                pass
        self.process.wait(timeout=10)
        try:
            self.process.stdin.close()
        except OSError:
            pass  # Windows 的已断开管道在 flush/close 时可能返回 EINVAL。
        self.process.stdout.close()
        # 此处只在已 wait 确认子进程退出后清理自己的锁，绝不抢活跃进程的锁。
        lock = self.directory / (self.session + ".lock")
        if lock.exists() and lock.read_text() == str(self.process.pid):
            lock.unlink()  # 启动被已有锁拒绝时，不能删掉另一个后端持有的锁。


def show(event):
    kind = event["type"]
    prefix = f"[{event['seq']:02d} {'落盘' if event['durable'] else '实时'}]"
    if kind == "message_update":
        print(prefix, "模型分片：", event["delta"], flush=True)
    elif kind == "message_end":
        message = event["message"]
        print(prefix, message["role"] + "：", message.get("content"), flush=True)
    elif kind == "tool_execution_start":
        print(prefix, "工具运行", event["toolCallId"], event["name"], event["arguments"], flush=True)
    elif kind == "tool_execution_update":
        print(prefix, event["toolCallId"], event["output"], flush=True)
    elif kind == "tool_execution_end":
        print(prefix, "失败" if event["isError"] else "成功", event["output"], flush=True)
    elif kind in ("session_ready", "restored"):
        print(prefix, "会话状态", json.dumps(event["state"], ensure_ascii=False), flush=True)
        if event.get("warning"):
            print(event["warning"], flush=True)
    else:
        print(prefix, kind, event.get("status", event.get("error", "")), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", default="demo_" + uuid4().hex[:8])
    parser.add_argument("--mode", choices=["offline", "live"], default="offline")
    parser.add_argument("--fail", action="store_true")
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--fault", choices=["interrupt", "after-persist"])
    args = parser.parse_args()
    client = Client(args.session, fault=args.fault)
    print(f"前端 PID={__import__('os').getpid()}，后端 PID={client.process.pid}，sessionId={args.session}", flush=True)
    try:
        ready = client.receive()
        if ready is None:
            raise RuntimeError("后端启动失败")
        show(ready)
        client.send(command="restore" if args.restore else "start", mode=args.mode, fail=args.fail)
        while (event := client.receive()) is not None:
            show(event)
            if event["type"] in ("task_end", "restored", "rpc_error"):
                break
    except KeyboardInterrupt:
        client.process.terminate()
        print("已停止后端；未结束的工具结果未知。")
    finally:
        client.close()
    print("前端最终状态：", json.dumps(stable(client.state, disconnected=True), ensure_ascii=False))
    if client.process.returncode:
        print("后端异常退出，工具中断/结果未知；请使用同一 sessionId --restore。")
        return 1
    return 1 if client.state["status"] == "failed" else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
