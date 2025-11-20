#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动添加系统管理字段脚本
检查每个表，只添加不存在的字段
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.db_connection import DatabaseConnection


def add_system_fields():
    """为所有表添加系统管理字段"""

    db = DatabaseConnection()
    connection = db.connect()
    cursor = connection.cursor()

    # 定义需要添加字段的表和字段配置
    tables_config = {
        'patient': ['Create_By', 'Update_By', 'Version', 'Deleted'],
        'medical_record': ['Create_By', 'Update_By', 'Version', 'Deleted'],
        'doctor': ['Create_By', 'Update_By', 'Version', 'Deleted'],
        'drugs': ['Create_By', 'Update_By', 'Version', 'Deleted'],
        'prescription': ['Create_By', 'Update_By', 'Version', 'Deleted'],
        'prescription_detail': ['Updated_At', 'Create_By', 'Update_By', 'Version', 'Deleted'],
        'appointment': ['Create_By', 'Update_By', 'Version', 'Deleted', 'Is_Generic_Event', 'Event_Type', 'Notes'],
        'reminder_config': ['Create_By', 'Update_By', 'Version', 'Deleted'],
        'reminder': ['Update_By', 'Version', 'Deleted'],  # 注意：reminder没有Create_By
        'reminder_history': ['Create_Time', 'Create_By', 'Update_Time', 'Update_By', 'Version', 'Deleted'],
        'doctor_working_schedule': ['Create_By', 'Update_By', 'Version', 'Deleted'],
        'doctor_time_slots': ['Create_By', 'Update_By', 'Version', 'Deleted'],
        'doctor_schedule_exceptions': ['Create_By', 'Update_By', 'Version', 'Deleted'],
        'biomechanics_scan': ['Create_By', 'Update_By', 'Version', 'Deleted'],
        'chat_conversation': ['Create_By', 'Update_By', 'Version', 'Deleted'],
        'chat_message': ['Create_By', 'Update_By', 'Version', 'Deleted'],
    }

    # 字段定义
    field_definitions = {
        'Create_By': "VARCHAR(36) COMMENT '创建人UUID'",
        'Update_By': "VARCHAR(36) COMMENT '更新人UUID'",
        'Version': "INT DEFAULT 0 COMMENT '乐观锁版本号'",
        'Deleted': "TINYINT DEFAULT 0 COMMENT '逻辑删除标记'",
        'Updated_At': "TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
        'Is_Generic_Event': "BOOLEAN DEFAULT FALSE COMMENT '是否为通用日程事件'",
        'Event_Type': "VARCHAR(50) DEFAULT 'appointment' COMMENT '事件类型'",
        'Notes': "TEXT COMMENT '日程备注'",
        'Create_Time': "DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'",
        'Update_Time': "DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
    }

    # 索引定义
    indexes_to_add = {
        'patient': ['idx_deleted'],
        'medical_record': ['idx_deleted'],
        'doctor': ['idx_deleted'],
        'drugs': ['idx_deleted'],
        'prescription': ['idx_deleted'],
        'prescription_detail': ['idx_deleted'],
        'appointment': ['idx_deleted', 'idx_event_type', 'idx_is_generic'],
        'reminder': ['idx_deleted'],
        'reminder_config': ['idx_deleted'],
        'reminder_history': ['idx_deleted'],
        'doctor_working_schedule': ['idx_deleted'],
        'doctor_time_slots': ['idx_deleted'],
        'doctor_schedule_exceptions': ['idx_deleted'],
        'biomechanics_scan': ['idx_deleted'],
        'chat_conversation': ['idx_deleted'],
        'chat_message': ['idx_deleted'],
    }

    index_definitions = {
        'idx_deleted': '(Deleted)',
        'idx_event_type': '(Event_Type)',
        'idx_is_generic': '(Is_Generic_Event)',
    }

    print("=" * 80)
    print("开始添加系统管理字段")
    print("=" * 80)

    total_fields_added = 0
    total_indexes_added = 0

    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

        # 处理每个表
        for table_name, fields in tables_config.items():
            print(f"\n处理表: {table_name}")

            # 检查表是否存在
            cursor.execute(f"""
                SELECT COUNT(*) as cnt FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = 'medical_db' AND TABLE_NAME = '{table_name}'
            """)
            if cursor.fetchone()['cnt'] == 0:
                print(f"  ⚠️  表 {table_name} 不存在，跳过")
                continue

            # 添加字段
            for field_name in fields:
                # 检查字段是否存在
                cursor.execute(f"""
                    SELECT COUNT(*) as cnt FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = 'medical_db'
                    AND TABLE_NAME = '{table_name}'
                    AND COLUMN_NAME = '{field_name}'
                """)

                if cursor.fetchone()['cnt'] == 0:
                    # 字段不存在，添加
                    field_def = field_definitions[field_name]
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {field_name} {field_def}"
                    try:
                        cursor.execute(sql)
                        print(f"  [OK] Added field: {field_name}")
                        total_fields_added += 1
                    except Exception as e:
                        print(f"  [ERROR] Failed to add field {field_name}: {e}")
                else:
                    print(f"  [SKIP] Field already exists: {field_name}")

            # 添加索引
            if table_name in indexes_to_add:
                for index_name in indexes_to_add[table_name]:
                    # 检查索引是否存在
                    cursor.execute(f"""
                        SELECT COUNT(*) as cnt FROM INFORMATION_SCHEMA.STATISTICS
                        WHERE TABLE_SCHEMA = 'medical_db'
                        AND TABLE_NAME = '{table_name}'
                        AND INDEX_NAME = '{index_name}'
                    """)

                    if cursor.fetchone()['cnt'] == 0:
                        # 索引不存在，添加
                        index_def = index_definitions[index_name]
                        sql = f"ALTER TABLE {table_name} ADD INDEX {index_name} {index_def}"
                        try:
                            cursor.execute(sql)
                            print(f"  [OK] Added index: {index_name}")
                            total_indexes_added += 1
                        except Exception as e:
                            print(f"  [ERROR] Failed to add index {index_name}: {e}")
                    else:
                        print(f"  [SKIP] Index already exists: {index_name}")

        connection.commit()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        print("\n" + "=" * 80)
        print("[SUCCESS] Migration completed!")
        print("=" * 80)
        print(f"Fields added: {total_fields_added}")
        print(f"Indexes added: {total_indexes_added}")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        connection.rollback()
        import traceback
        traceback.print_exc()
        return False

    finally:
        cursor.close()
        connection.close()


if __name__ == '__main__':
    success = add_system_fields()
    sys.exit(0 if success else 1)
