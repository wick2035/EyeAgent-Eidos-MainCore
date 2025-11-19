"""
执行对话历史记录表初始化脚本
用途: 创建 chat_conversation 和 chat_message 表
"""
import pymysql
from db_config import DB_CONFIG


def execute_sql_file(filepath: str):
    """执行SQL文件"""
    # 连接到MySQL（指定数据库）
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

        # 分割SQL语句（按分号分隔）
        sql_statements = []
        current_statement = []

        for line in sql_content.split('\n'):
            # 跳过注释和空行
            line = line.strip()
            if not line or line.startswith('--'):
                continue

            current_statement.append(line)

            # 如果行以分号结尾，表示一个完整语句
            if line.endswith(';'):
                sql = ' '.join(current_statement)
                sql_statements.append(sql)
                current_statement = []

        # 执行所有SQL语句
        for i, sql in enumerate(sql_statements, 1):
            try:
                print(f"[{i}/{len(sql_statements)}] 执行: {sql[:80]}...")
                cursor.execute(sql)
                conn.commit()
                print(f"  ✓ 成功")
            except Exception as e:
                print(f"  ✗ 失败: {e}")
                # 继续执行其他语句

        print("\n" + "=" * 60)
        print("对话历史记录表初始化完成！")
        print("=" * 60)

        # 显示表结构信息
        try:
            cursor.execute("SHOW TABLES LIKE 'chat_%'")
            tables = cursor.fetchall()
            print(f"\n已创建的表: {len(tables)}")
            for table in tables:
                table_name = table[0]
                print(f"  - {table_name}")

                # 显示表的字段信息
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                print(f"    字段数量: {len(columns)}")
                for col in columns[:5]:  # 只显示前5个字段
                    print(f"      • {col[0]} ({col[1]})")
                if len(columns) > 5:
                    print(f"      ... 及其他 {len(columns) - 5} 个字段")
                print()

        except Exception as e:
            print(f"显示表信息时出错: {e}")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sql_file = os.path.join(script_dir, 'chat_history_table.sql')

    print("=" * 60)
    print("开始执行对话历史记录表初始化脚本")
    print("=" * 60)
    print(f"SQL文件: {sql_file}\n")

    if not os.path.exists(sql_file):
        print(f"错误: SQL文件不存在: {sql_file}")
        exit(1)

    try:
        execute_sql_file(sql_file)
        print("\n执行完成! 可以开始使用 chat_service.py 进行数据操作。")
    except Exception as e:
        print(f"\n执行失败: {e}")
        exit(1)
