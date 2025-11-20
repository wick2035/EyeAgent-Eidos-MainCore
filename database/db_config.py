"""
数据库配置模块
包含 MySQL 数据库的连接配置信息
从环境变量读取配置以提高安全性
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'medical_db'),
    'charset': os.getenv('DB_CHARSET', 'utf8mb4'),
    'autocommit': os.getenv('DB_AUTOCOMMIT', 'False').lower() == 'true',  # 手动控制事务
}

# 连接池配置
POOL_CONFIG = {
    'pool_name': 'medical_pool',
    'pool_size': 5,  # 连接池大小
    'pool_reset_session': True,
}

