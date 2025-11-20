#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
================================================================================
数据库迁移验证脚本
================================================================================

验证内容:
  1. 系统管理字段是否正确添加
  2. appointment表扩展字段是否存在
  3. UUID字段是否正确添加
  4. 索引是否正确创建
  5. 数据完整性检查

作者: System Migration
日期: 2025-11-20
================================================================================
"""

import sys
from pathlib import Path
from tabulate import tabulate

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.db_connection import DatabaseConnection


class MigrationVerifier:
    """迁移验证器"""

    def __init__(self):
        self.connection = None
        self.cursor = None
        self.errors = []
        self.warnings = []
        self.success = []

    def log_success(self, message):
        self.success.append(f"[OK] {message}")
        print(f"[OK] {message}")

    def log_warning(self, message):
        self.warnings.append(f"[WARNING] {message}")
        print(f"[WARNING] {message}")

    def log_error(self, message):
        self.errors.append(f"[ERROR] {message}")
        print(f"[ERROR] {message}")

    def connect(self):
        """连接数据库"""
        try:
            db = DatabaseConnection()
            self.connection = db.connect()
            self.cursor = self.connection.cursor()
            self.log_success("Database connected successfully")
            return True
        except Exception as e:
            self.log_error(f"Database connection failed: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def verify_system_fields(self):
        """验证系统管理字段"""
        print("\n" + "=" * 80)
        print("1. 验证系统管理字段")
        print("=" * 80)

        required_fields = ['Create_By', 'Update_By', 'Version', 'Deleted']
        tables_to_check = [
            'patient', 'medical_record', 'doctor', 'drugs',
            'prescription', 'prescription_detail', 'appointment',
            'reminder', 'reminder_config', 'reminder_history',
            'doctor_working_schedule', 'doctor_time_slots',
            'doctor_schedule_exceptions', 'biomechanics_scan',
            'chat_conversation', 'chat_message'
        ]

        results = []
        for table in tables_to_check:
            self.cursor.execute(f"""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = '{table}'
                  AND COLUMN_NAME IN ('Create_By', 'Update_By', 'Version', 'Deleted')
            """)
            fields = [row['COLUMN_NAME'] for row in self.cursor.fetchall()]
            field_count = len(fields)

            # reminder表只需要3个字段（没有Create_By）
            expected_count = 3 if table == 'reminder' else 4

            if field_count == expected_count:
                status = "[OK]"
                self.log_success(f"{table}: {field_count}/{expected_count} fields")
            else:
                status = "[ERROR]"
                missing = set(required_fields) - set(fields)
                self.log_error(f"{table}: missing fields {missing}")

            results.append([table, field_count, expected_count, status])

        print("\n表格汇总:")
        print(tabulate(results, headers=["表名", "已有字段", "期望字段", "状态"], tablefmt="grid"))

    def verify_appointment_extension(self):
        """验证appointment表扩展"""
        print("\n" + "=" * 80)
        print("2. 验证appointment表通用日程扩展")
        print("=" * 80)

        required_fields = ['Is_Generic_Event', 'Event_Type', 'Notes']

        self.cursor.execute("""
            SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, COLUMN_COMMENT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'appointment'
              AND COLUMN_NAME IN ('Is_Generic_Event', 'Event_Type', 'Notes')
        """)

        fields = {row['COLUMN_NAME']: row for row in self.cursor.fetchall()}

        results = []
        for field_name in required_fields:
            if field_name in fields:
                field_info = fields[field_name]
                self.log_success(f"{field_name}: {field_info['COLUMN_TYPE']}")
                results.append([
                    field_name,
                    field_info['COLUMN_TYPE'],
                    field_info['COLUMN_DEFAULT'] or 'NULL',
                    "[OK]"
                ])
            else:
                self.log_error(f"{field_name}: 字段不存在")
                results.append([field_name, "-", "-", "[ERROR]"])

        print("\n扩展字段详情:")
        print(tabulate(results, headers=["字段名", "类型", "默认值", "状态"], tablefmt="grid"))

    def verify_uuid_fields(self):
        """验证UUID字段"""
        print("\n" + "=" * 80)
        print("3. 验证UUID字段")
        print("=" * 80)

        self.cursor.execute("""
            SELECT TABLE_NAME, COUNT(*) as uuid_count
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND COLUMN_NAME LIKE '%_UUID'
            GROUP BY TABLE_NAME
            ORDER BY TABLE_NAME
        """)

        results = self.cursor.fetchall()

        if results:
            self.log_success(f"找到 {len(results)} 个表包含UUID字段")
            print("\nUUID字段统计:")
            table_data = [[row['TABLE_NAME'], row['uuid_count']] for row in results]
            print(tabulate(table_data, headers=["表名", "UUID字段数"], tablefmt="grid"))
        else:
            self.log_warning("未找到UUID字段（可能未执行UUID迁移）")

    def verify_indexes(self):
        """验证索引"""
        print("\n" + "=" * 80)
        print("4. 验证索引")
        print("=" * 80)

        # 检查Deleted字段索引
        tables_to_check = [
            'patient', 'medical_record', 'doctor', 'drugs',
            'prescription', 'prescription_detail', 'appointment',
            'reminder', 'reminder_config'
        ]

        results = []
        for table in tables_to_check:
            self.cursor.execute(f"""
                SELECT INDEX_NAME
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = '{table}'
                  AND INDEX_NAME = 'idx_deleted'
            """)
            index_exists = self.cursor.fetchone() is not None

            if index_exists:
                status = "[OK]"
                self.log_success(f"{table}.idx_deleted 存在")
            else:
                status = "[ERROR]"
                self.log_warning(f"{table}.idx_deleted 不存在")

            results.append([table, "idx_deleted", status])

        print("\nDeleted索引检查:")
        print(tabulate(results, headers=["表名", "索引名", "状态"], tablefmt="grid"))

        # 检查appointment表特殊索引
        print("\nappointment表特殊索引:")
        appointment_indexes = ['idx_event_type', 'idx_is_generic', 'idx_deleted']
        results = []

        for index_name in appointment_indexes:
            self.cursor.execute(f"""
                SELECT COUNT(*) as cnt
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'appointment'
                  AND INDEX_NAME = '{index_name}'
            """)
            exists = self.cursor.fetchone()['cnt'] > 0
            status = "[OK]" if exists else "[ERROR]"
            results.append([index_name, status])

            if exists:
                self.log_success(f"appointment.{index_name} 存在")
            else:
                self.log_warning(f"appointment.{index_name} 不存在")

        print(tabulate(results, headers=["索引名", "状态"], tablefmt="grid"))

    def verify_data_integrity(self):
        """验证数据完整性"""
        print("\n" + "=" * 80)
        print("5. 验证数据完整性")
        print("=" * 80)

        # 检查patient表
        self.cursor.execute("""
            SELECT
                COUNT(*) as total_patients,
                SUM(CASE WHEN Deleted = 0 THEN 1 ELSE 0 END) as active_patients,
                SUM(CASE WHEN Deleted = 1 THEN 1 ELSE 0 END) as deleted_patients
            FROM patient
        """)
        patient_stats = self.cursor.fetchone()

        self.log_success(f"患者表: 总数 {patient_stats['total_patients']}, "
                        f"活跃 {patient_stats['active_patients']}, "
                        f"已删除 {patient_stats['deleted_patients']}")

        # 检查appointment表
        self.cursor.execute("""
            SELECT
                COUNT(*) as total_appointments,
                SUM(CASE WHEN Is_Generic_Event = 0 THEN 1 ELSE 0 END) as patient_appointments,
                SUM(CASE WHEN Is_Generic_Event = 1 THEN 1 ELSE 0 END) as generic_events
            FROM appointment
        """)
        appointment_stats = self.cursor.fetchone()

        self.log_success(f"预约表: 总数 {appointment_stats['total_appointments']}, "
                        f"患者预约 {appointment_stats['patient_appointments']}, "
                        f"通用日程 {appointment_stats['generic_events']}")

        # 如果有UUID字段，检查UUID完整性
        self.cursor.execute("""
            SELECT COUNT(*) as cnt
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'patient'
              AND COLUMN_NAME = 'Patient_UUID'
        """)

        if self.cursor.fetchone()['cnt'] > 0:
            self.cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN Patient_UUID IS NOT NULL THEN 1 ELSE 0 END) as with_uuid,
                    SUM(CASE WHEN Patient_UUID IS NULL THEN 1 ELSE 0 END) as without_uuid
                FROM patient
            """)
            uuid_stats = self.cursor.fetchone()

            if uuid_stats['without_uuid'] == 0:
                self.log_success(f"患者UUID完整性: 100% ({uuid_stats['with_uuid']}/{uuid_stats['total']})")
            else:
                self.log_warning(f"患者UUID不完整: {uuid_stats['without_uuid']} 条记录缺少UUID")

    def generate_report(self):
        """生成验证报告"""
        print("\n" + "=" * 80)
        print("验证报告汇总")
        print("=" * 80)

        print(f"\n[OK] 成功: {len(self.success)} 项")
        print(f"[WARNING]  警告: {len(self.warnings)} 项")
        print(f"[ERROR] 错误: {len(self.errors)} 项")

        if self.warnings:
            print("\n警告详情:")
            for warning in self.warnings:
                print(f"  {warning}")

        if self.errors:
            print("\n错误详情:")
            for error in self.errors:
                print(f"  {error}")

        if not self.errors:
            print("\n" + "=" * 80)
            print("[SUCCESS] 迁移验证通过！")
            print("=" * 80)
            return True
        else:
            print("\n" + "=" * 80)
            print("[FAIL] 迁移验证失败，请检查错误")
            print("=" * 80)
            return False

    def run(self):
        """执行验证"""
        print("=" * 80)
        print("数据库迁移验证")
        print("=" * 80)

        if not self.connect():
            return False

        try:
            self.verify_system_fields()
            self.verify_appointment_extension()
            self.verify_uuid_fields()
            self.verify_indexes()
            self.verify_data_integrity()

            return self.generate_report()

        except Exception as e:
            self.log_error(f"验证过程出错: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            self.disconnect()


if __name__ == '__main__':
    try:
        from tabulate import tabulate
    except ImportError:
        print("请先安装 tabulate: pip install tabulate")
        sys.exit(1)

    verifier = MigrationVerifier()
    success = verifier.run()
    sys.exit(0 if success else 1)
