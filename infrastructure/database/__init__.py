"""
数据库模块
提供 MySQL 数据库连接和管理功能
"""
from infrastructure.database.mysql_connection import (
    get_db_connection,
    DatabaseError,
    ConnectionError as DBConnectionError
)

__all__ = [
    "get_db_connection",
    "DatabaseError",
    "DBConnectionError"
]
