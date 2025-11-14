
"""
测试智能体与数据库集成
验证问答完成后是否能自动保存到数据库
"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"


def test_chat_and_database():
    """测试完整的对话流程和数据库操作"""
    
    print("=" * 60)
    print("智能体与数据库集成测试")
    print("=" * 60)
    
    # 对话序列
    messages = [
        "你好",
        "我最近眼睛看东西模糊，有点不舒服",
        "是的，我想预约医生",
        "我叫李明，30岁，男性，手机号是13912345678",
        "症状大概持续了一周左右，感觉视力有点下降",
        "没有其他病史，也不过敏",
        "明天下午可以吗？比较紧急"
    ]
    
    session_id = None
    
    print("\n开始对话测试...")
    print("-" * 60)
    
    for i, message in enumerate(messages):
        print(f"\n[第 {i+1} 轮]")
        print(f"用户: {message}")
        
        # 发送消息
        payload = {
            "message": message,
            "session_id": session_id
        }
        
        response = requests.post(f"{BASE_URL}/api/chat", json=payload)
        
        if response.status_code != 200:
            print(f"❌ 请求失败: {response.status_code}")
            print(response.text)
            return False
        
        data = response.json()
        session_id = data["session_id"]
        
        print(f"智能体: {data['response'][:100]}...")
        print(f"阶段: {data['stage']}")
        print(f"已完成: {data['is_completed']}")
        
        # 如果完成了，检查数据库
        if data['is_completed']:
            print("\n" + "=" * 60)
            print("✅ 对话已完成！")
            print("=" * 60)
            
            # 等待数据库操作完成
            time.sleep(1)
            
            # 检查是否保存到数据库
            check_database()
            break
        
        time.sleep(0.5)  # 避免请求过快
    
    return True


def check_database():
    """检查数据库中的记录"""
    
    print("\n检查数据库记录...")
    print("-" * 60)
    
    # 查询患者记录
    print("\n1️⃣ 查询患者记录:")
    try:
        response = requests.get(f"{BASE_URL}/api/patients")
        if response.status_code == 200:
            data = response.json()
            print(f"   患者总数: {data['count']}")
            if data['count'] > 0:
                latest = data['patients'][0]
                print(f"   最新患者: {latest['Name']}, {latest['Phone_Number']}")
                print(f"   就诊卡号: {latest['Visit_Card_Number']}")
                print(f"   主诉: {latest['Chief_Complaint']}")
                print("   ✅ 患者数据已保存")
        else:
            print(f"   ❌ 查询失败: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 查询错误: {e}")
    
    # 查询预约记录
    print("\n2️⃣ 查询预约记录:")
    try:
        response = requests.get(f"{BASE_URL}/api/appointments")
        if response.status_code == 200:
            data = response.json()
            print(f"   预约总数: {data['count']}")
            if data['count'] > 0:
                latest = data['appointments'][0]
                print(f"   最新预约: {latest['Patient_Name']}")
                print(f"   预约时间: {latest['Appointment_Time']}")
                print(f"   医生: {latest['Doctor_Name']} ({latest['Doctor_Title']})")
                print(f"   状态: {latest['Appointment_Status']}")
                print("   ✅ 预约数据已保存")
        else:
            print(f"   ❌ 查询失败: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 查询错误: {e}")
    
    print("\n" + "=" * 60)
    print("数据库验证完成")
    print("=" * 60)


def main():
    """主函数"""
    
    print("\n测试前提条件:")
    print("1. MySQL数据库已启动")
    print("2. 已运行数据库初始化脚本")
    print("3. FastAPI服务器正在运行 (python main.py)")
    print("\n开始测试...")
    print()
    
    try:
        # 测试服务器是否运行
        response = requests.get(BASE_URL, timeout=5)
        if response.status_code != 200:
            print("❌ 服务器未运行，请先启动: python main.py")
            return
    except Exception as e:
        print(f"❌ 无法连接到服务器，请先启动: python main.py")
        print(f"错误详情: {e}")
        return
    
    # 执行测试
    test_chat_and_database()


if __name__ == "__main__":
    main()

