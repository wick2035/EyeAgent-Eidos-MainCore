"""
数据库完整初始化脚本执行器
整合版本: 执行 database_init_complete.sql
包含: V3核心表 + 聊天历史 + 提醒功能 + 生物力学检查

使用方法:
    python database/execute_database_init.py

注意事项:
    1. 确保MySQL服务正在运行
    2. 确保db_config.py中的数据库配置正确
    3. 此脚本会删除并重建所有表,请谨慎使用
"""

import pymysql
import os
import sys
from pathlib import Path

# 添加父目录到路径以导入db_config
sys.path.insert(0, str(Path(__file__).parent))
from db_config import DB_CONFIG


def execute_sql_file(filepath: str, verbose: bool = True):
    """
    执行SQL文件

    Args:
        filepath: SQL文件路径
        verbose: 是否显示详细执行信息
    """
    # 连接到MySQL(不指定数据库)
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

        # 分割SQL语句
        sql_statements = []
        current_statement = []
        in_delimiter = False
        delimiter = ';'

        for line in sql_content.split('\n'):
            # 处理DELIMITER声明
            if line.strip().upper().startswith('DELIMITER'):
                delimiter = line.strip().split()[-1]
                in_delimiter = (delimiter != ';')
                continue

            # 跳过空行和纯注释行
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith('--'):
                continue

            current_statement.append(line)

            # 检查语句是否结束
            if stripped_line.endswith(delimiter):
                sql = '\n'.join(current_statement)
                # 移除末尾的delimiter
                sql = sql.rstrip(delimiter).strip()
                if sql:
                    sql_statements.append(sql)
                current_statement = []

        # 执行所有SQL语句
        total = len(sql_statements)
        success_count = 0
        error_count = 0

        for i, sql in enumerate(sql_statements, 1):
            try:
                # 跳过空语句
                if not sql.strip():
                    continue

                if verbose:
                    # 显示前50个字符作为预览
                    preview = sql[:80].replace('\n', ' ')
                    print(f"[{i}/{total}] 执行: {preview}...")

                cursor.execute(sql)
                conn.commit()
                success_count += 1

                if verbose:
                    print(f"  [✓] 成功")

            except Exception as e:
                error_count += 1
                print(f"  [✗] 失败: {e}")
                # 继续执行其他语句

        print("\n" + "=" * 60)
        print(f"数据库初始化完成！")
        print(f"成功: {success_count} 条语句")
        print(f"失败: {error_count} 条语句")
        print("=" * 60)

        # 显示统计信息
        try:
            cursor.execute("USE medical_db")

            tables_stats = [
                ("patient", "患者"),
                ("doctor", "医生"),
                ("medical_record", "病例"),
                ("appointment", "预约"),
                ("prescription", "处方"),
                ("drugs", "药品"),
                ("doctor_working_schedule", "医生排班规则"),
                ("biomechanics_scan", "生物力学检查"),
                ("chat_conversation", "聊天对话"),
                ("reminder", "提醒记录")
            ]

            print("\n数据统计:")
            print("-" * 60)
            for table, name in tables_stats:
                try:
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"{name}数量: {count}")
                except:
                    print(f"{name}数量: 表不存在")
            print("-" * 60)

        except Exception as e:
            print(f"\n统计信息获取失败: {e}")

    except Exception as e:
        print(f"\n致命错误: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def check_database_config():
    """检查数据库配置是否正确"""
    print("检查数据库配置...")
    print(f"  主机: {DB_CONFIG['host']}")
    print(f"  端口: {DB_CONFIG['port']}")
    print(f"  用户: {DB_CONFIG['user']}")
    print(f"  数据库: {DB_CONFIG['database']}")

    # 测试连接
    try:
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            charset='utf8mb4'
        )
        conn.close()
        print("  [✓] 数据库连接测试成功\n")
        return True
    except Exception as e:
        print(f"  [✗] 数据库连接失败: {e}\n")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("医疗数据库完整初始化")
    print("=" * 60)
    print()

    # 检查配置
    if not check_database_config():
        print("请检查 db_config.py 中的数据库配置")
        sys.exit(1)

    # 确认操作
    print("警告: 此操作将删除并重建所有数据库表!")
    confirm = input("确定要继续吗? (yes/no): ")

    if confirm.lower() not in ['yes', 'y', '是']:
        print("操作已取消")
        sys.exit(0)

    # 获取SQL文件路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sql_file = os.path.join(script_dir, 'database_init_complete.sql')

    if not os.path.exists(sql_file):
        print(f"错误: SQL文件不存在: {sql_file}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("开始执行数据库初始化...")
    print("=" * 60)
    print()

    # 执行SQL文件
    execute_sql_file(sql_file, verbose=True)

    print()
    print("=" * 60)
    print("初始化完成！")
    print("=" * 60)
    print("\n下一步:")
    print("  1. 运行 utils/schedule_generator.py 生成医生时间段")
    print("  2. 启动应用: python main.py")
    print()
