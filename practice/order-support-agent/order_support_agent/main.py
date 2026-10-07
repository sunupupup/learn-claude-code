"""命令行入口：一问一答或进程内连续会话。"""

import argparse
from datetime import datetime, timedelta, timezone
import sys

from .config import DEMO_USER_ID, load_settings
from .context import Context
from .debug import DebugLogger
from .loop import run_turn
from .mock_orders import make_orders
from .model import DeepSeekModel


def main(argv: list[str] | None = None) -> int:
    # Windows 管道默认编码可能不是 UTF-8，显式设置以免中文日志重定向后乱码。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="订单客服 Agent（阶段 1：模拟订单查询）")
    parser.add_argument("--query", help="执行一次查询后退出；省略则进入交互模式")
    parser.add_argument("--debug", action="store_true", help="将脱敏模型消息与工具事件打印到 stderr")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
    except (ValueError, OSError) as exc:
        print(str(exc) if isinstance(exc, ValueError) else "无法读取本地配置文件。", file=sys.stderr)
        return 2
    today = datetime.now(timezone(timedelta(hours=8))).date()
    context = Context(today)
    orders = make_orders(today)
    model = DeepSeekModel(settings)
    log = DebugLogger(args.debug, (settings.api_key,))

    def answer(question: str) -> int:
        result = run_turn(question, context=context, model=model, user_id=DEMO_USER_ID,
                          orders=orders, max_model_calls=settings.max_model_calls, log=log)
        print(result.text)
        return 0 if result.status == "completed" else 1

    try:
        if args.query is not None:
            return answer(args.query)
        print("模拟订单查询，输入 exit 退出；退出后内存历史丢失。")
        while True:
            question = input("你：").strip()
            if question.lower() in ("exit", "quit"):
                return 0
            if question:
                answer(question)
    except (EOFError, KeyboardInterrupt):
        print("\n已退出。")
        return 0
