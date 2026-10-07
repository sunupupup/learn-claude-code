"""验证真正的副作用边界、HTTP 确认流程和流式截断，不依赖模型恰好听话。"""

from datetime import date
import io
import json
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from order_support_agent.business import Session
from order_support_agent.config import Settings
from order_support_agent.model import ModelError, read_stream
from order_support_agent.server import AppServer


def tool(name, **args):
    return {"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(date(2026, 10, 7))
        self.events = []

    def send(self, event, data):
        self.events.append((event, data))

    def dispatch(self, name, **args):
        return self.session.dispatch(tool(name, **args), self.send)

    def prepare(self, action="refund"):
        self.dispatch("query_orders", product_name="白色")
        self.dispatch("query_rules", order_id="ORD-1001")
        result = self.dispatch("request_action_confirmation", order_id="ORD-1001", action=action, reason="不需要了")
        return result["operation_id"]

    def test_multiple_orders_must_be_selected(self):
        result = self.dispatch("query_orders", product_name="耳机")
        self.assertEqual(result["status"], "waiting_selection")
        self.assertEqual(self.dispatch("get_logistics", order_id="ORD-1001")["code"], "ORDER_NOT_SELECTED")
        with self.assertRaises(ValueError):
            self.session.select("ORD-2001", self.send)
        self.session.select("ORD-1002", self.send)
        self.assertEqual(self.dispatch("get_logistics", order_id="ORD-1002")["estimated_arrival"], "2026-10-10T18:00:00+08:00")

    def test_color_alias_selects_unique_order_without_extra_confirmation(self):
        result = self.dispatch("query_orders", product_name="白色耳机")
        self.assertEqual(result["selected_order_id"], "ORD-1001")
        self.assertFalse(self.session.candidates)
        self.assertEqual(len(result["orders"]), 1)

    def test_refund_only_after_explicit_confirmation_and_replay(self):
        operation_id = self.prepare()
        self.assertEqual(self.session.order("ORD-1001")["status"], "未发货")
        self.assertNotIn("application_id", self.session.operations[operation_id])
        result = self.session.decide(operation_id, True, self.send)
        replay = self.session.decide(operation_id, True, self.send)
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["application_id"], replay["application_id"])
        self.assertEqual(self.session.order("ORD-1001")["status"], "退款申请处理中")
        self.assertEqual(len([x for x in self.session.items if x["kind"] == "notice"]), 1)

    def test_cancellation_cannot_later_be_confirmed(self):
        op = self.prepare()
        self.session.decide(op, False, self.send)
        self.assertEqual(self.session.decide(op, True, self.send)["status"], "cancelled")
        self.assertEqual(self.session.order("ORD-1001")["status"], "未发货")

    def test_changed_amount_invalidates_confirmation(self):
        op = self.prepare()
        self.session.order("ORD-1001")["amount_cents"] = 99900
        self.assertEqual(self.session.decide(op, True, self.send)["status"], "invalidated")
        self.assertNotIn("application_id", self.session.operations[op])

    def test_unknown_eta_and_missing_rules(self):
        self.dispatch("query_orders", product_name="充电线")
        self.assertIsNone(self.dispatch("get_logistics", order_id="ORD-1003")["estimated_arrival"])
        self.dispatch("query_orders", product_name="定制键帽")
        self.assertEqual(self.dispatch("query_rules", order_id="ORD-1004")["status"], "manual_required")
        self.assertEqual(self.dispatch("request_action_confirmation", order_id="ORD-1004", action="refund", reason="退款")["code"], "RULES_REQUIRED")

    def test_foreign_order_and_model_supplied_amount_rejected(self):
        self.assertEqual(self.dispatch("get_logistics", order_id="ORD-2001")["code"], "ORDER_UNAVAILABLE")
        self.dispatch("query_orders", product_name="白色")
        self.assertEqual(self.dispatch("request_action_confirmation", order_id="ORD-1001", action="refund", reason="退款", amount_cents=1)["code"], "INVALID_ARGUMENTS")

    def test_expedite_is_confirmed_without_changing_shipping_status(self):
        op = self.prepare("expedite")
        result = self.session.decide(op, True, self.send)
        self.assertTrue(result["application_id"].startswith("EX-"))
        self.assertEqual(self.session.order("ORD-1001")["status"], "未发货")


class StreamTests(unittest.TestCase):
    def frame(self, delta, finish=None):
        return ("data: " + json.dumps({"choices": [{"delta": delta, "finish_reason": finish}]}) + "\n\n").encode()

    def test_fragmented_arguments_and_text(self):
        data = self.frame({"content": "查询"}) + self.frame({"content": "订单"})
        data += self.frame({"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "query_orders", "arguments": '{"product_'}}]})
        data += self.frame({"tool_calls": [{"index": 0, "function": {"arguments": 'name":"耳机"}'}}]}, "tool_calls")
        data += b"data: [DONE]\n\n"
        chunks = []
        result = read_stream(io.BytesIO(data), chunks.append)
        self.assertEqual(chunks, ["查询", "订单"])
        self.assertEqual(json.loads(result["tool_calls"][0]["function"]["arguments"]), {"product_name": "耳机"})

    def test_valid_json_tool_call_without_stream_end_is_not_executable(self):
        data = self.frame({"tool_calls": [{"index": 0, **tool("query_orders", product_name="耳机")}]}, "tool_calls")
        with self.assertRaises(ModelError):
            read_stream(io.BytesIO(data), lambda text: None)


class FakeStreamModel:
    def __init__(self):
        self.calls = 0

    def complete_stream(self, messages, tools, on_delta):
        self.calls += 1
        on_delta("正在查询。")
        if self.calls == 1:
            request = tool("query_orders", product_name="白色")
        elif self.calls == 2:
            request = tool("query_rules", order_id="ORD-1001")
        else:
            request = tool("request_action_confirmation", order_id="ORD-1001", action="refund", reason="用户要求")
        return {"role": "assistant", "content": "正在查询。", "tool_calls": [request]}


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.server = AppServer(("127.0.0.1", 0), FakeStreamModel(), Settings(api_key="test-only"))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.sid = json.loads(self.post("/api/sessions", {}))["id"]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def post(self, path, data, **headers):
        req = Request(self.base + path, data=json.dumps(data).encode(), headers={"Content-Type": "application/json", "X-Agent-Client": "web", **headers})
        with urlopen(req, timeout=3) as response:
            return response.read().decode()

    def test_stream_confirmation_cancel_and_next_request(self):
        stream = self.post(f"/api/sessions/{self.sid}/messages", {"text": "我要退款"})
        self.assertIn("event: delta", stream)
        self.assertIn("event: done", stream)
        session = self.server.sessions[self.sid]
        operation = session.pending
        with self.assertRaises(HTTPError) as exc:
            self.post(f"/api/sessions/{self.sid}/decide", {"operation_id": operation, "approved": "true"})
        self.assertEqual(exc.exception.code, 400)
        state = json.loads(self.post(f"/api/sessions/{self.sid}/decide", {"operation_id": operation, "approved": False}))
        self.assertIsNone(state["pending"])
        # 回归：确认接口必须释放会话锁，下一次消息不能永远返回 409。
        next_stream = self.post(f"/api/sessions/{self.sid}/messages", {"text": "重新申请"})
        self.assertIn("event: done", next_stream)

    def test_cross_session_operation_cannot_be_confirmed(self):
        self.post(f"/api/sessions/{self.sid}/messages", {"text": "我要退款"})
        other = json.loads(self.post("/api/sessions", {}))["id"]
        with self.assertRaises(HTTPError):
            self.post(f"/api/sessions/{other}/decide", {"operation_id": self.server.sessions[self.sid].pending, "approved": True})
        self.assertEqual(self.server.sessions[self.sid].order("ORD-1001")["status"], "未发货")

    def test_concurrent_request_is_rejected(self):
        session = self.server.sessions[self.sid]
        session.lock.acquire()
        try:
            with self.assertRaises(HTTPError) as exc:
                self.post(f"/api/sessions/{self.sid}/messages", {"text": "查询"})
            self.assertEqual(exc.exception.code, 409)
        finally:
            session.lock.release()

    def test_external_origin_and_secret_file_not_exposed(self):
        with self.assertRaises(HTTPError):
            self.post("/api/sessions", {}, Origin="https://external.example")
        with self.assertRaises(HTTPError) as exc:
            urlopen(self.base + "/.env")
        self.assertEqual(exc.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
