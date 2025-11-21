#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
执行主键切换到UUID的迁移脚本
将 appointment 和 chat_conversation 的主键从 INT 改为 UUID
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.db_connection import DatabaseConnection


def backup_database():
    """备份数据库"""
    print("=" * 80)
    print("步骤 1: 备份数据库")
    print("=" * 80)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(__file__).parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup_file = backup_dir / f"medical_db_before_pk_switch_{timestamp}.sql"

    try:
        # 使用 mysqldump 备份
        import subprocess
        from dotenv import load_dotenv

        load_dotenv()

        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '3306')
        user = os.getenv('DB_USER', 'root')
        password = os.getenv('DB_PASSWORD', '')
        database = os.getenv('DB_NAME', 'medical_db')

        cmd = [
            'mysqldump',
            f'--host={host}',
            f'--port={port}',
            f'--user={user}',
            f'--password={password}',
            '--single-transaction',
            '--routines',
            '--triggers',
            '--events',
            database
        ]

        print(f"备份文件: {backup_file}")
        print("正在备份...")

        with open(backup_file, 'w', encoding='utf8') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)

        if result.returncode == 0:
            print(f"[OK] 数据库备份成功: {backup_file}")
            return True
        else:
            print(f"[X] 备份失败: {result.stderr}")
            return False

    except Exception as e:
        print(f"[X] 备份过程出错: {e}")
        print("[警告] 建议手动备份数据库后再继续!")
        return False


def execute_migration():
    """执行迁移脚本"""
    print("\n" + "=" * 80)
    print("步骤 2: 执行主键切换迁移")
    print("=" * 80)

    sql_file = Path(__file__).parent / "migrations" / "switch_primary_key_to_uuid.sql"

    if not sql_file.exists():
        print(f"[X] 迁移文件不存在: {sql_file}")
        return False

    db = DatabaseConnection()
    connection = db.connect()
    cursor = connection.cursor()

    try:
        # 读取SQL文件
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 分割SQL语句 (处理 DELIMITER)
        statements = []
        current_statement = []
        delimiter = ';'
        in_block_comment = False

        for line in sql_content.split('\n'):
            line = line.strip()

            # 处理块注释开始
            if line.startswith('/*'):
                in_block_comment = True
                continue

            # 处理块注释结束
            if '*/' in line:
                in_block_comment = False
                continue

            # 跳过块注释中的内容
            if in_block_comment:
                continue

            # 跳过单行注释和空行
            if not line or line.startswith('--'):
                continue

            # 跳过装饰线 (=====)
            if line.startswith('===') or line == '=' * len(line):
                continue

            # 处理 DELIMITER 指令
            if line.upper().startswith('DELIMITER'):
                if 'DELIMITER //' in line.upper():
                    delimiter = '//'
                elif 'DELIMITER ;' in line.upper():
                    delimiter = ';'
                continue

            # 累积当前语句
            current_statement.append(line)

            # 检查语句是否结束
            if line.endswith(delimiter):
                stmt = ' '.join(current_statement).rstrip(delimiter).strip()
                if stmt and not stmt.startswith('SELECT') or 'FROM' in stmt.upper():
                    # 排除纯提示性的 SELECT 语句 (如 SELECT '=== message ===' AS message)
                    if not (stmt.upper().startswith('SELECT') and 'FROM' not in stmt.upper() and 'AS message' in stmt.lower()):
                        statements.append(stmt)
                    elif 'FROM' in stmt.upper():
                        statements.append(stmt)
                current_statement = []

        # 处理最后一个语句
        if current_statement:
            stmt = ' '.join(current_statement).strip()
            if stmt and ('FROM' in stmt.upper() or not stmt.upper().startswith('SELECT')):
                statements.append(stmt)

        print(f"共 {len(statements)} 条SQL语句待执行\n")

        # 执行每条语句
        executed = 0
        for i, statement in enumerate(statements, 1):
            # 跳过提示性SELECT语句
            if statement.upper().startswith('SELECT') and 'FROM' not in statement.upper():
                continue

            # 执行语句
            try:
                cursor.execute(statement)
                connection.commit()
                executed += 1

                # 显示重要操作的结果
                if any(keyword in statement.upper() for keyword in ['ALTER TABLE', 'CREATE TRIGGER', 'DROP TRIGGER', 'UPDATE']):
                    print(f"[{executed}] [OK] {statement[:100]}...")

            except Exception as e:
                # 忽略一些非关键错误
                error_msg = str(e).lower()
                if "doesn't exist" in error_msg or "unknown" in error_msg:
                    print(f"[{i}/{len(statements)}] [SKIP] 跳过: {statement[:80]}... (错误: {e})")
                    continue
                else:
                    print(f"[{i}/{len(statements)}] [X] 失败: {statement[:100]}...")
                    print(f"   错误: {e}")
                    raise

        print("\n[OK] 所有迁移语句执行完成!")
        return True

    except Exception as e:
        print(f"\n[X] 迁移执行失败: {e}")
        connection.rollback()
        import traceback
        traceback.print_exc()
        return False

    finally:
        cursor.close()
        connection.close()


def verify_migration():
    """验证迁移结果"""
    print("\n" + "=" * 80)
    print("步骤 3: 验证迁移结果")
    print("=" * 80)

    db = DatabaseConnection()

    # 检查 chat_conversation 主键
    result = db.execute_query("""
        SELECT
            COLUMN_NAME,
            COLUMN_KEY,
            COLUMN_TYPE,
            EXTRA
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'medical_db'
          AND TABLE_NAME = 'chat_conversation'
          AND COLUMN_NAME IN ('Chat_ID', 'Chat_UUID')
        ORDER BY ORDINAL_POSITION
    """)

    print("\n[chat_conversation table]")
    for row in result:
        print(f"  {row['COLUMN_NAME']:20} | Key: {row['COLUMN_KEY']:4} | Type: {row['COLUMN_TYPE']:15} | {row['EXTRA']}")

    # 检查 appointment 主键
    result = db.execute_query("""
        SELECT
            COLUMN_NAME,
            COLUMN_KEY,
            COLUMN_TYPE,
            EXTRA
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'medical_db'
          AND TABLE_NAME = 'appointment'
          AND COLUMN_NAME IN ('Appointment_ID', 'Appointment_UUID')
        ORDER BY ORDINAL_POSITION
    """)

    print("\n[appointment table]")
    for row in result:
        print(f"  {row['COLUMN_NAME']:20} | Key: {row['COLUMN_KEY']:4} | Type: {row['COLUMN_TYPE']:15} | {row['EXTRA']}")

    # 检查外键约束
    result = db.execute_query("""
        SELECT
            TABLE_NAME,
            CONSTRAINT_NAME,
            COLUMN_NAME,
            REFERENCED_TABLE_NAME,
            REFERENCED_COLUMN_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = 'medical_db'
          AND REFERENCED_TABLE_NAME IN ('chat_conversation', 'appointment')
          AND CONSTRAINT_NAME != 'PRIMARY'
        ORDER BY TABLE_NAME, CONSTRAINT_NAME
    """)

    print("\n[Foreign Keys]")
    for row in result:
        print(f"  {row['TABLE_NAME']:20} | {row['COLUMN_NAME']:25} -> {row['REFERENCED_TABLE_NAME']}.{row['REFERENCED_COLUMN_NAME']}")

    db.close()

    print("\n[OK] Verification complete!")


def main():
    """主函数"""
    # 设置 Windows 控制台 UTF-8 编码
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("\n" + "=" * 80)
    print("主键切换迁移: INT ID -> UUID")
    print("=" * 80)
    print("\n[警告] 这是一个重要的数据库结构变更!")
    print("   - 将会修改 appointment 和 chat_conversation 表的主键")
    print("   - 会影响外键关联关系")
    print("   - 迁移后需要更新应用代码")
    print("\n" + "=" * 80)

    # 确认继续
    response = input("\n是否继续执行迁移? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("[X] 迁移已取消")
        return

    # 步骤1: 备份
    if not backup_database():
        response = input("\n[警告] 备份失败，是否仍要继续? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("[X] 迁移已取消")
            return

    # 步骤2: 执行迁移
    if not execute_migration():
        print("\n[X] 迁移失败，请检查错误信息")
        print("   可以使用备份文件恢复数据库")
        sys.exit(1)

    # 步骤3: 验证
    verify_migration()

    print("\n" + "=" * 80)
    print("[OK] 迁移完成!")
    print("=" * 80)
    print("\n后续步骤:")
    print("  1. 测试应用功能，确保一切正常")
    print("  2. 代码已经使用 UUID，无需额外修改")
    print("  3. Chat_ID 和 Appointment_ID 保留用于向后兼容")
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
