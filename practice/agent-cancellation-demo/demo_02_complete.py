"""基本预约 Agent：真实模型—工具循环，以及取消、Hook 补偿和持久化恢复。"""

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path

from model import ScriptedModel, load_model


# ==================== 【模型可见的工具定义】 ====================
# tools 是请求模型时传入的声明；实际执行由下面的 execute_tool() 完成。
TOOLS = [
    {'type': 'function', 'function': {
        'name': 'search_slots', 'description': '查询可预约时间，创建前必须先查询。',
        'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False},
    }},
    {'type': 'function', 'function': {
        'name': 'create_booking', 'description': '为用户创建已经确认时间的预约。',
        'parameters': {'type': 'object', 'properties': {'slot': {'type': 'string'}},
                       'required': ['slot'], 'additionalProperties': False},
    }},
]


UI = {
    'BOOKING': '正在创建预约',
    'BOOKED': '预约成功',
    'CANCEL_REQUESTED': '正在确认取消结果',
    'COMPENSATING': '正在撤销预约',
    'CANCEL_FAILED': '取消结果未确认，需要重试或人工处理',
    'CANCELLED': '已取消',
}


def trace(operation_id, event, **details):
    # 所有事件带同一个 operation_id，把工作流状态与外部预约事实串起来。
    print(json.dumps(dict(operation_id=operation_id, event=event, **details), ensure_ascii=False))


class ExternalSystem:
    """独立数据库代表外部系统；Harness 丢失对象不会撤回已经发出的请求。"""

    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('''CREATE TABLE IF NOT EXISTS bookings (
            operation_id TEXT PRIMARY KEY, status TEXT,
            create_effects INTEGER, cancel_effects INTEGER, reminders INTEGER)''')
        self.db.commit()
        # 【模拟补偿失败 / 响应丢失】只用于故障注入，不是业务状态。
        self.fail_next_cancel = False
        self.lose_next_cancel_response = False

    def search_slots(self):
        return ['周三 10:00']

    def create_booking(self, operation_id):
        # 同一操作 ID 重复提交不重复创建；先记录 PENDING，稍后手动完成请求。
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO bookings VALUES (?, ?, 0, 0, 0)',
                            (operation_id, 'PENDING'))
        trace(operation_id, 'create_booking.sent')

    def finish_create(self, operation_id, success=True):
        # 【模拟外部执行完成】即使用户停止了 Agent，外部系统也会继续执行。
        with self.db:
            self.db.execute('''UPDATE bookings SET status=?, create_effects=?, reminders=?
                WHERE operation_id=? AND status='PENDING' ''',
                ('ACTIVE' if success else 'FAILED', int(success), int(success), operation_id))
        trace(operation_id, 'external.create_finished', **self.query(operation_id))

    def query(self, operation_id):
        row = self.db.execute('SELECT status, create_effects, cancel_effects, reminders '
                              'FROM bookings WHERE operation_id=?', (operation_id,)).fetchone()
        if row is None:
            # 查不到记录不等于请求永远不会到达；不能据此直接确认取消。
            return dict(status='UNKNOWN', create_effects=0, cancel_effects=0, reminders=0)
        return dict(zip(('status', 'create_effects', 'cancel_effects', 'reminders'), row))

    def cancel_booking(self, operation_id):
        if self.fail_next_cancel:
            self.fail_next_cancel = False
            raise RuntimeError('模拟撤销失败，预约仍有效')
        # 【幂等补偿】只有 ACTIVE -> CANCELLED 才增加副作用计数。
        # 同一 operation_id 反复撤销，最终仍然只撤销一次。
        with self.db:
            self.db.execute("UPDATE bookings SET status='CANCELLED', cancel_effects=cancel_effects+1 "
                            "WHERE operation_id=? AND status='ACTIVE'", (operation_id,))
        trace(operation_id, 'external.cancel_applied', **self.query(operation_id))
        if self.lose_next_cancel_response:
            self.lose_next_cancel_response = False
            raise RuntimeError('模拟撤销已生效，但响应丢失')

    def close(self):
        self.db.close()


class Harness:
    """运行协调层：保存取消意图，根据外部事实决定工作流及界面状态。"""

    def __init__(self, path, external):
        self.external = external
        self.db = sqlite3.connect(path)
        self.db.execute('''CREATE TABLE IF NOT EXISTS operations (
            operation_id TEXT PRIMARY KEY, state TEXT, cancel_requested INTEGER)''')
        self.db.commit()

    def read(self, operation_id):
        return self.db.execute('SELECT state, cancel_requested FROM operations WHERE operation_id=?',
                               (operation_id,)).fetchone()

    def set_state(self, operation_id, state):
        before, _ = self.read(operation_id)
        with self.db:
            self.db.execute('UPDATE operations SET state=? WHERE operation_id=?', (state, operation_id))
        trace(operation_id, 'workflow.state', before=before, after=state, ui=UI[state])

    def start(self, operation_id):
        # 发出副作用请求前持久化操作 ID；本 Demo 只演示单执行者。
        with self.db:
            self.db.execute('INSERT INTO operations VALUES (?, ?, 0)', (operation_id, 'BOOKING'))
        self.external.create_booking(operation_id)

    def request_cancel(self, operation_id):
        # 【取消意图】模拟点击停止：先落盘，才向界面报告“正在确认”。
        # 重复停止不能把已经确认的 CANCELLED 降回等待状态。
        with self.db:
            self.db.execute('UPDATE operations SET cancel_requested=1 WHERE operation_id=?', (operation_id,))
        if self.read(operation_id)[0] != 'CANCELLED':
            self.set_state(operation_id, 'CANCEL_REQUESTED')

    # ==================== 【Hook 补偿入口】 ====================
    def tool_result_hook(self, operation_id):
        # 工具结果回来后读取持久取消意图；模型停止后，这段业务协调仍需运行。
        # Hook 只触发统一处理，避免和恢复代码维护两套补偿规则。
        trace(operation_id, 'hook.tool_result')
        self.reconcile(operation_id)

    # ==================== 【Hook / 恢复共用的补偿逻辑】 ====================
    def reconcile(self, operation_id):
        state, cancel_requested = self.read(operation_id)
        if state == 'CANCELLED':
            trace(operation_id, 'reconcile.already_cancelled')
            return
        result = self.external.query(operation_id)
        trace(operation_id, 'reconcile.query', **result)
        if not cancel_requested:
            if result['status'] == 'ACTIVE':
                self.set_state(operation_id, 'BOOKED')
            return
        if result['status'] in ('PENDING', 'UNKNOWN'):
            # 请求还没完成 / 无法确认；保留取消意图，之后继续查询。
            self.set_state(operation_id, 'CANCEL_REQUESTED')
            return
        if result['status'] in ('FAILED', 'CANCELLED'):
            # FAILED 是外部确认创建最终失败；CANCELLED 是外部确认撤销成功。
            self.set_state(operation_id, 'CANCELLED')
            return
        self.set_state(operation_id, 'COMPENSATING')
        try:
            self.external.cancel_booking(operation_id)
        except RuntimeError as error:
            # 【重试保留点】不清除取消意图，不误报已取消；下一次恢复继续核对事实。
            trace(operation_id, 'compensation.error', error=str(error))
            self.set_state(operation_id, 'CANCEL_FAILED')
            return
        # 成功调用后仍核对业务结果；实际接口若异步撤销，应保持等待确认。
        result = self.external.query(operation_id)
        self.set_state(operation_id, 'CANCELLED' if result['status'] == 'CANCELLED' else 'COMPENSATING')

    # ==================== 【恢复与重试入口】 ====================
    def recover(self):
        # 模拟后台扫描：重启后从 SQLite 找回待处理操作，无需旧 Hook 或内存变量。
        # CANCEL_FAILED 也进入扫描，实现重试；教学版手动触发，不启用定时线程。
        rows = self.db.execute("SELECT operation_id FROM operations WHERE cancel_requested=1 "
                               "AND state IN ('CANCEL_REQUESTED', 'COMPENSATING', 'CANCEL_FAILED')").fetchall()
        for (operation_id,) in rows:
            trace(operation_id, 'recovery.retry_or_resume')
            self.reconcile(operation_id)

    def close(self):
        self.db.close()


SCENARIOS = ('normal', 'hook', 'recovery', 'retry', 'pending', 'create_failed', 'response_lost')


# ==================== 【工具执行：接收模型的 tool_call】 ====================
def execute_tool(call, harness, operation_id, scenario, control):
    name = call['function']['name']
    arguments = json.loads(call['function']['arguments'])
    if not isinstance(arguments, dict):
        raise ValueError('工具参数必须是对象')
    if name == 'search_slots' and not arguments:
        control['slots'] = harness.external.search_slots()
        return {'slots': control['slots']}
    if name != 'create_booking':
        raise ValueError('未知工具或参数无效')
    if set(arguments) != {'slot'} or arguments['slot'] not in control['slots']:
        raise ValueError('必须先查询，并选择已确认的周三 10:00')
    # 模型不能更改可信操作 ID；重复工具调用复用已存在的业务记录。
    if harness.read(operation_id):
        return harness.external.query(operation_id)
    harness.start(operation_id)

    # 【模拟打断：直接赋值】请求已发出、工具尚未完成时，模拟用户停止。
    user_clicked_stop = scenario != 'normal'
    if user_clicked_stop:
        control['stop_requested'] = True
        harness.request_cancel(operation_id)
        assert harness.read(operation_id)[0] == 'CANCEL_REQUESTED'
    if scenario == 'pending':
        harness.recover()
        assert harness.read(operation_id)[0] == 'CANCEL_REQUESTED'

    # 已发出的外部操作仍完成；停止模型循环不能撤回这个副作用。
    harness.external.finish_create(operation_id, success=scenario != 'create_failed')
    result = harness.external.query(operation_id)
    # 【模拟 Hook 未运行】工具完成后中断整个 Agent，由恢复入口重新加载数据。
    control['process_interrupted'] = scenario == 'recovery'
    if control['process_interrupted']:
        trace(operation_id, 'simulation.crash_before_hook')
        return result
    harness.external.fail_next_cancel = scenario == 'retry'
    harness.external.lose_next_cancel_response = scenario == 'response_lost'
    # 【Hook 补偿调用位置】工具实际执行完成后触发，即使用户停止也继续协调。
    harness.tool_result_hook(operation_id)
    return result


# ==================== 【真正的 Agent Loop 主入口】 ====================
def run_agent(model, harness, operation_id, scenario, max_steps=6):
    messages = [
        {'role': 'system', 'content': '你是预约助手。用户已确认周三 10:00。'
         '先调用 search_slots，再调用 create_booking，每轮只调用一个工具。'
         '创建结果返回后回答结果，不重复创建，不得凭空宣称成功。'},
        {'role': 'user', 'content': '请帮我预约周三 10:00，我确认这个时间。'},
    ]
    control = {'stop_requested': False, 'process_interrupted': False, 'slots': []}
    for step in range(1, max_steps + 1):
        # 1. 请求真实模型：messages 是对话历史，TOOLS 是顶层工具声明。
        trace(operation_id, 'model.request', step=step, message_count=len(messages))
        reply = model.complete(messages, TOOLS)
        messages.append(reply)
        calls = reply.get('tool_calls') or []
        trace(operation_id, 'model.response', step=step, tools=[c['function']['name'] for c in calls])
        # 2. 没有工具调用，模型已给出最终回答，结束循环。
        if not calls:
            print('[Agent]', reply.get('content'))
            return messages
        # 3. 按模型实际返回的工具名派发，不硬编码模型的选择顺序。
        for call in calls:
            trace(operation_id, 'tool.dispatch', tool=call['function']['name'], tool_call_id=call['id'])
            if control['stop_requested']:
                result = {'error': '用户已停止，不执行后续工具'}
            else:
                try:
                    result = execute_tool(call, harness, operation_id, scenario, control)
                except (ValueError, TypeError) as error:
                    result = {'error': str(error)}
            if control['process_interrupted']:
                return messages
            # 4. 工具结果回传：与 assistant.tool_calls 按 tool_call_id 一一配对。
            messages.append({'role': 'tool', 'tool_call_id': call['id'],
                             'content': json.dumps(result, ensure_ascii=False)})
            trace(operation_id, 'tool.result_appended', tool=call['function']['name'], result=result)
        # 【停止模型循环】补偿已执行，但不再请求下一轮模型或发出新的业务操作。
        if control['stop_requested']:
            trace(operation_id, 'agent.loop_stopped', model_calls=step)
            return messages
        # 5. 回到 for 顶部，把工具结果交给模型继续决策。
    raise RuntimeError('Agent 达到模型调用上限，未正常结束')


def run_scenario(scenario, model):
    print(f'\n===== 场景：{scenario} =====')
    # 每个场景独立数据库，重复运行不会串数据；退出后自动清理临时文件。
    with tempfile.TemporaryDirectory(prefix='agent-cancel-') as directory:
        external_path = Path(directory) / 'external.db'
        workflow_path = Path(directory) / 'workflow.db'
        external = ExternalSystem(external_path)
        harness = Harness(workflow_path, external)
        operation_id = f'booking-{scenario}'
        # 场景入口只组装环境；模型、工具调用与取消均发生在实际 Agent loop 中。
        run_agent(model, harness, operation_id, scenario)
        if not harness.read(operation_id):
            harness.close()
            external.close()
            raise RuntimeError('模型未创建预约，场景未复现，请查看 model.response')
        user_clicked_stop = scenario != 'normal'

        # 【模拟 Hook 未运行】外部创建完成后、Hook 前中断，重新打开两方数据库。
        process_interrupted = scenario == 'recovery'
        if process_interrupted:
            harness.close()
            external.close()
            external = ExternalSystem(external_path)
            harness = Harness(workflow_path, external)
            trace(operation_id, 'simulation.restart_from_sqlite')
            harness.recover()

        # 【模拟重试】第一次失败必须保留待处理状态；下一轮扫描重新查询后处理。
        if scenario in ('retry', 'response_lost'):
            assert harness.read(operation_id)[0] == 'CANCEL_FAILED'
            expected = 'ACTIVE' if scenario == 'retry' else 'CANCELLED'
            assert external.query(operation_id)['status'] == expected
            harness.close()
            harness = Harness(workflow_path, external)
            harness.recover()

        if user_clicked_stop:
            # 重复停止、重复 Hook、重复恢复和重复外部撤销都不得增加业务副作用。
            harness.request_cancel(operation_id)
            harness.tool_result_hook(operation_id)
            harness.recover()
            external.cancel_booking(operation_id)
            external.create_booking(operation_id)
            external.finish_create(operation_id)

        result = external.query(operation_id)
        expected_state = 'BOOKED' if scenario == 'normal' else 'CANCELLED'
        expected_status = 'ACTIVE' if scenario == 'normal' else (
            'FAILED' if scenario == 'create_failed' else 'CANCELLED')
        assert harness.read(operation_id)[0] == expected_state
        assert result['status'] == expected_status
        assert result['create_effects'] == int(scenario != 'create_failed')
        assert result['cancel_effects'] == int(user_clicked_stop and scenario != 'create_failed')
        # 补偿不会收回已发送提醒；这是与真正回滚的区别。
        assert result['reminders'] == result['create_effects']
        trace(operation_id, 'validation.passed', state=expected_state, **result)
        harness.close()
        external.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scenario', nargs='?', default='hook', choices=('all', *SCENARIOS))
    parser.add_argument('--offline', action='store_true', help='离线验证：使用脚本模型，不调用真实 LLM')
    args = parser.parse_args()
    model = ScriptedModel() if args.offline else load_model()
    for scenario in SCENARIOS if args.scenario == 'all' else (args.scenario,):
        run_scenario(scenario, model)
