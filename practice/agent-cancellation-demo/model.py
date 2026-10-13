"""真实 DeepSeek 调用；复用仓库已有客户端，但配置与本项目运行独立。"""

import sys
from pathlib import Path


def load_model():
    # 复用已验证的非流式 Chat Completions 客户端，不复制供应商协议处理代码。
    sibling = Path(__file__).resolve().parent.parent / 'order-support-agent'
    sys.path.insert(0, str(sibling))
    from order_support_agent.config import load_settings
    from order_support_agent.model import DeepSeekModel

    # 优先本项目 .env；没有时复用订单客服的本地配置。环境变量始终优先。
    # 只读取配置，不打印、不复制密钥到代码、Trace 或仓库。
    local = Path(__file__).resolve().parent / '.env'
    return DeepSeekModel(load_settings(local if local.exists() else sibling / '.env'))


class ScriptedModel:
    """仅供 --offline 验证：明确模拟模型，不能冒充真实模型运行。"""

    def complete(self, messages, tools):
        results = [message for message in messages if message['role'] == 'tool']
        if len(results) >= 2:
            return {'role': 'assistant', 'content': '预约工具已返回结果。'}
        name = 'search_slots' if not results else 'create_booking'
        arguments = {} if not results else {'slot': '周三 10:00'}
        import json
        return {'role': 'assistant', 'content': None, 'tool_calls': [{
            'id': f'call-{len(results)}', 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(arguments, ensure_ascii=False)},
        }]}
