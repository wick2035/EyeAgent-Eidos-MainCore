"""
执行数据库初始化脚本V2
"""
import pymysql
from db_config import DB_CONFIG

def execute_sql_file(filepath: str):
    """执行SQL文件"""
    # 连接到MySQL（不指定数据库）
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
                print(f"[{i}/{len(sql_statements)}] 执行: {sql[:50]}...")
                cursor.execute(sql)
                conn.commit()
                print(f"  [OK] 成功")
            except Exception as e:
                print(f"  [ERROR] 失败: {e}")
                # 继续执行其他语句
        
        print("\n数据库初始化完成！")
        
        # 显示统计信息
        cursor.execute("USE medical_db")
        cursor.execute("SELECT COUNT(*) as count FROM patient")
        patient_count = cursor.fetchone()[0]
        print(f"用户数量: {patient_count}")
        
        cursor.execute("SELECT COUNT(*) as count FROM medical_record")
        record_count = cursor.fetchone()[0]
        print(f"病例数量: {record_count}")
        
        cursor.execute("SELECT COUNT(*) as count FROM appointment")
        appointment_count = cursor.fetchone()[0]
        print(f"预约数量: {appointment_count}")
        
        cursor.execute("SELECT COUNT(*) as count FROM doctor")
        doctor_count = cursor.fetchone()[0]
        print(f"医生数量: {doctor_count}")
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sql_file = os.path.join(script_dir, 'init_database_v2.sql')
    
    print("=" * 60)
    print("开始执行数据库初始化脚本 V2")
    print("=" * 60)
    
    execute_sql_file(sql_file)

