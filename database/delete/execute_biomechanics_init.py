"""
执行生物力学检查表初始化脚本
创建biomechanics_scan表并插入演示数据
"""
import mysql.connector
from database.db_config import DB_CONFIG


def execute_biomechanics_init():
    """执行生物力学表创建脚本"""
    try:
        # 连接数据库
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        print("=" * 60)
        print("开始执行生物力学检查表初始化...")
        print("=" * 60)

        # 读取SQL脚本
        with open('database/biomechanics_table.sql', 'r', encoding='utf-8') as file:
            sql_script = file.read()

        # 分割SQL语句（按分号分割）
        sql_statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]

        # 执行每条SQL语句
        for i, statement in enumerate(sql_statements, 1):
            if statement:
                try:
                    # 跳过注释行
                    if statement.strip().startswith('--'):
                        continue

                    cursor.execute(statement)

                    # 如果是SELECT语句，显示结果
                    if statement.strip().upper().startswith('SELECT'):
                        results = cursor.fetchall()
                        for row in results:
                            print(f"  {row}")

                except mysql.connector.Error as err:
                    print(f"[警告] SQL语句 {i} 执行失败: {err}")
                    print(f"  语句内容: {statement[:100]}...")
                    continue

        # 提交事务
        connection.commit()

        print("\n" + "=" * 60)
        print("生物力学检查表初始化完成！")
        print("=" * 60)

        # 验证表是否创建成功
        cursor.execute("SHOW TABLES LIKE 'biomechanics_scan'")
        result = cursor.fetchone()
        if result:
            print(f"\n[OK] 表 'biomechanics_scan' 创建成功")

            # 查询表结构
            cursor.execute("DESCRIBE biomechanics_scan")
            columns = cursor.fetchall()
            print(f"[OK] 表包含 {len(columns)} 个字段")

            # 查询数据条数
            cursor.execute("SELECT COUNT(*) FROM biomechanics_scan")
            count = cursor.fetchone()[0]
            print(f"[OK] 已插入 {count} 条演示数据")

            # 显示演示数据摘要
            print("\n演示数据摘要:")
            cursor.execute("""
                SELECT Scan_ID, Patient_Name, Gender, Age, Scan_Date,
                       Operator, Report_Status, Report_Type
                FROM biomechanics_scan
                ORDER BY Scan_Date DESC
            """)
            results = cursor.fetchall()
            print(f"{'ID':<5} {'姓名':<10} {'性别':<6} {'年龄':<6} {'检查日期':<12} {'操作员':<10} {'状态':<10} {'类型':<10}")
            print("-" * 80)
            for row in results:
                scan_id, name, gender, age, scan_date, operator, status, report_type = row
                print(f"{scan_id:<5} {name:<10} {gender:<6} {age:<6} {str(scan_date):<12} {operator:<10} {status:<10} {report_type or '基础':<10}")
        else:
            print("[ERROR] 表创建失败")

    except mysql.connector.Error as err:
        print(f"[ERROR] 数据库错误: {err}")
        return False

    except FileNotFoundError:
        print("[ERROR] 找不到SQL脚本文件: database/biomechanics_table.sql")
        return False

    except Exception as e:
        print(f"[ERROR] 未知错误: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
            print("\n数据库连接已关闭")

    return True


if __name__ == "__main__":
    execute_biomechanics_init()
