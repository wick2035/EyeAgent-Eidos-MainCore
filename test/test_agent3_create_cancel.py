"""
测试Agent3新增和取消提醒功能
"""
from datetime import datetime, timedelta
from agents.agent_3 import ReminderAgent


def test_create_follow_up_reminder():
    """测试创建复诊提醒的完整流程"""
    print("\n" + "="*60)
    print("测试1: 创建复诊提醒")
    print("="*60)

    agent = ReminderAgent(patient_id=1, role="patient")

    # 模拟对话流程
    conversations = [
        "创建复诊提醒",
        "2025-12-15",  # 输入日期
        "3",  # 提前3天提醒
    ]

    for msg in conversations:
        print(f"\n用户: {msg}")
        response, is_completed = agent.chat(msg)
        print(f"Agent: {response}")
        print(f"当前阶段: {agent.stage.value}")


def test_create_appointment_reminder():
    """测试创建预约提醒的完整流程"""
    print("\n" + "="*60)
    print("测试2: 创建预约提醒")
    print("="*60)

    agent = ReminderAgent(patient_id=1, role="patient")

    # 模拟对话流程
    conversations = [
        "创建预约提醒",
        "明天下午2点",  # 使用相对时间
        "1",  # 提前1天提醒
    ]

    for msg in conversations:
        print(f"\n用户: {msg}")
        response, is_completed = agent.chat(msg)
        print(f"Agent: {response}")
        print(f"当前阶段: {agent.stage.value}")


def test_create_medication_reminder():
    """测试创建用药提醒的完整流程"""
    print("\n" + "="*60)
    print("测试3: 创建用药提醒")
    print("="*60)

    agent = ReminderAgent(patient_id=1, role="patient")

    # 模拟对话流程
    conversations = [
        "创建用药提醒",
        "玻璃酸钠滴眼液",  # 药物名称
        "每日3次，每次1-2滴",  # 用法用量
        "7",  # 疗程天数
    ]

    for msg in conversations:
        print(f"\n用户: {msg}")
        response, is_completed = agent.chat(msg)
        print(f"Agent: {response}")
        print(f"当前阶段: {agent.stage.value}")


def test_cancel_reminder():
    """测试取消提醒功能"""
    print("\n" + "="*60)
    print("测试4: 取消提醒")
    print("="*60)

    agent = ReminderAgent(patient_id=1, role="patient")

    # 先查看提醒列表
    print("\n用户: 查看提醒")
    response, _ = agent.chat("查看提醒")
    print(f"Agent: {response}")

    # 测试取消提醒（不带ID）
    print("\n用户: 取消提醒")
    response, _ = agent.chat("取消提醒")
    print(f"Agent: {response}")

    # 测试取消提醒（带ID，需要根据实际情况调整ID）
    # print("\n用户: 取消提醒 ID:1")
    # response, _ = agent.chat("取消提醒 ID:1")
    # print(f"Agent: {response}")


def test_date_parsing():
    """测试日期解析功能"""
    print("\n" + "="*60)
    print("测试5: 日期解析")
    print("="*60)

    agent = ReminderAgent(patient_id=1, role="patient")

    test_dates = [
        "明天",
        "后天",
        "2025-12-01",
        "12-25",
        "明天下午3点",
        "今天14:30",
    ]

    for date_text in test_dates:
        parsed = agent._parse_datetime(date_text)
        print(f"{date_text:20s} -> {parsed}")


def test_cancel_workflow():
    """测试取消创建提醒的流程"""
    print("\n" + "="*60)
    print("测试6: 取消创建提醒")
    print("="*60)

    agent = ReminderAgent(patient_id=1, role="patient")

    conversations = [
        "创建复诊提醒",
        "取消",  # 中途取消
    ]

    for msg in conversations:
        print(f"\n用户: {msg}")
        response, is_completed = agent.chat(msg)
        print(f"Agent: {response}")
        print(f"当前阶段: {agent.stage.value}")


def test_multiple_reminder_types():
    """测试创建多种类型的提醒"""
    print("\n" + "="*60)
    print("测试7: 创建多种类型提醒")
    print("="*60)

    agent = ReminderAgent(patient_id=1, role="patient")

    # 查看初始提醒列表
    print("\n--- 初始状态 ---")
    summary = agent.get_summary()
    print(f"总提醒数: {summary['total_reminders']}")
    print(f"待处理: {summary['pending_reminders']}")

    # 创建复诊提醒
    print("\n--- 创建复诊提醒 ---")
    agent.chat("创建复诊提醒")
    agent.chat("2025-12-20")
    response, _ = agent.chat("2")
    print(response)

    # 创建用药提醒
    print("\n--- 创建用药提醒 ---")
    agent.chat("创建用药提醒")
    agent.chat("阿托品滴眼液")
    agent.chat("睡前一次，每次1滴")
    response, _ = agent.chat("14")
    print(response)

    # 查看最终提醒列表
    print("\n--- 最终状态 ---")
    summary = agent.get_summary()
    print(f"总提醒数: {summary['total_reminders']}")
    print(f"待处理: {summary['pending_reminders']}")

    response, _ = agent.chat("查看待处理提醒")
    print(f"\n{response}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Agent3 新增和取消提醒功能测试")
    print("="*60)

    try:
        # 基础功能测试
        test_date_parsing()

        # 创建提醒测试
        test_create_follow_up_reminder()
        test_create_appointment_reminder()
        test_create_medication_reminder()

        # 取消提醒测试
        test_cancel_reminder()
        test_cancel_workflow()

        # 综合测试
        test_multiple_reminder_types()

        print("\n" + "="*60)
        print("所有测试完成！")
        print("="*60)

    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback
        traceback.print_exc()
