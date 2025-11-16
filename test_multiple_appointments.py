"""
测试多次预约功能
验证：
1. 同一患者可以预约多个医生
2. 历史预约只显示今天之前的预约
3. 当前/未来预约单独显示
"""
import sys
import json
from datetime import datetime, timedelta
from database.user_history_service import UserHistoryService
from database.appointment_service import AppointmentService

def test_multiple_appointments():
    """测试同一患者预约多个医生"""
    print("=" * 60)
    print("测试：同一患者预约多个医生")
    print("=" * 60)
    
    appointment_service = AppointmentService()
    
    # 模拟患者数据 - 第一次预约
    patient_data_1 = {
        "patient_info": {
            "name": "测试患者",
            "age": "45",
            "gender": "男",
            "contact": "13800138888"
        },
        "chief_complaint": "左眼视力模糊",
        "medical_history": "无",
        "allergy_history": "无",
        "family_history": "无",
        "appointment": {
            "department": "眼科",
            "preferred_time": "明天上午",
            "urgency": "普通"
        }
    }
    
    print("\n【第一次预约】")
    result_1 = appointment_service.process_appointment(patient_data_1)
    if result_1['success']:
        print(f"[OK] 预约成功！")
        print(f"  患者ID: {result_1['patient_id']}")
        print(f"  预约ID: {result_1['appointment_id']}")
        print(f"  医生: {result_1['doctor_info']['name']} ({result_1['doctor_info']['title']})")
        print(f"  时间: {result_1['appointment_time']}")
        patient_id = result_1['patient_id']
    else:
        print(f"[FAIL] 预约失败: {result_1['message']}")
        return
    
    # 同一患者第二次预约（预约不同医生）
    patient_data_2 = {
        "patient_info": {
            "name": "测试患者",
            "age": "45",
            "gender": "男",
            "contact": "13800138888"
        },
        "chief_complaint": "右眼疼痛",
        "medical_history": "无",
        "allergy_history": "无",
        "family_history": "无",
        "appointment": {
            "department": "眼科",
            "preferred_time": "后天下午",
            "urgency": "紧急"
        }
    }
    
    print("\n【第二次预约（同一患者，不同时间和症状）】")
    result_2 = appointment_service.process_appointment(patient_data_2)
    if result_2['success']:
        print(f"[OK] 预约成功！")
        print(f"  患者ID: {result_2['patient_id']}")
        print(f"  预约ID: {result_2['appointment_id']}")
        print(f"  医生: {result_2['doctor_info']['name']} ({result_2['doctor_info']['title']})")
        print(f"  时间: {result_2['appointment_time']}")
    else:
        print(f"[FAIL] 预约失败: {result_2['message']}")
        return
    
    # 验证患者ID是否相同
    print("\n【验证】")
    if result_1['patient_id'] == result_2['patient_id']:
        print(f"[OK] 两次预约使用相同的患者ID: {patient_id}")
    else:
        print(f"[FAIL] 患者ID不同！第一次: {result_1['patient_id']}, 第二次: {result_2['patient_id']}")
    
    if result_1['appointment_id'] != result_2['appointment_id']:
        print(f"[OK] 两次预约创建了不同的预约记录")
        print(f"  第一次预约ID: {result_1['appointment_id']}")
        print(f"  第二次预约ID: {result_2['appointment_id']}")
    else:
        print(f"[FAIL] 预约ID相同！可能出现了错误")
    
    appointment_service.close()


def test_historical_vs_current_appointments():
    """测试历史预约和当前预约的区分"""
    print("\n" + "=" * 60)
    print("测试：历史预约和当前/未来预约的区分")
    print("=" * 60)
    
    history_service = UserHistoryService()
    
    # 假设使用患者ID=1进行测试（需要数据库中有这个患者）
    test_patient_id = 1
    
    print(f"\n查询患者ID: {test_patient_id} 的预约记录")
    
    # 查询所有预约
    all_appointments = history_service.get_user_appointments(test_patient_id)
    print(f"\n【所有预约】共 {len(all_appointments)} 条")
    for i, appt in enumerate(all_appointments[:5], 1):
        appt_time = appt.get('Appointment_Time', '未知')
        if isinstance(appt_time, datetime):
            appt_time_str = appt_time.strftime('%Y-%m-%d %H:%M')
        else:
            appt_time_str = str(appt_time)
        print(f"  {i}. {appt_time_str} - {appt.get('Doctor_Name', '未知')} ({appt.get('Doctor_Title', '')})")
    
    # 查询历史预约（今天之前）
    historical_appointments = history_service.get_historical_appointments(test_patient_id)
    print(f"\n【历史预约】（今天之前）共 {len(historical_appointments)} 条")
    for i, appt in enumerate(historical_appointments[:5], 1):
        appt_time = appt.get('Appointment_Time', '未知')
        if isinstance(appt_time, datetime):
            appt_time_str = appt_time.strftime('%Y-%m-%d %H:%M')
        else:
            appt_time_str = str(appt_time)
        print(f"  {i}. {appt_time_str} - {appt.get('Doctor_Name', '未知')} ({appt.get('Doctor_Title', '')})")
    
    # 查询当前/未来预约
    current_future_appointments = history_service.get_current_future_appointments(test_patient_id)
    print(f"\n【当前/未来预约】（今天及以后）共 {len(current_future_appointments)} 条")
    for i, appt in enumerate(current_future_appointments[:5], 1):
        appt_time = appt.get('Appointment_Time', '未知')
        if isinstance(appt_time, datetime):
            appt_time_str = appt_time.strftime('%Y-%m-%d %H:%M')
        else:
            appt_time_str = str(appt_time)
        print(f"  {i}. {appt_time_str} - {appt.get('Doctor_Name', '未知')} ({appt.get('Doctor_Title', '')})")
    
    # 验证
    print("\n【验证】")
    today = datetime.now().date()
    
    # 验证历史预约都在今天之前
    all_historical_valid = True
    for appt in historical_appointments:
        appt_time = appt.get('Appointment_Time')
        if isinstance(appt_time, datetime):
            appt_date = appt_time.date()
            if appt_date >= today:
                all_historical_valid = False
                print(f"[FAIL] 发现历史预约中有今天或未来的预约: {appt_time}")
                break
    
    if all_historical_valid:
        print(f"[OK] 所有历史预约都在今天（{today}）之前")
    
    # 验证当前/未来预约都在今天及以后
    all_current_future_valid = True
    for appt in current_future_appointments:
        appt_time = appt.get('Appointment_Time')
        if isinstance(appt_time, datetime):
            appt_date = appt_time.date()
            if appt_date < today:
                all_current_future_valid = False
                print(f"[FAIL] 发现当前/未来预约中有过去的预约: {appt_time}")
                break
    
    if all_current_future_valid:
        print(f"[OK] 所有当前/未来预约都在今天（{today}）及以后")
    
    # 显示格式化的历史信息
    print("\n" + "=" * 60)
    print("【格式化的用户历史信息】")
    print("=" * 60)
    history_text = history_service.format_user_history_text(test_patient_id)
    print(history_text)
    
    history_service.close()


if __name__ == "__main__":
    try:
        # 测试1：同一患者多次预约
        test_multiple_appointments()
        
        # 测试2：历史预约和当前预约区分
        test_historical_vs_current_appointments()
        
        print("\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

