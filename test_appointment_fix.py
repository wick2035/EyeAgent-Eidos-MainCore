"""
测试预约修复效果的脚本
模拟用户在不同阶段提供预约信息的场景
"""
import requests
import json
import uuid

BASE_URL = "http://localhost:8000"

def test_appointment_early_stage():
    """
    测试场景：用户在早期阶段（OPHTHALMOLOGY_TRIAGE）就提供预约时间
    这是之前会失败的场景
    """
    print("=" * 80)
    print("测试场景：用户在眼科分诊阶段就提供预约信息")
    print("=" * 80)

    session_id = str(uuid.uuid4())
    phone_number = "13900000002"

    messages = [
        "你好",
        "眼痛",
        "持续性的，我想约个医生，明天下午14点可以吗",  # 在早期阶段提供预约时间
        "刘医生，无过敏"
    ]

    for i, message in enumerate(messages, 1):
        print(f"\n[消息 {i}] 用户: {message}")

        response = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "session_id": session_id,
                "message": message,
                "role": "patient",
                "user_id": 2,
                "phone_number": phone_number
            }
        )

        if response.status_code == 200:
            data = response.json()
            print(f"[响应] AI: {data['response'][:200]}...")
            print(f"[状态] 完成: {data['is_completed']}, 阶段: {data.get('stage', 'N/A')}")

            # 检查是否包含预约成功的标记
            if "✅" in data['response'] or "预约ID" in data['response']:
                print("✅ 检测到预约成功消息！")

                # 检查数据库
                check_appointment_in_db(phone_number)
                return True
        else:
            print(f"❌ 请求失败: {response.status_code}")
            return False

    print("\n⚠️ 对话结束但未看到预约成功标记")
    return False

def check_appointment_in_db(phone_number):
    """检查数据库中是否有预约记录"""
    print("\n--- 检查数据库预约记录 ---")

    try:
        response = requests.get(
            f"{BASE_URL}/api/appointments",
            params={"phone_number": phone_number}
        )

        if response.status_code == 200:
            appointments = response.json()
            print(f"找到 {len(appointments)} 条预约记录")

            if appointments:
                latest = appointments[-1]
                print(f"最新预约:")
                print(f"  - 预约ID: {latest.get('Appointment_UUID')}")
                print(f"  - 医生: {latest.get('Doctor_Name')}")
                print(f"  - 时间: {latest.get('Appointment_Time')}")
                print(f"  - 状态: {latest.get('Status')}")
                return True
            else:
                print("❌ 数据库中没有预约记录！")
                return False
        else:
            print(f"❌ 查询失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 查询异常: {e}")
        return False

def test_appointment_normal_flow():
    """
    测试场景：正常流程，按阶段收集信息后预约
    """
    print("\n" + "=" * 80)
    print("测试场景：正常流程按阶段预约")
    print("=" * 80)

    session_id = str(uuid.uuid4())
    phone_number = "13900000003"

    messages = [
        "你好，我想预约",
        "王五，男，35岁，电话13900000003",
        "眼睛红肿，有分泌物",
        "无既往病史",
        "无过敏",
        "明天上午10点，李医生"
    ]

    for i, message in enumerate(messages, 1):
        print(f"\n[消息 {i}] 用户: {message}")

        response = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "session_id": session_id,
                "message": message,
                "role": "patient",
                "phone_number": phone_number
            }
        )

        if response.status_code == 200:
            data = response.json()
            print(f"[响应] AI: {data['response'][:200]}...")
            print(f"[状态] 完成: {data['is_completed']}, 阶段: {data.get('stage', 'N/A')}")

            if "✅" in data['response'] or "预约ID" in data['response']:
                print("✅ 检测到预约成功消息！")
                check_appointment_in_db(phone_number)
                return True
        else:
            print(f"❌ 请求失败: {response.status_code}")
            return False

    print("\n⚠️ 对话结束但未看到预约成功标记")
    return False

def main():
    """运行所有测试"""
    print("\n" + "🧪" * 40)
    print("开始测试预约修复效果")
    print("🧪" * 40)

    # 首先确保服务器运行
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code != 200:
            print("❌ 服务器未运行，请先启动 main.py")
            return
    except:
        print("❌ 无法连接到服务器，请确保 main.py 正在运行")
        return

    print("✅ 服务器运行正常\n")

    # 测试1: 早期阶段提供预约信息（之前会失败的场景）
    result1 = test_appointment_early_stage()

    # 测试2: 正常流程
    result2 = test_appointment_normal_flow()

    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"早期阶段预约测试: {'✅ 通过' if result1 else '❌ 失败'}")
    print(f"正常流程预约测试: {'✅ 通过' if result2 else '❌ 失败'}")

    if result1 and result2:
        print("\n🎉 所有测试通过！预约功能修复成功！")
    else:
        print("\n⚠️ 部分测试失败，请检查日志")

if __name__ == "__main__":
    main()
