"""
执行触发器修复脚本
"""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def execute_sql_file(filepath):
    """执行SQL文件"""
    conn = pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '3306')),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME', 'medical_db'),
        charset='utf8mb4'
    )

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 分割SQL语句(按DELIMITER分隔)
        statements = []
        current_delimiter = ';'
        current_statement = []

        for line in sql_content.split('\n'):
            line = line.strip()

            # 跳过注释和空行
            if not line or line.startswith('--'):
                continue

            # 处理DELIMITER指令
            if line.startswith('DELIMITER'):
                if current_statement:
                    statements.append('\n'.join(current_statement))
                    current_statement = []
                current_delimiter = line.split()[1]
                continue

            current_statement.append(line)

            # 检查语句结束
            if line.endswith(current_delimiter):
                stmt = '\n'.join(current_statement).rstrip(current_delimiter)
                if stmt.strip():
                    statements.append(stmt)
                current_statement = []

        # 执行SQL语句
        cursor = conn.cursor()
        for i, stmt in enumerate(statements):
            if stmt.strip():
                print(f"执行语句 {i+1}: {stmt[:50]}...")
                try:
                    cursor.execute(stmt)
                    conn.commit()
                    print(f"  [OK] Success")
                except Exception as e:
                    print(f"  [ERROR] Failed: {e}")

        # 验证触发器
        cursor.execute("SHOW TRIGGERS WHERE `Table` = 'appointment'")
        triggers = cursor.fetchall()
        print(f"\n当前appointment表触发器:")
        for t in triggers:
            print(f"  - {t[0]}")

        cursor.close()
        print("\n[SUCCESS] Trigger fix completed!")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    execute_sql_file("database/fix_appointment_triggers.sql")
