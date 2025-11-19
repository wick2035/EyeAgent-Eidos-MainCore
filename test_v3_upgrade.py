"""
测试V3升级功能
验证：
1. 数据库表结构是否正确
2. 时间段是否已生成
3. V3预约服务是否工作正常

使用方法：
    python test_v3_upgrade.py
"""

import sys
from datetime import date, datetime, timedelta
from database.db_connection import DatabaseConnection
from database.appointment_service_v3 import AppointmentServiceV3
from database.time_slot_service import TimeSlotService
from database.doctor_schedule_service import DoctorScheduleService


def test_database_tables():
    """测试数据库表结构"""
    print("\n" + "=" * 60)
    print("测试1: 检查数据库表结构")
    print("=" * 60)
    
    db = DatabaseConnection()
    
    required_tables = [
        'doctor',
        'doctor_working_schedule',
        'doctor_time_slots',
        'doctor_schedule_exceptions',
        'appointment'
    ]
    
    try:
        for table in required_tables:
            result = db.execute_one(f"SHOW TABLES LIKE '{table}'")
            if result:
                print(f"  [OK] 表 {table} 存在")
            else:
                print(f"  [FAIL] 表 {table} 不存在")
                return False
        
        # 检查doctor表的新字段
        result = db.execute_one("SHOW COLUMNS FROM doctor LIKE 'is_active'")
        if result:
            print(f"  [OK] doctor.is_active 字段存在")
        else:
            print(f"  [FAIL] doctor.is_active 字段不存在")
            return False
        
        # 检查appointment表的新字段
        result = db.execute_one("SHOW COLUMNS FROM appointment LIKE 'Time_Slot_ID'")
        if result:
            print(f"  [OK] appointment.Time_Slot_ID 字段存在")
        else:
            print(f"  [FAIL] appointment.Time_Slot_ID 字段不存在")
            return False
        
        print("\n[SUCCESS] 数据库表结构检查通过")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] 数据库检查失败: {e}")
        return False
    finally:
        db.close()


def test_doctor_schedules():
    """测试医生排班"""
    print("\n" + "=" * 60)
    print("测试2: 检查医生排班")
    print("=" * 60)
    
    service = DoctorScheduleService()
    
    try:
        # 查询第一个医生的排班
        db = DatabaseConnection()
        doctor = db.execute_one("SELECT Doctor_ID, Name FROM doctor LIMIT 1")
        db.close()
        
        if not doctor:
            print("  [FAIL] 没有找到医生数据")
            return False
        
        doctor_id = doctor['Doctor_ID']
        doctor_name = doctor['Name']
        
        result = service.get_weekly_schedule(doctor_id)
        if result['success'] and result['schedule']:
            print(f"  [OK] 医生 {doctor_name} 有 {len(result['schedule'])} 条排班规则")
            return True
        else:
            print(f"  [FAIL] 医生 {doctor_name} 没有排班规则")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] 排班检查失败: {e}")
        return False


def test_time_slots():
    """测试时间段生成"""
    print("\n" + "=" * 60)
    print("测试3: 检查时间段生成")
    print("=" * 60)
    
    service = TimeSlotService()
    
    try:
        # 查询今天和未来2天的时间段
        today = date.today()
        result = service.get_available_slots(
            start_date=today,
            end_date=today + timedelta(days=2),
            only_available=False
        )
        
        if result['success']:
            total = result['total_count']
            available = len([s for s in result['slots'] if s['is_available'] and s['remaining_slots'] > 0])
            print(f"  [OK] 找到 {total} 个时间段")
            print(f"  [OK] 其中 {available} 个可预约")
            
            if total > 0:
                # 显示示例
                example = result['slots'][0]
                print(f"\n  示例时间段:")
                print(f"    医生: {example['doctor_name']}")
                print(f"    时间: {example['appointment_datetime']}")
                print(f"    容量: {example['current_bookings']}/{example['max_capacity']}")
                return True
            else:
                print("  [WARN] 没有找到时间段，可能需要运行生成脚本")
                return False
        else:
            print(f"  [FAIL] 查询时间段失败: {result.get('message')}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] 时间段检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_v3_appointment_service():
    """测试V3预约服务"""
    print("\n" + "=" * 60)
    print("测试4: V3预约服务功能")
    print("=" * 60)
    
    service = AppointmentServiceV3()
    
    try:
        # 测试查找可用医生
        available_doctors = service.find_available_doctors(
            department="眼科",
            preferred_time_expr="明天上午"
        )
        
        if available_doctors:
            print(f"  [OK] 找到 {len(available_doctors)} 位可用医生")
            
            # 显示第一个医生的信息
            doctor = available_doctors[0]
            print(f"\n  示例医生:")
            print(f"    姓名: {doctor['doctor_name']}")
            print(f"    职称: {doctor['doctor_title']}")
            print(f"    可用时间段: {len(doctor['available_slots'])} 个")
            
            if doctor['available_slots']:
                slot = doctor['available_slots'][0]
                print(f"    首个时间段: {slot['appointment_datetime']}")
                print(f"    剩余名额: {slot['remaining_slots']}")
            
            return True
        else:
            print("  [WARN] 没有找到可用医生")
            print("  提示: 可能需要为医生创建排班并生成时间段")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] 预约服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("V3升级功能测试")
    print("=" * 60)
    
    results = {
        "数据库表结构": test_database_tables(),
        "医生排班": test_doctor_schedules(),
        "时间段生成": test_time_slots(),
        "V3预约服务": test_v3_appointment_service()
    }
    
    # 显示测试结果汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] 所有测试通过，V3升级成功！")
        print("\n下一步:")
        print("  1. 启动应用: python main.py")
        print("  2. 测试预约功能")
        print("  3. 定时任务将在每天0点自动生成时间段")
    else:
        print("[FAILED] 部分测试失败，请检查错误信息")
    print("=" * 60)


if __name__ == '__main__':
    main()

