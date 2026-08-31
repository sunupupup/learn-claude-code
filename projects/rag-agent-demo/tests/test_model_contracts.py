"""模型适配器、Tool Schema 和 Responses continuation 契约测试。"""

from __future__ import annotations

from types import SimpleNamespace
import unittest

from rag_agent_demo.contracts import ModelResponse, ToolCallRequest
from rag_agent_demo.model import OpenAIResponsesModel, ScriptedModel
from rag_agent_demo.tools import SearchKnowledgeTool


class FakeResponsesEndpoint:
    """不发网络请求的 Responses API endpoint 替身。"""

    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict] = []

    def create(self, **request):
        self.calls.append(request)
        return self.response


class FakeOpenAIClient:
    """只提供 responses.create 的最小 fake client。"""

    def __init__(self, response: object) -> None:
        self.responses = FakeResponsesEndpoint(response)


class ModelContractTests(unittest.TestCase):
    def test_search_tool_schema_is_strict_and_requires_query(self) -> None:
        # SDK Schema 能约束模型生成格式，但 execute() 仍会再次校验。
        schema = SearchKnowledgeTool.schema()
        self.assertEqual(schema["type"], "function")
        self.assertTrue(schema["strict"])
        self.assertIn("query", schema["parameters"]["required"])
        self.assertFalse(schema["parameters"]["additionalProperties"])

    def test_scripted_model_preserves_tool_call_contract(self) -> None:
        # 测试模型也必须返回内部统一的 ToolCallRequest。
        response = ModelResponse(
            kind="tool_call",
            tool_calls=(
                ToolCallRequest(
                    call_id="call-1",
                    name="search_knowledge",
                    arguments={"query": "RAG", "top_k": 3},
                ),
            ),
            response_id="response-1",
        )
        model = ScriptedModel([response])
        actual = model.respond(input="RAG", instructions="", tools=[])
        self.assertEqual(actual.tool_calls[0].name, "search_knowledge")
        self.assertEqual(model.calls[0]["input"], "RAG")

    def test_real_responses_adapter_parses_function_call(self) -> None:
        # 验证供应商 function_call item 会被归一化为 Harness 能理解的请求。
        response = SimpleNamespace(
            id="response-1",
            output=[
                SimpleNamespace(
                    type="function_call",
                    call_id="call-1",
                    name="search_knowledge",
                    arguments='{"query":"RAG","top_k":3}',
                )
            ],
            output_text="",
        )
        client = FakeOpenAIClient(response)
        model = OpenAIResponsesModel(client, "model-under-test")

        actual = model.respond(
            input="RAG 是什么？",
            instructions="必须检索",
            tools=[SearchKnowledgeTool.schema()],
            tool_choice={"type": "function", "name": "search_knowledge"},
        )

        self.assertEqual(actual.kind, "tool_call")
        self.assertEqual(actual.tool_calls[0].arguments["query"], "RAG")
        request = client.responses.calls[0]
        self.assertEqual(request["tool_choice"]["name"], "search_knowledge")

    def test_real_responses_adapter_sets_structured_continuation(self) -> None:
        # 验证 tool result 通过 previous_response_id 接回第二次模型调用，
        # 并使用 JSON Schema 约束最终输出。
        response = SimpleNamespace(
            id="response-2",
            output=[],
            output_text='{"answerable":false,"answer":"资料不足","sources":[]}',
        )
        client = FakeOpenAIClient(response)
        model = OpenAIResponsesModel(client, "model-under-test")

        actual = model.respond(
            input=[
                {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": "{\"matches\":[]}",
                }
            ],
            instructions="只输出 JSON",
            tools=[SearchKnowledgeTool.schema()],
            tool_choice="none",
            previous_response_id="response-1",
            output_schema={"type": "object"},
        )

        self.assertEqual(actual.kind, "final_text")
        request = client.responses.calls[0]
        self.assertEqual(request["previous_response_id"], "response-1")
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertTrue(request["text"]["format"]["strict"])


if __name__ == "__main__":
    unittest.main()
