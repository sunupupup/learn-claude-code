"""显式运行的真实模型故事检查，会产生 API 调用；不参与离线 unittest。"""

from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from order_support_agent.config import DEMO_USER_ID, PROJECT_ROOT, load_settings
from order_support_agent.context import Context
from order_support_agent.debug import DebugLogger
from order_support_agent.loop import run_turn
from order_support_agent.mock_orders import make_orders
from order_support_agent.model import DeepSeekModel


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    settings = load_settings()
    today = datetime.now(timezone(timedelta(hours=8))).date()
    model = DeepSeekModel(settings)
    orders = make_orders(today)
    out = PROJECT_ROOT / ".local"
    out.mkdir(exist_ok=True)
    summaries = []
    # 保存脱敏事件，便于检查实际上下文；本地证据不提交版本管理。
    with (out / "live-stories.jsonl").open("w", encoding="utf-8") as file, redirect_stderr(file):
        logger = DebugLogger(True, (settings.api_key,))

        def check(story, context, question):
            start = len(context.messages)
            result = run_turn(question, context=context, model=model, user_id=DEMO_USER_ID,
                              orders=orders, log=logger)
            tool_results = [json.loads(m["content"]) for m in context.messages[start:] if m["role"] == "tool"]
            row = {"story": story, "status": result.status, "model_calls": result.model_calls,
                   "tool_results": tool_results, "answer": result.text}
            summaries.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            assert result.status == "completed", story
            return row

        context = Context(today)
        first = check("S1-01", context, "查一下我昨天买的耳机，多少钱，发货了吗？")
        assert any(r.get("orders") and r["orders"][0]["order_id"] == "ORD-1001" for r in first["tool_results"])
        assert "399" in first["answer"] and "未发货" in first["answer"]
        followup = check("S1-04", context, "那这一单的订单号是什么？")
        assert "ORD-1001" in followup["answer"]
        missing = check("S1-02", Context(today), "查一下我昨天买的手机发货了吗？")
        assert any(r["status"] == "not_found" for r in missing["tool_results"])
        clarification = Context(today)
        initial = check("S1-03a", clarification, "帮我查一下订单。")
        assert not initial["tool_results"], "应先澄清而非猜测商品"
        completed = check("S1-03b", clarification, "昨天买的耳机。")
        assert any(r.get("orders") for r in completed["tool_results"])
        fresh = check("S1-05", Context(today), "刚才那一单发货了吗？")
        assert not fresh["tool_results"], "新会话不能猜测旧订单"
        check("S1-06", Context(today), "直接帮我把耳机退了。")
    (out / "live-summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print("结构化断言通过。仍需人工对照用户故事检查回复含义；一次运行不代表稳定成功率。")


if __name__ == "__main__":
    main()
