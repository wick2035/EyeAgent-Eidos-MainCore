"""
简化版测试脚本 - 快速测试数据库集成
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_simple():
    """简单的对话测试"""
    
    print("=" * 60)
    print("简化版数据库集成测试")
    print("=" * 60)
    
    # 简化的对话序列（一次性提供所有信息）
    messages = [
        "你好，我最近眼睛不舒服，想预约医生",
        "我眼睛看东西模糊，已经持续一周了",
        "我叫李明，30岁，男性，手机号是13912345678",
        "没有其他病史，也不过敏，明天下午可以吗"
    ]
    
    session_id = None
    
    for i, message in enumerate(messages):
        print(f"\n[第 {i+1} 轮]")
        print(f"用户: {message}")
        
        payload = {
            "message": message,
            "session_id": session_id
        }
        
        try:
            response = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ 请求失败: {response.status_code}")
                print(response.text)
                return False
            
            data = response.json()
            session_id = data["session_id"]
            
            print(f"智能体: {data['response'][:150]}...")
            print(f"阶段: {data['stage']}")
            print(f"已完成: {data['is_completed']}")
            
            if data['is_completed']:
                print("\n" + "=" * 60)
                print("✅ 对话已完成！检查是否保存到数据库...")
                print("=" * 60)
                
                # 检查数据库
                import time
                time.sleep(2)
                check_database()
                return True
                
        except Exception as e:
            print(f"❌ 请求错误: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    print("\n⚠️ 对话未完成，继续检查数据库...")
    check_database()
    return True


def check_database():
    """检查数据库记录"""
    
    print("\n检查数据库记录...")
    print("-" * 60)
    
    try:
        # 查询患者记录
        print("\n1️⃣ 查询患者记录:")
        response = requests.get(f"{BASE_URL}/api/patients", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   患者总数: {data['count']}")
            if data['count'] > 0:
                latest = data['patients'][0]
                print(f"   最新患者: {latest.get('Name', 'N/A')}")
                print(f"   手机号: {latest.get('Phone_Number', 'N/A')}")
                print(f"   主诉: {latest.get('Chief_Complaint', 'N/A')}")
                print("   ✅ 患者数据已保存")
            else:
                print("   ⚠️ 暂无患者记录")
        else:
            print(f"   ❌ 查询失败: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 查询患者记录错误: {e}")
    
    try:
        # 查询预约记录
        print("\n2️⃣ 查询预约记录:")
        response = requests.get(f"{BASE_URL}/api/appointments", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   预约总数: {data['count']}")
            if data['count'] > 0:
                latest = data['appointments'][0]
                print(f"   最新预约: {latest.get('Patient_Name', 'N/A')}")
                print(f"   预约时间: {latest.get('Appointment_Time', 'N/A')}")
                print(f"   医生: {latest.get('Doctor_Name', 'N/A')}")
                print("   ✅ 预约数据已保存")
            else:
                print("   ⚠️ 暂无预约记录")
        else:
            print(f"   ❌ 查询失败: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 查询预约记录错误: {e}")


if __name__ == "__main__":
    print("\n开始测试...")
    
    # 检查服务器
    try:
        response = requests.get(BASE_URL, timeout=5)
        print(f"✅ 服务器运行正常 (状态码: {response.status_code})")
    except Exception as e:
        print(f"❌ 服务器未运行，请先启动: python main.py")
        print(f"错误: {e}")
        exit(1)
    
    # 运行测试
    test_simple()
    
    print("\n测试完成！")

