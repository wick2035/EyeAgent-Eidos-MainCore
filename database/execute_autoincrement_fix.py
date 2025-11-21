"""
执行AUTO_INCREMENT修复脚本
修复 chat_message, chat_conversation, appointment 表的主键AUTO_INCREMENT问题

使用方法:
    python database/execute_autoincrement_fix.py
"""

import pymysql
import os
import sys
from pathlib import Path

# 添加父目录到路径以导入db_config
sys.path.insert(0, str(Path(__file__).parent))
from db_config import DB_CONFIG


def execute_sql_file(filepath: str):
    """执行SQL文件"""
    # 连接到MySQL
    conn = pymysql.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database'],
        charset='utf8mb4'
    )

    try:
        cursor = conn.cursor()

        # 读取SQL文件
        with open(filepath, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 分割SQL语句
        sql_statements = []
        current_statement = []

        for line in sql_content.split('\n'):
            # 跳过空行和纯注释行
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith('--') or stripped_line.startswith('/*') or stripped_line.startswith('*/') or stripped_line.startswith('*'):
                continue

            current_statement.append(line)

            # 检查语句是否结束
            if stripped_line.endswith(';'):
                sql = '\n'.join(current_statement)
                # 移除末尾的分号
                sql = sql.rstrip(';').strip()
                if sql and not sql.startswith('/*'):
                    sql_statements.append(sql)
                current_statement = []

        # 执行所有SQL语句
        print("开始执行AUTO_INCREMENT修复...")
        print("=" * 60)

        for i, sql in enumerate(sql_statements, 1):
            try:
                # 跳过空语句和注释
                if not sql.strip() or sql.strip().startswith('--'):
                    continue

                # 显示正在执行的语句
                preview = sql[:100].replace('\n', ' ')
                print(f"[{i}] {preview}...")

                cursor.execute(sql)
                conn.commit()
                print(f"    [OK] 成功")

            except Exception as e:
                # 某些语句可能失败是正常的(比如SHOW CREATE TABLE)
                if "SHOW" not in sql.upper() and "SELECT" not in sql.upper():
                    print(f"    [FAIL] 失败: {e}")

        print("=" * 60)
        print("修复完成！")
        print()

        # 验证修复结果
        print("验证修复结果:")
        print("-" * 60)

        # 检查 chat_message
        cursor.execute("""
            SELECT COLUMN_NAME, COLUMN_TYPE, EXTRA
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'chat_message'
              AND COLUMN_NAME = 'Message_ID'
        """, (DB_CONFIG['database'],))
        result = cursor.fetchone()
        if result:
            print(f"chat_message.Message_ID: {result[1]} {result[2]}")
            if 'auto_increment' in result[2].lower():
                print("  [OK] AUTO_INCREMENT 已设置")
            else:
                print("  [WARNING] AUTO_INCREMENT 未设置")

        # 检查 chat_conversation
        cursor.execute("""
            SELECT COLUMN_NAME, COLUMN_TYPE, EXTRA
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'chat_conversation'
              AND COLUMN_NAME = 'Chat_ID'
        """, (DB_CONFIG['database'],))
        result = cursor.fetchone()
        if result:
            print(f"chat_conversation.Chat_ID: {result[1]} {result[2]}")
            if 'auto_increment' in result[2].lower():
                print("  [OK] AUTO_INCREMENT 已设置")
            else:
                print("  [WARNING] AUTO_INCREMENT 未设置")

        # 检查 appointment
        cursor.execute("""
            SELECT COLUMN_NAME, COLUMN_TYPE, EXTRA
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'appointment'
              AND COLUMN_NAME = 'Appointment_ID'
        """, (DB_CONFIG['database'],))
        result = cursor.fetchone()
        if result:
            print(f"appointment.Appointment_ID: {result[1]} {result[2]}")
            if 'auto_increment' in result[2].lower():
                print("  [OK] AUTO_INCREMENT 已设置")
            else:
                print("  [WARNING] AUTO_INCREMENT 未设置")

        print("-" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("AUTO_INCREMENT修复工具")
    print("=" * 60)
    print()

    # 获取SQL文件路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sql_file = os.path.join(script_dir, 'fix_chat_id_autoincrement.sql')

    if not os.path.exists(sql_file):
        print(f"错误: SQL文件不存在: {sql_file}")
        sys.exit(1)

    # 执行SQL文件
    try:
        execute_sql_file(sql_file)
        print()
        print("修复成功！现在可以正常保存聊天消息了。")
    except Exception as e:
        print(f"\n修复失败: {e}")
        sys.exit(1)
