"""用固定响应验证执行边界；不把离线测试冒充真实模型验收。"""

from contextlib import redirect_stderr
from datetime import date
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from order_support_agent.config import DEMO_USER_ID, Settings, load_settings
from order_support_agent.context import Context
from order_support_agent.debug import DebugLogger
from order_support_agent.loop import run_turn
from order_support_agent.mock_orders import make_orders
from order_support_agent.model import DeepSeekModel, ModelError
from order_support_agent.tools import dispatch_tool


def call(arguments='{"product_name":"耳机"}', name="query_orders", call_id="c1"):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def request_tool(tool=None):
    return {"role": "assistant", "content": None, "tool_calls": [tool or call()]}


class ScriptedModel:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []

    def complete(self, messages, tools):
        self.requests.append(messages)
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.context = Context(date(2026, 10, 7))
        self.orders = make_orders(date(2026, 10, 7))

    def run_agent(self, model, query="查一下耳机", **kwargs):
        return run_turn(query, context=self.context, model=model,
                        user_id=DEMO_USER_ID, orders=self.orders, **kwargs)

    def dispatch(self, tool):
        return dispatch_tool(tool, user_id=DEMO_USER_ID, orders=self.orders)

    def test_tool_result_reaches_next_request(self):
        model = ScriptedModel([request_tool(), {"role": "assistant", "content": "未发货，399 元"}])
        result = self.run_agent(model)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.model_calls, 2)
        second = model.requests[1]
        self.assertEqual(second[-2]["tool_calls"][0]["id"], second[-1]["tool_call_id"])
        data = json.loads(second[-1]["content"])
        self.assertEqual([x["order_id"] for x in data["orders"]], ["ORD-1001"])
        self.assertEqual(data["orders"][0]["amount_cents"], 39900)
        self.assertEqual(len(model.requests[0]), 2)  # 第一次快照没有被后续追加污染。

    def test_not_found_and_date_filter(self):
        for args in ['{"product_name":"手机"}', '{"product_name":"耳机","purchased_on":"2020-01-01"}']:
            with self.subTest(args=args):
                self.assertEqual(self.dispatch(call(args)), {"status": "not_found", "orders": []})

    def test_identity_filter_and_no_identity_in_output(self):
        result = self.dispatch(call())
        self.assertEqual(len(result["orders"]), 1)
        self.assertNotIn("user_id", result["orders"][0])
        self.assertNotIn("ORD-2001", json.dumps(result))

    def test_invalid_arguments_and_unknown_tool(self):
        for args in ['{', '[]', '{}', '{"product_name":123}', '{"product_name":" "}',
                     '{"product_name":"耳机","user_id":"demo-user-002"}',
                     '{"product_name":"耳机","purchased_on":null}',
                     '{"product_name":"耳机","purchased_on":"2026-02-30"}']:
            with self.subTest(args=args):
                self.assertEqual(self.dispatch(call(args))["code"], "INVALID_ARGUMENTS")
        self.assertEqual(self.dispatch(call(name="submit_refund"))["code"], "UNKNOWN_TOOL")

    def test_error_is_returned_to_model_without_query_execution(self):
        model = ScriptedModel([request_tool(call('{')), {"role": "assistant", "content": "参数错误"}])
        with patch("order_support_agent.tools.query_orders") as query:
            self.run_agent(model)
            query.assert_not_called()
        self.assertEqual(json.loads(model.requests[1][-1]["content"])["code"], "INVALID_ARGUMENTS")

    def test_budget_stops_at_six_with_matched_results(self):
        model = ScriptedModel([request_tool(call(call_id=f"c{i}")) for i in range(6)])
        result = self.run_agent(model)
        self.assertEqual(result.status, "budget_exhausted")
        self.assertEqual(len(model.requests), 6)
        self.assertEqual(len([m for m in self.context.messages if m["role"] == "tool"]), 6)

    def test_multiple_calls_paired_before_next_request(self):
        reply = request_tool()
        reply["tool_calls"].append(call('{"product_name":"手机"}', call_id="c2"))
        model = ScriptedModel([reply, {"role": "assistant", "content": "查询完成"}])
        self.run_agent(model)
        self.assertEqual([m["tool_call_id"] for m in model.requests[1] if m["role"] == "tool"], ["c1", "c2"])

    def test_same_session_and_new_session(self):
        self.run_agent(ScriptedModel([{"role": "assistant", "content": "请问是什么商品？"}]), "查订单")
        model = ScriptedModel([request_tool(), {"role": "assistant", "content": "未发货"}])
        self.run_agent(model, "耳机")
        self.assertIn("请问是什么商品？", str(model.requests[0]))
        self.assertEqual(len(Context(date(2026, 10, 7)).messages), 1)

    def test_model_failure_does_not_execute_tool(self):
        with patch("order_support_agent.loop.dispatch_tool") as dispatch:
            result = self.run_agent(ScriptedModel([ModelError("连接失败")]))
            self.assertEqual(result.status, "model_error")
            dispatch.assert_not_called()

    def test_malformed_call_does_not_execute(self):
        bad = request_tool()
        del bad["tool_calls"][0]["id"]
        with patch("order_support_agent.loop.dispatch_tool") as dispatch:
            self.assertEqual(self.run_agent(ScriptedModel([bad])).status, "model_error")
            dispatch.assert_not_called()

    def test_empty_input_does_not_request_model(self):
        model = ScriptedModel([])
        self.assertEqual(self.run_agent(model, " ").model_calls, 0)
        self.assertFalse(model.requests)

    def test_missing_config_and_env_precedence(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            env = Path(directory) / ".env"
            with self.assertRaisesRegex(ValueError, "缺少 DEEPSEEK_API_KEY"):
                load_settings(env)
            env.write_text("DEEPSEEK_API_KEY=local-test-value\n", encoding="utf-8")
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "environment-test-value"}):
                settings = load_settings(env)
                self.assertEqual(settings.api_key, "environment-test-value")
                self.assertNotIn(settings.api_key, repr(settings))

    def test_debug_redacts_secrets(self):
        output = io.StringIO()
        with redirect_stderr(output):
            DebugLogger(True, ("private-test-value",))("test", {"text": "private-test-value sk-example-secret"})
        self.assertNotIn("private-test-value", output.getvalue())
        self.assertNotIn("sk-example-secret", output.getvalue())

    def test_truncated_provider_response_is_rejected(self):
        body = {"choices": [{"finish_reason": "length", "message": request_tool()}]}
        response = io.BytesIO(json.dumps(body).encode())
        with patch("order_support_agent.model.urlopen", return_value=response):
            with self.assertRaisesRegex(ModelError, "未完整结束"):
                DeepSeekModel(Settings(api_key="test-only")).complete([], [])


if __name__ == "__main__":
    unittest.main()
