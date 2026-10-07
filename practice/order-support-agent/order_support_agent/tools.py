"""工具定义、参数校验和分发：模型只能提出请求，实际执行由程序控制。"""

from datetime import date
import json

from .mock_orders import query_orders

TOOL_DEFINITIONS = [{
    "type": "function",
    "function": {
        "name": "query_orders",
        "description": "查询当前登录用户的模拟订单，按商品关键词和可选购买日期筛选。",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "商品关键词，如耳机"},
                "purchased_on": {"type": "string", "description": "可选购买日期，YYYY-MM-DD"},
            },
            "required": ["product_name"],
            "additionalProperties": False,
        },
    },
}]


def error(code: str, message: str) -> dict:
    return {"status": "error", "code": code, "message": message}


def dispatch_tool(call: dict, *, user_id: str, orders: list[dict]) -> dict:
    function = call["function"]
    if function["name"] != "query_orders":
        return error("UNKNOWN_TOOL", "工具不存在；当前仅支持 query_orders。")
    try:
        args = json.loads(function["arguments"])
    except (json.JSONDecodeError, TypeError):
        return error("INVALID_ARGUMENTS", "工具参数必须是合法 JSON 对象。")
    # 即使给模型提供了 schema，也必须在执行前独立校验，不允许多余的身份字段。
    if not isinstance(args, dict) or set(args) - {"product_name", "purchased_on"}:
        return error("INVALID_ARGUMENTS", "仅允许 product_name 和 purchased_on，不接受身份参数。")
    product = args.get("product_name")
    if not isinstance(product, str) or not 1 <= len(product.strip()) <= 100:
        return error("INVALID_ARGUMENTS", "product_name 必须是 1～100 字的非空字符串。")
    purchased_on = args.get("purchased_on")
    if "purchased_on" in args:
        try:
            if not isinstance(purchased_on, str) or date.fromisoformat(purchased_on).isoformat() != purchased_on:
                raise ValueError
        except ValueError:
            return error("INVALID_ARGUMENTS", "purchased_on 必须是 YYYY-MM-DD 格式的有效日期。")
    found = query_orders(orders, user_id=user_id, product_name=product.strip(), purchased_on=purchased_on)
    return {"status": "ok" if found else "not_found", "orders": found}
