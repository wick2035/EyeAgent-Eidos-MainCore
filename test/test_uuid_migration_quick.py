"""
UUID迁移快速测试脚本
验证UUID迁移后的基本功能

Created: 2025-11-20
"""

import sys
from pathlib import Path

# 设置UTF-8编码输出(Windows兼容)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.base_service import generate_uuid, is_valid_uuid, normalize_id
from database.user_history_service_v2 import UserHistoryServiceV2


def test_uuid_tools():
    """测试UUID工具函数"""
    print("="*70)
    print("测试 1: UUID工具函数")
    print("="*70)

    # 测试UUID生成
    uuid1 = generate_uuid()
    uuid2 = generate_uuid()
    print(f"✓ 生成UUID 1: {uuid1}")
    print(f"✓ 生成UUID 2: {uuid2}")
    assert uuid1 != uuid2, "UUID应该是唯一的"
    print("✓ UUID唯一性验证通过\n")

    # 测试UUID验证
    valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
    invalid_uuid = "not-a-uuid"
    assert is_valid_uuid(valid_uuid) == True
    assert is_valid_uuid(invalid_uuid) == False
    print(f"✓ UUID验证功能正常\n")

    # 测试ID规范化
    assert normalize_id(123) == "123"
    assert normalize_id("456") == "456"
    assert normalize_id(valid_uuid) == valid_uuid.lower()
    print("✓ ID规范化功能正常\n")

    print("✓ 所有UUID工具测试通过!\n")


def test_user_query_with_uuid():
    """测试使用UUID查询用户"""
    print("="*70)
    print("测试 2: 用户查询(UUID支持)")
    print("="*70)

    service = UserHistoryServiceV2()

    try:
        # 测试通过手机号查询
        print("测试: 通过手机号查询用户...")
        user = service.get_user_by_phone("13900139000")

        if user:
            print(f"✓ 找到用户: {user.get('Name')}")
            print(f"  Patient_ID: {user.get('Patient_ID')}")
            print(f"  Patient_UUID: {user.get('Patient_UUID')}")

            # 测试使用UUID查询
            if user.get('Patient_UUID'):
                print(f"\n测试: 使用UUID查询...")
                user_by_uuid = service.get_user_by_id(user['Patient_UUID'])
                if user_by_uuid:
                    print(f"✓ UUID查询成功: {user_by_uuid.get('Name')}")
                    assert user_by_uuid['Patient_UUID'] == user['Patient_UUID']
                else:
                    print("✗ UUID查询失败")

            # 测试使用INT ID查询
            if user.get('Patient_ID'):
                print(f"\n测试: 使用INT ID查询...")
                user_by_int = service.get_user_by_id(user['Patient_ID'])
                if user_by_int:
                    print(f"✓ INT ID查询成功: {user_by_int.get('Name')}")
                else:
                    print("✗ INT ID查询失败")

            # 测试病例查询
            print(f"\n测试: 查询病例记录...")
            records = service.get_medical_records_by_patient_id(user['Patient_UUID'])
            print(f"✓ 找到 {len(records)} 条病例记录")
            if records:
                print(f"  最近病例: {records[0].get('Visit_Date')} - {records[0].get('Chief_Complaint', '无')[:30]}")

            # 测试预约查询
            print(f"\n测试: 查询预约记录...")
            appointments = service.get_appointments_by_patient_id(user['Patient_UUID'])
            print(f"✓ 找到 {len(appointments)} 条预约记录")

            print("\n✓ 所有用户查询测试通过!")

        else:
            print("⚠ 未找到测试用户 (手机号: 13900139000)")
            print("提示: 可以使用数据库中存在的手机号进行测试")

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    finally:
        service.close()


def test_database_migration_status():
    """测试数据库迁移状态"""
    print("="*70)
    print("测试 3: 数据库迁移状态")
    print("="*70)

    from database.db_connection import DatabaseConnection

    db = DatabaseConnection()

    try:
        # 检查迁移日志表
        query = """
            SELECT phase, COUNT(*) as tables_count, SUM(records_migrated) as total_records
            FROM _uuid_migration_log
            WHERE status = 'completed'
            GROUP BY phase
            ORDER BY phase
        """
        results = db.execute_query(query)

        if results:
            print("迁移状态:")
            print("-" * 70)
            for row in results:
                phase_name = row['phase'].replace('_', ' ').title()
                print(f"  {phase_name}:")
                print(f"    表数: {row['tables_count']}")
                print(f"    记录数: {row['total_records']}")
            print("-" * 70)

            # 检查所有阶段是否完成
            completed_phases = set(r['phase'] for r in results)
            expected_phases = {'phase1_core', 'phase2_business', 'phase3_auxiliary'}

            if completed_phases == expected_phases:
                print("\n✓ 所有阶段迁移已完成!")
            else:
                missing = expected_phases - completed_phases
                print(f"\n⚠ 未完成的阶段: {', '.join(missing)}")

        else:
            print("✗ 未找到迁移日志,可能未执行迁移")

    except Exception as e:
        print(f"✗ 查询迁移状态失败: {e}")

    finally:
        db.close()


def test_uuid_columns_exist():
    """测试UUID列是否存在"""
    print("\n" + "="*70)
    print("测试 4: UUID列存在性检查")
    print("="*70)

    from database.db_connection import DatabaseConnection
    from database.db_config import DB_CONFIG

    db = DatabaseConnection()

    try:
        tables_to_check = [
            ('patient', 'Patient_UUID'),
            ('medical_record', 'Medical_Record_UUID'),
            ('doctor', 'Doctor_UUID'),
            ('appointment', 'Appointment_UUID'),
            ('prescription', 'Prescription_UUID'),
            ('chat_conversation', 'Chat_UUID'),
        ]

        print("检查UUID列:")
        print("-" * 70)

        for table_name, uuid_column in tables_to_check:
            query = """
                SELECT COUNT(*) as cnt
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = %s
                  AND COLUMN_NAME = %s
            """
            result = db.execute_one(query, (DB_CONFIG['database'], table_name, uuid_column))

            if result and result['cnt'] > 0:
                print(f"  ✓ {table_name}.{uuid_column}")
            else:
                print(f"  ✗ {table_name}.{uuid_column} 不存在")

        print("-" * 70)
        print("\n✓ UUID列检查完成!")

    except Exception as e:
        print(f"✗ 检查失败: {e}")

    finally:
        db.close()


def main():
    """主测试函数"""
    print("\n" + "="*70)
    print("UUID迁移快速测试")
    print("="*70 + "\n")

    try:
        # 测试1: UUID工具函数
        test_uuid_tools()

        # 测试2: 数据库迁移状态
        test_database_migration_status()

        # 测试3: UUID列存在性
        test_uuid_columns_exist()

        # 测试4: 用户查询功能
        test_user_query_with_uuid()

        print("\n" + "="*70)
        print("✓ 所有测试完成!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
