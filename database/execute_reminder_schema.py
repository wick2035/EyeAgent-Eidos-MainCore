"""
执行提醒功能数据库扩展脚本
创建 reminder、reminder_history、reminder_config 表及相关触发器
"""
import pymysql
from db_config import DB_CONFIG


def execute_sql_file(filepath: str):
    """执行包含触发器的SQL文件"""
    # 连接到MySQL
    conn = pymysql.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        charset='utf8mb4'
    )

    try:
        cursor = conn.cursor()

        # 读取SQL文件
        with open(filepath, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 处理DELIMITER语句
        statements = []
        current_delimiter = ';'
        current_statement = []
        in_delimiter_block = False

        lines = sql_content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 检查DELIMITER命令
            if line.upper().startswith('DELIMITER'):
                parts = line.split()
                if len(parts) > 1:
                    new_delimiter = parts[1]
                    if new_delimiter == '$$':
                        in_delimiter_block = True
                        current_delimiter = '$$'
                    else:
                        in_delimiter_block = False
                        current_delimiter = ';'
                i += 1
                continue

            # 跳过空行和注释
            if not line or line.startswith('--'):
                i += 1
                continue

            # 累积当前语句
            current_statement.append(line)

            # 检查是否到达语句结束
            if line.endswith(current_delimiter):
                stmt = ' '.join(current_statement)
                # 移除末尾的分隔符
                if current_delimiter == '$$':
                    stmt = stmt[:-2].strip()
                else:
                    stmt = stmt[:-1].strip()

                if stmt:
                    statements.append(stmt)
                current_statement = []

            i += 1

        # 执行所有SQL语句
        print(f"准备执行 {len(statements)} 条SQL语句...")
        print("=" * 70)

        for idx, sql in enumerate(statements, 1):
            try:
                # 显示简短预览
                preview = sql[:80].replace('\n', ' ')
                if len(sql) > 80:
                    preview += "..."
                print(f"\n[{idx}/{len(statements)}] {preview}")

                cursor.execute(sql)
                conn.commit()
                print(f"  [OK] 执行成功")

            except Exception as e:
                print(f"  [ERROR] 执行失败: {e}")
                # 对于某些错误（如表已存在），继续执行
                if "already exists" in str(e) or "Duplicate" in str(e):
                    print(f"  → 跳过并继续...")
                    continue

        print("\n" + "=" * 70)
        print("数据库扩展完成！\n")

        # 显示统计信息
        cursor.execute("USE medical_db")

        # 检查新表是否创建成功
        tables_to_check = ['reminder', 'reminder_history', 'reminder_config']
        for table in tables_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"[OK] {table} 表: {count} 条记录")
            except Exception as e:
                print(f"[X] {table} 表: 不存在或查询失败")

        # 检查触发器
        try:
            cursor.execute("SHOW TRIGGERS FROM medical_db LIKE 'patient'")
            triggers = cursor.fetchall()
            print(f"\n[OK] 触发器数量: {len(triggers)}")
            for trigger in triggers:
                print(f"  - {trigger[0]}")
        except Exception as e:
            print(f"[X] 触发器检查失败: {e}")

        print("\n初始化完成！提醒功能已就绪。")

    except Exception as e:
        print(f"\n执行过程中发生错误: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    import os

    script_dir = os.path.dirname(os.path.abspath(__file__))
    sql_file = os.path.join(script_dir, 'reminder_schema.sql')

    print("=" * 70)
    print("开始执行提醒功能数据库扩展脚本")
    print("=" * 70)
    print(f"SQL文件: {sql_file}\n")

    if not os.path.exists(sql_file):
        print(f"错误: 找不到SQL文件 {sql_file}")
        exit(1)

    execute_sql_file(sql_file)
