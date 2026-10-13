"""错误示例：停止 Agent 的显示状态，不能撤销已发出的业务请求。"""


def main():
    # 模型已经根据用户确认选择了 create_booking；这里固定工具调用，不接 LLM。
    request_sent = True
    booking_active = False
    print('[Trace] create_booking 已发出：周三 10:00')

    # 【模拟打断】直接赋值，代表工具执行期间用户点击停止。
    cancelled = True
    ui_text = '任务已取消' if cancelled else '正在创建预约'
    print(f'[界面] {ui_text}')

    # 模拟 500 毫秒后的业务完成；用顺序执行表达时间先后，无需真的等待。
    if request_sent:
        booking_active = True
        print('[外部系统] 创建成功，提醒已发送')

    assert cancelled and booking_active
    print('[验证] 界面显示已取消，但预约仍然有效：错误复现成功')


if __name__ == '__main__':
    main()
