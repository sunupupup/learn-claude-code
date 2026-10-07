"""进程内模拟订单数据；后续可替换为独立业务服务。"""

from datetime import date, timedelta

from .config import DEMO_USER_ID


def make_orders(today: date) -> list[dict]:
    yesterday = (today - timedelta(days=1)).isoformat()
    return [
        {
            "order_id": "ORD-1001", "user_id": DEMO_USER_ID,
            "product_name": "白色无线耳机", "purchased_on": yesterday,
            "status": "未发货", "amount_cents": 39900, "currency": "CNY",
        },
        # 保留另一用户的样本，用于证明身份过滤确实生效；当前用户仍只有一单。
        {
            "order_id": "ORD-2001", "user_id": "demo-user-002",
            "product_name": "黑色无线耳机", "purchased_on": yesterday,
            "status": "已发货", "amount_cents": 29900, "currency": "CNY",
        },
    ]


def query_orders(orders: list[dict], *, user_id: str,
                 product_name: str, purchased_on: str | None = None) -> list[dict]:
    # 先限定归属，再筛选商品；不要先把其他用户订单交给模型判断权限。
    return [
        {key: value for key, value in order.items() if key not in ("user_id", "aliases")}
        for order in orders
        if order["user_id"] == user_id
        and any(product_name.casefold() in name.casefold()
                for name in [order["product_name"], *order.get("aliases", [])])
        and (purchased_on is None or order["purchased_on"] == purchased_on)
    ]
