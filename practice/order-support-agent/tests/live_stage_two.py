"""对正在运行的本地服务执行真实模型故事；显式运行，会产生 API 调用。"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from time import perf_counter
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8765"
HEADERS = {"Content-Type": "application/json", "X-Agent-Client": "web"}
REPORT = []


def post(path, body):
    request = Request(BASE + path, data=json.dumps(body).encode(), headers=HEADERS)
    with urlopen(request, timeout=120) as response:
        if "text/event-stream" not in response.headers["Content-Type"]:
            return json.load(response)
        start = perf_counter()
        events = []
        for raw in response:
            if raw.startswith(b"data: "):
                events.append((perf_counter() - start, json.loads(raw[6:])))
        snapshot = events[-1][1]
        assert "items" in snapshot and not snapshot["busy"], "缺少 done 快照"
        deltas = [e for e in events if set(e[1]) == {"id", "text"}]
        REPORT.append({"path": path, "delta_count": len(deltas), "first_delta_seconds": round(deltas[0][0], 3) if deltas else None,
                       "duration_seconds": round(events[-1][0], 3), "snapshot": snapshot})
        # 断言失败也保留当时的真实响应，便于定位而非盲目重跑。
        out = Path(__file__).resolve().parents[1] / ".local" / "stage-two-live.json"
        out.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding="utf-8")
        return snapshot


def new():
    return post("/api/sessions", {})["id"]


def chat(sid, text):
    return post(f"/api/sessions/{sid}/messages", {"text": text})


def approval(snapshot):
    return next(i["operation"] for i in reversed(snapshot["items"]) if i["kind"] == "approval")


def choose_if_needed(sid, snapshot, order_id):
    if snapshot["candidates"]:
        assert order_id in snapshot["candidates"]
        return post(f"/api/sessions/{sid}/select", {"order_id": order_id})
    return snapshot


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tomorrow = (datetime.now(timezone(timedelta(hours=8))).date() + timedelta(days=1)).isoformat()
    sid = new()
    selected = chat(sid, f"昨天买的耳机最晚需要在 {tomorrow} 20:00 收到，能赶上就催一下，赶不上就退款。")
    assert len(selected["candidates"]) == 2
    refund = post(f"/api/sessions/{sid}/select", {"order_id": "ORD-1002"})
    op = approval(refund)
    assert op["action"] == "refund" and op["amount_cents"] == 29900 and op["status"] == "waiting"
    done = post(f"/api/sessions/{sid}/decide", {"operation_id": op["id"], "approved": True})
    assert approval(done)["status"] == "submitted"
    print("PASS: 多订单选择 → 物流与规则 → 299 元退款确认 → 模拟申请提交", flush=True)

    sid = new()
    expedite = chat(sid, f"白色耳机最晚 {tomorrow} 20:00 收到，能赶上就帮我催一下。")
    expedite = choose_if_needed(sid, expedite, "ORD-1001")
    op = approval(expedite)
    assert op["action"] == "expedite"
    done = post(f"/api/sessions/{sid}/decide", {"operation_id": op["id"], "approved": True})
    assert approval(done)["application_id"].startswith("EX-")
    print("PASS: 预计能到 → 催单确认 → 工单提交", flush=True)

    sid = new()
    refund = chat(sid, "白色耳机不需要了，帮我申请退款。")
    refund = choose_if_needed(sid, refund, "ORD-1001")
    op = approval(refund)
    cancelled = post(f"/api/sessions/{sid}/decide", {"operation_id": op["id"], "approved": False})
    assert approval(cancelled)["status"] == "cancelled"
    assert "application_id" not in approval(cancelled)
    print("PASS: 取消退款 → 没有申请编号", flush=True)

    unknown = chat(new(), "充电线明天晚上20点前能收到吗？赶不上就退款。")
    assert unknown["pending"] is None
    assert any(i.get("name") == "get_logistics" and i.get("result", {}).get("estimated_arrival", "missing") is None for i in unknown["items"])
    print("PASS: 无预计时间 → 不自动退款（回复含义需人工检查）", flush=True)

    unclear = chat(new(), "白色耳机周五出差前能收到吗？能到就催一下。")
    assert unclear["pending"] is None
    print("PASS: 截止时间不明确 → 不自动执行（澄清内容需人工检查）", flush=True)

    manual = chat(new(), "定制键帽不想要了，帮我退款。")
    assert manual["pending"] is None
    assert any(i.get("name") == "query_rules" and i.get("result", {}).get("status") == "manual_required" for i in manual["items"])
    print("PASS: 规则缺失 → 人工处理", flush=True)
    out = Path(__file__).resolve().parents[1] / ".local" / "stage-two-live.json"
    out.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding="utf-8")
    print("保存本地脱敏报告；本次通过不代表多次采样成功率。")


if __name__ == "__main__":
    main()
