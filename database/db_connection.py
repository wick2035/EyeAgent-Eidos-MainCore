"""
数据库连接管理模块
提供数据库连接池管理和事务控制功能
"""

import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager
from typing import Optional, Any, Dict
import logging

from .db_config import DB_CONFIG

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConnection:
    """数据库连接管理类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化数据库连接管理器
        
        Args:
            config: 数据库配置字典，如果为 None 则使用默认配置
        """
        self.config = config or DB_CONFIG
        self._connection = None
    
    def connect(self) -> pymysql.connections.Connection:
        """
        创建数据库连接
        
        Returns:
            pymysql 连接对象
        """
        try:
            self._connection = pymysql.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                charset=self.config.get('charset', 'utf8mb4'),
                cursorclass=DictCursor,  # 返回字典格式的结果
                autocommit=self.config.get('autocommit', False)
            )
            logger.info("数据库连接成功")
            return self._connection
        except pymysql.MySQLError as e:
            logger.error(f"数据库连接失败: {e}")
            raise
    
    def get_connection(self) -> pymysql.connections.Connection:
        """
        获取数据库连接（如果连接不存在或已关闭则创建新连接）
        
        Returns:
            pymysql 连接对象
        """
        if self._connection is None or not self._connection.open:
            return self.connect()
        return self._connection
    
    def close(self):
        """关闭数据库连接"""
        if self._connection and self._connection.open:
            self._connection.close()
            logger.info("数据库连接已关闭")
            self._connection = None
    
    @contextmanager
    def get_cursor(self):
        """
        获取数据库游标的上下文管理器
        使用 with 语句自动管理游标的创建和关闭
        
        Yields:
            数据库游标对象
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
    
    @contextmanager
    def transaction(self):
        """
        事务管理的上下文管理器
        自动处理事务的提交和回滚
        
        Yields:
            数据库游标对象
            
        Example:
            with db.transaction() as cursor:
                cursor.execute("INSERT INTO ...")
                cursor.execute("UPDATE ...")
                # 自动提交
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
            logger.info("事务提交成功")
        except Exception as e:
            conn.rollback()
            logger.error(f"事务回滚: {e}")
            raise
        finally:
            cursor.close()
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> list:
        """
        执行查询语句（SELECT）
        
        Args:
            query: SQL 查询语句
            params: 查询参数（可选）
            
        Returns:
            查询结果列表
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            result = cursor.fetchall()
            return result
    
    def execute_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict]:
        """
        执行查询语句并返回单条结果
        
        Args:
            query: SQL 查询语句
            params: 查询参数（可选）
            
        Returns:
            查询结果字典，如果没有结果则返回 None
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            result = cursor.fetchone()
            return result
    
    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """
        执行更新语句（INSERT, UPDATE, DELETE）
        
        Args:
            query: SQL 更新语句
            params: 更新参数（可选）
            
        Returns:
            受影响的行数
        """
        conn = self.get_connection()
        with self.get_cursor() as cursor:
            affected_rows = cursor.execute(query, params or ())
            conn.commit()
            logger.info(f"更新操作影响了 {affected_rows} 行")
            return affected_rows
    
    def execute_insert(self, query: str, params: Optional[tuple] = None) -> int:
        """
        执行插入语句并返回插入的 ID
        
        Args:
            query: SQL 插入语句
            params: 插入参数（可选）
            
        Returns:
            新插入记录的自增 ID
        """
        conn = self.get_connection()
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            conn.commit()
            last_id = cursor.lastrowid
            logger.info(f"插入成功，ID: {last_id}")
            return last_id
    
    def __enter__(self):
        """支持 with 语句"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出 with 语句时自动关闭连接"""
        self.close()
        return False


def get_db_connection():
    """
    便捷函数：创建并返回一个新的数据库连接
    
    Returns:
        pymysql 连接对象
    """
    db = DatabaseConnection()
    return db.get_connection()