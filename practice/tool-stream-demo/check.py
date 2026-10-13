"""真实双进程验收；比较内容和顺序，而不是截图、时间戳或运行耗时。"""
import argparse
import json
from pathlib import Path
import tempfile

from frontend import Client
from state import stable


def run(directory, session, mode="offline", fail=False, fault=None):
    client = Client(session, directory, fault, delay=0.01)
    try:
        assert client.receive()["type"] == "session_ready"
        client.send(command="start", mode=mode, fail=fail)
        while (event := client.receive()) is not None:
            if event["type"] in ("task_end", "rpc_error"):
                break
    finally:
        client.close()
    return stable(client.state, disconnected=True), client.events, client.process.returncode


def restore(directory, session):
    path = directory / (session + ".jsonl")
    before = path.read_bytes()
    client = Client(session, directory, delay=0)
    try:
        assert client.receive()["type"] == "session_ready"
        client.send(command="restore")
        event = client.receive()
        assert event["type"] == "restored"
        assert not any(e["type"].startswith("tool_execution") for e in client.events)
        state = event["state"]
    finally:
        client.close()
    assert before == path.read_bytes(), "恢复不应改写或追加会话历史"
    return state, event.get("warning")


def checks(directory, live=False):
    evidence = []
    for name, fail in [("success", False), ("failure", True)]:
        state, events, code = run(directory, name, fail=fail)
        recovered, _ = restore(directory, name)
        assert code == 0 and state == recovered
        assert state["status"] == ("failed" if fail else "completed")
        assert len(state["messages"]) == 4 and len(state["tools"]) == 1
        assert sum(e["type"] == "tool_execution_update" for e in events) == 3
        records = [json.loads(line) for line in (directory / (name + ".jsonl")).read_text(encoding="utf-8").splitlines()]
        assert all(e["durable"] for e in records)
        assert not any(e["type"] in ("message_update", "tool_execution_update") for e in records)
        evidence.append({"case": name, "equal": True, "progressEvents": 3, "messages": 4, "state": state})
    state, events, code = run(directory, "interrupt", fault="interrupt")
    recovered, _ = restore(directory, "interrupt")
    assert code == 71 and state == recovered
    assert recovered["status"] == "interrupted"
    assert next(iter(recovered["tools"].values()))["output"] is None
    assert next(iter(recovered["tools"].values()))["isError"] is None
    interrupted_state = recovered
    evidence.append({"case": "interrupt", "equal": True, "exitCode": code, "state": recovered})
    state, events, code = run(directory, "persist-gap", fault="after-persist")
    recovered, _ = restore(directory, "persist-gap")
    assert code == 72 and state != recovered
    assert next(iter(state["tools"].values()))["status"] == "interrupted"
    assert next(iter(recovered["tools"].values()))["status"] == "succeeded"
    evidence.append({"case": "persist-before-send", "expectedMismatch": True, "exitCode": code,
                     "live": state, "recovered": recovered})
    path = directory / "interrupt.jsonl"
    with path.open("ab") as handle:
        handle.write(b'{"type":')
    tail, warning = restore(directory, "interrupt")
    assert tail == interrupted_state
    assert warning
    evidence.append({"case": "partial-tail", "warning": warning, "status": tail["status"]})
    # 已有历史拒绝 start，证明恢复路径不会隐式再执行工具。
    duplicate = Client("success", directory, delay=0)
    try:
        duplicate.receive()
        duplicate.send(command="start")
        assert duplicate.receive()["type"] == "rpc_error"
    finally:
        duplicate.close()
    evidence.append({"case": "duplicate-start", "rejected": True})
    owner = Client("exclusive", directory, delay=0)
    try:
        owner.receive()
        rejected = Client("exclusive", directory, delay=0)
        try:
            assert rejected.receive() is None
        finally:
            rejected.close()
        assert (directory / "exclusive.lock").read_text() == str(owner.process.pid)
    finally:
        owner.close()
    evidence.append({"case": "exclusive-writer", "rejected": True, "ownerLockPreserved": True})
    if live:
        state, events, code = run(directory, "deepseek", mode="live")
        recovered, _ = restore(directory, "deepseek")
        assert code == 0 and state["status"] == "completed", state
        assert state == recovered and len(state["tools"]) == 1
        assert any(e["type"] == "message_update" for e in events)
        evidence.append({"case": "deepseek-flash", "equal": True, "state": state,
                         "modelDeltas": sum(e["type"] == "message_update" for e in events)})
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="额外访问真实 DeepSeek，产生费用")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tool-stream-check-") as folder:
        evidence = checks(Path(folder), args.live)
    report = {"result": "PASS", "cases": evidence}
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for case in evidence:
        print("PASS", case["case"])
