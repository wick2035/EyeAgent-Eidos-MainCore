"""
数据库升级到V3版本 - 执行脚本
只进行补充修改，不删除现有数据

功能：
1. 执行upgrade_to_v3.sql升级数据库结构
2. 为所有医生创建默认排班规则
3. 生成未来3天的时间段

使用方法：
    python database/run_upgrade_to_v3.py
"""

import sys
import os
from datetime import date, time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_connection import DatabaseConnection
from database.doctor_schedule_service import DoctorScheduleService
from utils.schedule_generator import ScheduleGenerator


def execute_sql_file(filepath):
    """执行SQL文件"""
    print(f"\n[步骤 1/3] 执行SQL升级脚本...")
    
    try:
        # 读取SQL文件
        with open(filepath, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 分割SQL语句（按分号分割，但跳过触发器内部的分号）
        statements = []
        current_statement = []
        in_delimiter = False
        
        for line in sql_content.split('\n'):
            line = line.strip()
            
            # 跳过注释和空行
            if not line or line.startswith('--'):
                continue
            
            # 检测DELIMITER
            if 'DELIMITER' in line.upper():
                if '$$' in line:
                    in_delimiter = True
                else:
                    in_delimiter = False
                continue
            
            current_statement.append(line)
            
            # 判断语句结束
            if not in_delimiter and line.endswith(';'):
                statements.append(' '.join(current_statement))
                current_statement = []
            elif in_delimiter and line.endswith('$$'):
                statements.append(' '.join(current_statement))
                current_statement = []
        
        # 执行SQL语句
        db = DatabaseConnection()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        executed_count = 0
        for statement in statements:
            statement = statement.strip()
            if not statement:
                continue
            
            # 移除末尾的 $$ 或 ;
            statement = statement.rstrip('$$').rstrip(';')
            
            try:
                cursor.execute(statement)
                executed_count += 1
            except Exception as e:
                # 忽略"已存在"的错误
                error_msg = str(e).lower()
                if 'duplicate' in error_msg or 'exists' in error_msg or "doesn't exist" in error_msg:
                    print(f"  -> 跳过: {error_msg[:50]}")
                else:
                    print(f"  ! 执行失败: {e}")
        
        conn.commit()
        cursor.close()
        db.close()
        
        print(f"[OK] SQL升级完成，执行了 {executed_count} 条语句")
        return True
        
    except Exception as e:
        print(f"[ERROR] SQL升级失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def initialize_doctor_schedules():
    """为现有医生创建默认排班规则"""
    print(f"\n[步骤 2/3] 为现有医生创建默认排班规则...")
    
    try:
        db = DatabaseConnection()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 获取所有活跃医生
        sql = "SELECT Doctor_ID, Name FROM doctor WHERE is_active = TRUE OR is_active IS NULL"
        cursor.execute(sql)
        doctors = cursor.fetchall()
        cursor.close()
        db.close()
        
        if not doctors:
            print("  -> 没有找到医生")
            return True
        
        schedule_service = DoctorScheduleService()
        
        # 默认排班：周一到周五，上午9:00-12:00，下午14:00-17:00
        default_schedule = [
            # 周一
            {"day_of_week": 1, "shift_start_time": "09:00:00", "shift_end_time": "12:00:00", "is_active": True},
            {"day_of_week": 1, "shift_start_time": "14:00:00", "shift_end_time": "17:00:00", "is_active": True},
            # 周二
            {"day_of_week": 2, "shift_start_time": "09:00:00", "shift_end_time": "12:00:00", "is_active": True},
            {"day_of_week": 2, "shift_start_time": "14:00:00", "shift_end_time": "17:00:00", "is_active": True},
            # 周三
            {"day_of_week": 3, "shift_start_time": "09:00:00", "shift_end_time": "12:00:00", "is_active": True},
            {"day_of_week": 3, "shift_start_time": "14:00:00", "shift_end_time": "17:00:00", "is_active": True},
            # 周四
            {"day_of_week": 4, "shift_start_time": "09:00:00", "shift_end_time": "12:00:00", "is_active": True},
            {"day_of_week": 4, "shift_start_time": "14:00:00", "shift_end_time": "17:00:00", "is_active": True},
            # 周五
            {"day_of_week": 5, "shift_start_time": "09:00:00", "shift_end_time": "12:00:00", "is_active": True},
            {"day_of_week": 5, "shift_start_time": "14:00:00", "shift_end_time": "17:00:00", "is_active": True},
        ]
        
        success_count = 0
        for doctor in doctors:
            doctor_id = doctor['Doctor_ID']
            doctor_name = doctor['Name']
            
            # 检查是否已有排班
            schedule_result = schedule_service.get_weekly_schedule(doctor_id)
            if schedule_result['success'] and schedule_result['schedule']:
                print(f"  -> {doctor_name}: 已有排班规则，跳过")
                continue
            
            # 创建排班
            result = schedule_service.create_weekly_schedule(doctor_id, default_schedule)
            if result['success']:
                print(f"  [OK] {doctor_name}: {result['created_count']} 条排班规则")
                success_count += 1
            else:
                print(f"  [FAIL] {doctor_name}: {result.get('message', '失败')}")
        
        print(f"[OK] 为 {success_count}/{len(doctors)} 位医生创建了排班规则")
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建排班规则失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_initial_time_slots():
    """生成未来3天的时间段"""
    print(f"\n[步骤 3/3] 生成未来3天的时间段...")
    
    try:
        generator = ScheduleGenerator()
        result = generator.generate_slots_for_all_doctors(
            start_date=date.today(),
            days=3
        )
        
        if result['success']:
            print(f"[OK] 成功生成 {result['total_slots_created']} 个时间段")
            print(f"  处理了 {result['doctors_processed']} 位医生")
            return True
        else:
            print(f"[FAIL] 生成时间段失败: {result.get('message', '未知错误')}")
            return False
            
    except Exception as e:
        print(f"[ERROR] 生成时间段失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 70)
    print("数据库升级到 V3 版本")
    print("=" * 70)
    
    # 获取SQL文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sql_file = os.path.join(current_dir, 'upgrade_to_v3.sql')
    
    if not os.path.exists(sql_file):
        print(f"[ERROR] 找不到SQL文件: {sql_file}")
        return
    
    # 执行升级步骤
    success = True
    
    # 步骤1: 执行SQL
    if not execute_sql_file(sql_file):
        success = False
    
    # 步骤2: 初始化排班
    if success and not initialize_doctor_schedules():
        success = False
    
    # 步骤3: 生成时间段
    if success and not generate_initial_time_slots():
        success = False
    
    # 显示结果
    print("\n" + "=" * 70)
    if success:
        print("[SUCCESS] 升级成功完成！")
        print("\n下一步:")
        print("  1. 更新 main.py 使用 AppointmentServiceV3")
        print("  2. 启动应用测试预约功能")
        print("  3. 设置定时任务每天0点生成时间段")
    else:
        print("[FAILED] 升级过程中出现错误")
        print("\n建议:")
        print("  1. 检查错误信息")
        print("  2. 确认数据库连接正常")
        print("  3. 如有必要，恢复数据库备份后重试")
    print("=" * 70)


if __name__ == '__main__':
    main()

