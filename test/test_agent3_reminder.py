"""
测试Agent3提醒功能
"""
from datetime import datetime, timedelta
from agents.agent_3 import ReminderAgent
from database.reminder_service import ReminderService


def test_reminder_service():
    """测试提醒服务基本功能"""
    print("\n" + "="*60)
    print("测试1: 提醒服务基本功能")
    print("="*60)

    service = ReminderService()

    # 1. 创建复诊提醒
    print("\n1. 创建复诊提醒...")
    result = service.create_follow_up_reminder(
        patient_id=1,
        follow_up_date=datetime.now() + timedelta(days=7),
        advance_days=3,
        notes="请携带上次的检查报告"
    )
    print(f"结果: {result}")

    # 2. 创建用药提醒
    print("\n2. 创建用药提醒...")
    result = service.create_medication_reminder(
        patient_id=1,
        prescription_id=1,
        medication_name="玻璃酸钠滴眼液",
        dosage="每日3次，每次1-2滴",
        duration_days=7
    )
    print(f"结果: {result}")

    # 3. 查询患者的提醒列表
    print("\n3. 查询患者的提醒列表...")
    reminders = service.get_reminders_by_patient(patient_id=1)
    print(f"找到 {len(reminders)} 条提醒:")
    for r in reminders[:3]:  # 显示前3条
        print(f"  - [{r['Reminder_Type']}] {r['Reminder_Title']} - {r['Status']} - {r['Scheduled_Time']}")

    # 4. 查询待发送的提醒
    print("\n4. 查询待发送的提醒...")
    pending = service.get_pending_reminders()
    print(f"找到 {len(pending)} 条待发送提醒")

    # 5. 更新提醒状态
    if reminders:
        reminder_id = reminders[0]['Reminder_ID']
        print(f"\n5. 更新提醒状态 (ID: {reminder_id})...")
        result = service.update_reminder_status(
            reminder_id=reminder_id,
            status='sent',
            action_by='test'
        )
        print(f"结果: {result}")

    service.close()


def test_reminder_agent_basic():
    """测试提醒Agent基本对话"""
    print("\n" + "="*60)
    print("测试2: 提醒Agent基本对话")
    print("="*60)

    # 创建Agent（使用手机号）
    agent = ReminderAgent(phone_number="13900000001", role="patient")

    # 测试对话
    test_messages = [
        "你好",
        "查看我的提醒",
        "查看待处理提醒",
    ]

    for msg in test_messages:
        print(f"\n用户: {msg}")
        response, is_completed = agent.chat(msg)
        print(f"Agent: {response[:200]}...")
        print(f"完成状态: {is_completed}, 阶段: {agent.stage.value}")


def test_reminder_agent_commands():
    """测试提醒Agent命令功能"""
    print("\n" + "="*60)
    print("测试3: 提醒Agent命令功能")
    print("="*60)

    agent = ReminderAgent(patient_id=1, role="patient")

    # 测试各种命令
    test_commands = [
        "查看提醒",
        "查看待处理提醒",
        "创建复诊提醒",
        # 下一步需要用户输入具体信息，这里先测试命令识别
    ]

    for cmd in test_commands:
        print(f"\n用户命令: {cmd}")
        response, is_completed = agent.chat(cmd)
        print(f"Agent响应: {response[:150]}...")
        print(f"当前阶段: {agent.stage.value}")


def test_reminder_config():
    """测试提醒配置功能"""
    print("\n" + "="*60)
    print("测试4: 提醒配置功能")
    print("="*60)

    service = ReminderService()

    # 查询配置
    print("\n1. 查询患者配置...")
    config = service.get_reminder_config(patient_id=1)
    if config:
        print(f"配置信息:")
        print(f"  - 复诊提醒: {'启用' if config['Enable_Follow_Up'] else '禁用'}")
        print(f"  - 预约提醒: {'启用' if config['Enable_Appointment'] else '禁用'}")
        print(f"  - 用药提醒: {'启用' if config['Enable_Medication'] else '禁用'}")
        print(f"  - 提前天数: {config['Default_Advance_Days']} 天")

    # 更新配置
    print("\n2. 更新配置...")
    result = service.update_reminder_config(
        patient_id=1,
        enable_follow_up=True,
        enable_medication=True,
        default_advance_days=2
    )
    print(f"结果: {result}")

    service.close()


def test_agent_summary():
    """测试Agent摘要功能"""
    print("\n" + "="*60)
    print("测试5: Agent摘要功能")
    print("="*60)

    agent = ReminderAgent(patient_id=1, role="patient")

    # 进行一些对话
    agent.chat("你好")
    agent.chat("查看提醒")

    # 获取摘要
    summary = agent.get_summary()
    print("\nAgent对话摘要:")
    print(f"  - 患者ID: {summary['patient_id']}")
    print(f"  - 总提醒数: {summary['total_reminders']}")
    print(f"  - 待处理提醒: {summary['pending_reminders']}")
    print(f"  - 对话轮数: {summary['conversation_turns']}")
    print(f"  - 当前阶段: {summary['stage']}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Agent3 提醒功能测试")
    print("="*60)

    try:
        # 运行测试
        test_reminder_service()
        test_reminder_agent_basic()
        test_reminder_agent_commands()
        test_reminder_config()
        test_agent_summary()

        print("\n" + "="*60)
        print("所有测试完成！")
        print("="*60)

    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback
        traceback.print_exc()
