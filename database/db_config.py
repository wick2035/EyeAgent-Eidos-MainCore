"""
数据库配置模块
包含 MySQL 数据库的连接配置信息
"""

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '20041118',
    'database': 'medical_db',
    'charset': 'utf8mb4',
    'autocommit': False,  # 手动控制事务
}

# 连接池配置
POOL_CONFIG = {
    'pool_name': 'medical_pool',
    'pool_size': 5,  # 连接池大小
    'pool_reset_session': True,
}

