"""
数据库迁移脚本：从 V2 迁移到 V3（时间段管理系统）

功能：
1. 备份 V2 数据
2. 执行 V3 架构创建（init_database_v3.sql）
3. 迁移现有数据
4. 为所有医生创建默认排班规则
5. 生成初始时间段

使用方法：
    python database/migrate_to_slot_system.py

注意事项：
- 此脚本会修改数据库结构
- 建议先在测试环境运行
- 执行前会提示确认

Created: 2025-11-19
"""

import sys
import os
from datetime import datetime, date, time, timedelta
import pymysql

# 添加项目根目录
sys.path.insert(0, 'D:\\Agent\\pythonProject1')

from database.db_config import DB_CONFIG
from database.doctor_schedule_service import DoctorScheduleService
from utils.schedule_generator import ScheduleGenerator


class DatabaseMigration:
    """数据库迁移工具"""

    def __init__(self):
        self.db_config = DB_CONFIG
        self.backup_file = None

    def get_connection(self):
        """获取数据库连接"""
        return pymysql.connect(
            host=self.db_config['host'],
            port=self.db_config['port'],
            user=self.db_config['user'],
            password=self.db_config['password'],
            database=self.db_config['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

    def backup_v2_data(self) -> bool:
        """
        备份 V2 版本数据

        Returns:
            备份是否成功
        """
        print("\n[步骤 1/5] 备份 V2 数据...")

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # 创建备份目录
            backup_dir = "D:\\Agent\\pythonProject1\\database\\backup"
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.backup_file = os.path.join(backup_dir, f"backup_v2_{timestamp}.sql")

            print(f"备份文件：{self.backup_file}")

            with open(self.backup_file, 'w', encoding='utf-8') as f:
                # 备份 doctor 表的 Available_Time 数据
                f.write("-- V2 Doctor Table Backup\n")
                f.write(f"-- Created: {datetime.now()}\n\n")

                cursor.execute("SELECT * FROM doctor")
                doctors = cursor.fetchall()

                for doctor in doctors:
                    f.write(f"-- Doctor: {doctor['Name']}\n")
                    f.write(f"-- Available_Time: {doctor.get('Available_Time', 'NULL')}\n\n")

                # 备份预约数据
                cursor.execute("SELECT COUNT(*) as count FROM appointment")
                appointment_count = cursor.fetchone()['count']
                f.write(f"-- Total Appointments: {appointment_count}\n\n")

            print(f"✓ 备份完成：{len(doctors)} 位医生数据已保存")
            return True

        except Exception as e:
            print(f"✗ 备份失败：{e}")
            return False
        finally:
            if conn:
                conn.close()

    def execute_v3_schema(self) -> bool:
        """
        执行 V3 数据库架构

        Returns:
            执行是否成功
        """
        print("\n[步骤 2/5] 执行 V3 数据库架构...")

        sql_file = "D:\\Agent\\pythonProject1\\database\\init_database_v3.sql"

        if not os.path.exists(sql_file):
            print(f"✗ SQL 文件不存在：{sql_file}")
            return False

        conn = None
        try:
            # 读取 SQL 文件
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            conn = self.get_connection()
            cursor = conn.cursor()

            # 分割 SQL 语句
            statements = []
            current_statement = []
            in_delimiter_block = False

            for line in sql_content.split('\n'):
                stripped = line.strip()

                # 处理 DELIMITER
                if stripped.startswith('DELIMITER'):
                    in_delimiter_block = 'DELIMITER $$' in line
                    continue

                if in_delimiter_block:
                    current_statement.append(line)
                    if 'DELIMITER ;' in line:
                        in_delimiter_block = False
                        statements.append('\n'.join(current_statement))
                        current_statement = []
                else:
                    if stripped and not stripped.startswith('--'):
                        current_statement.append(line)
                        if stripped.endswith(';'):
                            statements.append('\n'.join(current_statement))
                            current_statement = []

            # 执行 SQL 语句
            executed_count = 0
            for statement in statements:
                statement = statement.strip()
                if statement:
                    try:
                        # 分割触发器定义中的多个语句
                        if 'CREATE TRIGGER' in statement:
                            # 触发器需要特殊处理
                            cursor.execute(statement)
                        else:
                            for stmt in statement.split(';'):
                                stmt = stmt.strip()
                                if stmt:
                                    cursor.execute(stmt)
                        executed_count += 1
                    except Exception as e:
                        # 忽略一些预期的错误（如表已存在）
                        if 'already exists' not in str(e).lower():
                            print(f"警告：执行SQL时出错：{e}")

            conn.commit()
            print(f"✓ V3 架构创建完成，执行了 {executed_count} 条语句")
            return True

        except Exception as e:
            print(f"✗ 执行V3架构失败：{e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def create_default_schedules(self) -> bool:
        """
        为现有医生创建默认排班规则

        默认规则：周一至周五 9:00-12:00, 14:00-17:00

        Returns:
            创建是否成功
        """
        print("\n[步骤 3/5] 创建默认排班规则...")

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # 获取所有医生
            cursor.execute("SELECT Doctor_ID, Name FROM doctor WHERE is_active = TRUE")
            doctors = cursor.fetchall()

            if not doctors:
                print("✗ 未找到活跃医生")
                return False

            schedule_service = DoctorScheduleService()
            success_count = 0

            for doctor in doctors:
                doctor_id = doctor['Doctor_ID']
                doctor_name = doctor['Name']

                # 创建周一至周五的排班（上午+下午）
                schedule_data = []
                for day in range(1, 6):  # 1=周一, 5=周五
                    schedule_data.append({
                        "day_of_week": day,
                        "shift_start_time": "09:00:00",
                        "shift_end_time": "12:00:00",
                        "is_active": True
                    })
                    schedule_data.append({
                        "day_of_week": day,
                        "shift_start_time": "14:00:00",
                        "shift_end_time": "17:00:00",
                        "is_active": True
                    })

                result = schedule_service.create_weekly_schedule(doctor_id, schedule_data)

                if result['success']:
                    print(f"✓ {doctor_name}: {result['created_count']} 条排班规则")
                    success_count += 1
                else:
                    print(f"✗ {doctor_name}: {result['message']}")

            print(f"\n✓ 为 {success_count}/{len(doctors)} 位医生创建排班规则")
            return success_count > 0

        except Exception as e:
            print(f"✗ 创建排班规则失败：{e}")
            return False
        finally:
            if conn:
                conn.close()

    def generate_initial_slots(self) -> bool:
        """
        生成未来3天的初始时间段

        Returns:
            生成是否成功
        """
        print("\n[步骤 4/5] 生成初始时间段...")

        try:
            generator = ScheduleGenerator()

            result = generator.generate_slots_for_all_doctors(
                start_date=date.today(),
                days=3
            )

            if result['success']:
                print(f"✓ 成功生成 {result['total_slots_created']} 个时间段")
                print(f"  处理医生数：{result['doctors_processed']}")
                return True
            else:
                print(f"✗ 生成时间段失败：{result['message']}")
                return False

        except Exception as e:
            print(f"✗ 生成时间段异常：{e}")
            return False

    def verify_migration(self) -> bool:
        """
        验证迁移结果

        Returns:
            验证是否通过
        """
        print("\n[步骤 5/5] 验证迁移结果...")

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            checks = []

            # 检查1：doctor 表是否有新字段
            cursor.execute("SHOW COLUMNS FROM doctor LIKE 'default_slot_duration_minutes'")
            has_new_field = cursor.fetchone() is not None
            checks.append(("doctor表新字段", has_new_field))

            # 检查2：新表是否存在
            cursor.execute("SHOW TABLES LIKE 'doctor_working_schedule'")
            has_schedule_table = cursor.fetchone() is not None
            checks.append(("doctor_working_schedule表", has_schedule_table))

            cursor.execute("SHOW TABLES LIKE 'doctor_time_slots'")
            has_slots_table = cursor.fetchone() is not None
            checks.append(("doctor_time_slots表", has_slots_table))

            cursor.execute("SHOW TABLES LIKE 'doctor_schedule_exceptions'")
            has_exceptions_table = cursor.fetchone() is not None
            checks.append(("doctor_schedule_exceptions表", has_exceptions_table))

            # 检查3：触发器是否存在
            cursor.execute("SHOW TRIGGERS LIKE 'appointment'")
            triggers = cursor.fetchall()
            has_triggers = len(triggers) >= 3
            checks.append(("预约触发器", has_triggers))

            # 检查4：是否有排班数据
            cursor.execute("SELECT COUNT(*) as count FROM doctor_working_schedule")
            schedule_count = cursor.fetchone()['count']
            has_schedules = schedule_count > 0
            checks.append(("排班规则数据", has_schedules))

            # 检查5：是否有时间段数据
            cursor.execute("SELECT COUNT(*) as count FROM doctor_time_slots")
            slot_count = cursor.fetchone()['count']
            has_slots = slot_count > 0
            checks.append(("时间段数据", has_slots))

            # 输出验证结果
            print("\n验证项目：")
            all_passed = True
            for check_name, passed in checks:
                status = "✓" if passed else "✗"
                print(f"  {status} {check_name}")
                if not passed:
                    all_passed = False

            if all_passed:
                print("\n✓ 所有验证项通过！")
                print(f"\n统计信息：")
                print(f"  - 排班规则：{schedule_count} 条")
                print(f"  - 时间段：{slot_count} 个")
            else:
                print("\n✗ 部分验证项未通过，请检查")

            return all_passed

        except Exception as e:
            print(f"✗ 验证失败：{e}")
            return False
        finally:
            if conn:
                conn.close()

    def run_migration(self):
        """执行完整迁移流程"""
        print("=" * 70)
        print("数据库迁移工具：V2 → V3（时间段管理系统）")
        print("=" * 70)
        print("\n迁移流程：")
        print("1. 备份 V2 数据")
        print("2. 执行 V3 数据库架构")
        print("3. 创建默认排班规则")
        print("4. 生成初始时间段")
        print("5. 验证迁移结果")
        print("\n警告：此操作将修改数据库结构！")

        # 确认执行
        confirm = input("\n是否继续？(yes/no): ").strip().lower()
        if confirm != 'yes':
            print("\n已取消迁移")
            return

        # 执行迁移步骤
        start_time = datetime.now()

        steps = [
            ("备份数据", self.backup_v2_data),
            ("执行V3架构", self.execute_v3_schema),
            ("创建排班规则", self.create_default_schedules),
            ("生成时间段", self.generate_initial_slots),
            ("验证结果", self.verify_migration)
        ]

        results = []
        for step_name, step_func in steps:
            try:
                success = step_func()
                results.append((step_name, success))
                if not success:
                    print(f"\n✗ 步骤失败：{step_name}")
                    print("迁移中止")
                    break
            except Exception as e:
                print(f"\n✗ 步骤异常：{step_name}")
                print(f"错误：{e}")
                results.append((step_name, False))
                break

        # 输出总结
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print("\n" + "=" * 70)
        print("迁移总结")
        print("=" * 70)

        for step_name, success in results:
            status = "✓ 成功" if success else "✗ 失败"
            print(f"{status} - {step_name}")

        all_success = all(success for _, success in results)

        if all_success:
            print(f"\n✓ 迁移成功完成！耗时：{duration:.2f}秒")
            if self.backup_file:
                print(f"\n备份文件：{self.backup_file}")
            print("\n下一步：")
            print("1. 测试新的预约系统")
            print("2. 设置定时任务运行 schedule_generator.py")
            print("3. 更新 main.py 使用 AppointmentServiceV3")
        else:
            print(f"\n✗ 迁移失败或未完成，耗时：{duration:.2f}秒")
            if self.backup_file:
                print(f"\n可使用备份文件回滚：{self.backup_file}")

        print("=" * 70)


def main():
    """主函数"""
    migration = DatabaseMigration()
    migration.run_migration()


if __name__ == '__main__':
    main()
