"""
测试多角色智能体系统
"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_patient_role():
    """测试患者角色"""
    print("\n" + "="*60)
    print("测试1: 患者角色 - 健康咨询")
    print("="*60)
    
    session_id = f"test_patient_{int(time.time())}"
    
    # 1. 患者咨询症状
    response = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "医生您好，我最近眼睛有点模糊",
        "session_id": session_id,
        "role": "patient"
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n[患者] 我: 医生您好，我最近眼睛有点模糊")
        print(f"[AI] 回复: {data['response'][:100]}...")
        print(f"当前Agent: {data.get('agent_type')}")
        print(f"当前阶段: {data.get('stage')}")
    else:
        print(f"❌ 请求失败: {response.status_code}")
        return False
    
    # 2. 患者尝试查看历史报告（应该切换到report agent）
    print("\n" + "-"*60)
    print("测试2: 患者角色 - 查看历史报告")
    print("-"*60)
    
    response = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "我想查看一下我的历史病例报告",
        "session_id": session_id,
        "role": "patient"
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n[患者] 我: 我想查看一下我的历史病例报告")
        print(f"[AI] 回复: {data['response'][:100]}...")
        print(f"当前Agent: {data.get('agent_type')}")
        print(f"当前阶段: {data.get('stage')}")
        
        if data.get('agent_type') == 'report':
            print("✅ 成功切换到报告Agent")
        else:
            print("⚠️ 未切换到报告Agent")
    else:
        print(f"❌ 请求失败: {response.status_code}")
        return False
    
    # 3. 患者尝试生成报告（应该被拒绝）
    print("\n" + "-"*60)
    print("测试3: 患者角色 - 尝试生成报告（应被拒绝）")
    print("-"*60)
    
    response = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "请帮我生成一份病例报告",
        "session_id": session_id,
        "role": "patient"
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n[患者] 我: 请帮我生成一份病例报告")
        print(f"[AI] 回复: {data['response']}")
        
        if "抱歉" in data['response'] or "无权" in data['response'] or "不能生成" in data['response']:
            print("✅ 成功拒绝患者生成报告")
        else:
            print("⚠️ 权限控制可能有问题")
    else:
        print(f"❌ 请求失败: {response.status_code}")
        return False
    
    return True


def test_doctor_role():
    """测试医生角色"""
    print("\n" + "="*60)
    print("测试4: 医生角色 - 健康咨询")
    print("="*60)
    
    session_id = f"test_doctor_{int(time.time())}"
    
    # 1. 医生进行问诊
    response = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "患者主诉眼睛模糊，我需要了解详细情况",
        "session_id": session_id,
        "role": "doctor"
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n[医生] 我: 患者主诉眼睛模糊，我需要了解详细情况")
        print(f"[AI] 回复: {data['response'][:100]}...")
        print(f"当前Agent: {data.get('agent_type')}")
        print(f"当前阶段: {data.get('stage')}")
    else:
        print(f"❌ 请求失败: {response.status_code}")
        return False
    
    # 2. 医生查看患者历史
    print("\n" + "-"*60)
    print("测试5: 医生角色 - 查看患者历史")
    print("-"*60)
    
    response = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "查看这个患者的历史病例",
        "session_id": session_id,
        "role": "doctor"
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n[医生] 我: 查看这个患者的历史病例")
        print(f"[AI] 回复: {data['response'][:100]}...")
        print(f"当前Agent: {data.get('agent_type')}")
        print(f"当前阶段: {data.get('stage')}")
        
        if data.get('agent_type') == 'report':
            print("✅ 成功切换到报告Agent")
        else:
            print("⚠️ 未切换到报告Agent")
    else:
        print(f"❌ 请求失败: {response.status_code}")
        return False
    
    # 3. 医生尝试生成报告（应该允许）
    print("\n" + "-"*60)
    print("测试6: 医生角色 - 生成报告（应允许）")
    print("-"*60)
    
    response = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "我想生成一份病例报告",
        "session_id": session_id,
        "role": "doctor"
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n[医生] 我: 我想生成一份病例报告")
        print(f"[AI] 回复: {data['response'][:150]}...")
        print(f"当前Agent: {data.get('agent_type')}")
        
        # 检查是否提示需要选择具体病例或直接生成
        if "哪一份" in data['response'] or "选择" in data['response'] or "生成成功" in data['response']:
            print("✅ 医生可以使用生成报告功能")
        elif "抱歉" in data['response'] or "无权" in data['response']:
            print("❌ 医生被错误拒绝")
        else:
            print("⚠️ 响应不明确")
    else:
        print(f"❌ 请求失败: {response.status_code}")
        return False
    
    return True


def test_intent_detection():
    """测试意图识别"""
    print("\n" + "="*60)
    print("测试7: 意图识别 - 自动切换Agent")
    print("="*60)
    
    session_id = f"test_intent_{int(time.time())}"
    
    test_cases = [
        ("我眼睛疼", "health", "症状咨询应使用health agent"),
        ("查看历史报告", "report", "查看报告应使用report agent"),
        ("我想预约医生", "health", "预约医生应使用health agent"),
        ("对比我的两次就诊记录", "report", "对比记录应使用report agent"),
    ]
    
    for message, expected_agent, description in test_cases:
        print(f"\n测试: {description}")
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "message": message,
            "session_id": session_id,
            "role": "doctor"
        })
        
        if response.status_code == 200:
            data = response.json()
            actual_agent = data.get('agent_type')
            print(f"  消息: {message}")
            print(f"  期望Agent: {expected_agent}")
            print(f"  实际Agent: {actual_agent}")
            
            if actual_agent == expected_agent:
                print(f"  ✅ 意图识别正确")
            else:
                print(f"  ⚠️ 意图识别可能有误")
        else:
            print(f"  ❌ 请求失败: {response.status_code}")
    
    return True


def main():
    """主测试函数"""
    print("\n" + "#"*60)
    print("# 多角色智能体系统测试")
    print("#"*60)
    
    try:
        # 等待服务器启动
        print("\n等待服务器启动...")
        for i in range(5):
            try:
                response = requests.get(f"{BASE_URL}/api/stats", timeout=2)
                if response.status_code == 200:
                    print("✅ 服务器已就绪")
                    break
            except:
                if i < 4:
                    print(f"  等待中... ({i+1}/5)")
                    time.sleep(2)
                else:
                    print("❌ 无法连接到服务器，请确保服务器已启动")
                    print("   运行命令: python main.py")
                    return
        
        # 运行测试
        test_patient_role()
        test_doctor_role()
        test_intent_detection()
        
        print("\n" + "#"*60)
        print("# 测试完成")
        print("#"*60)
        
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

