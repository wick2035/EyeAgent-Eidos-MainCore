"""
MySQL 数据库连接管理模块
使用 pymysql 实现数据库连接，支持单例模式和连接池
"""
import os
import logging
from typing import Optional, Any, List, Dict, Tuple
from contextlib import contextmanager
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """数据库操作错误"""
    pass


class ConnectionError(Exception):
    """数据库连接错误"""
    pass


class MySQLConnection:
    """
    MySQL 数据库连接管理器

    功能：
    - 管理数据库连接
    - 提供连接上下文管理器
    - 支持事务操作
    """

    def __init__(self):
        """初始化数据库连接配置"""
        self.config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 3306)),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("DB_NAME", "eye_agent_db"),
            "charset": os.getenv("DB_CHARSET", "utf8mb4"),
            "autocommit": os.getenv("DB_AUTOCOMMIT", "False").lower() == "true",
            "cursorclass": DictCursor
        }
        self._connection: Optional[pymysql.Connection] = None
        logger.info(f"[MySQLConnection] 初始化完成 - host={self.config['host']}:{self.config['port']}")

    def _get_connection(self) -> pymysql.Connection:
        """
        获取数据库连接（内部方法）

        如果连接不存在或已断开，会自动重新连接

        Returns:
            pymysql.Connection: 数据库连接对象

        Raises:
            ConnectionError: 连接失败时抛出
        """
        try:
            if self._connection is None or not self._connection.open:
                logger.debug("[MySQLConnection] 创建新连接")
                self._connection = pymysql.connect(**self.config)
            else:
                # 检查连接是否有效
                self._connection.ping(reconnect=True)
            return self._connection
        except pymysql.Error as e:
            logger.error(f"[MySQLConnection] 连接失败: {e}")
            raise ConnectionError(f"数据库连接失败: {str(e)}")

    @contextmanager
    def get_cursor(self):
        """
        获取数据库游标的上下文管理器

        自动处理连接获取和事务提交/回滚

        Yields:
            DictCursor: 字典游标对象

        Example:
            with db.get_cursor() as cursor:
                cursor.execute("SELECT * FROM users")
                result = cursor.fetchall()
        """
        connection = self._get_connection()
        cursor = connection.cursor()
        try:
            yield cursor
            connection.commit()
        except Exception as e:
            connection.rollback()
            logger.error(f"[MySQLConnection] 事务回滚: {e}")
            raise
        finally:
            cursor.close()

    def execute(self, sql: str, params: Tuple = None) -> int:
        """
        执行 SQL 语句（INSERT/UPDATE/DELETE）

        Args:
            sql: SQL 语句
            params: 参数元组

        Returns:
            int: 受影响的行数

        Raises:
            DatabaseError: 执行失败时抛出
        """
        try:
            with self.get_cursor() as cursor:
                affected_rows = cursor.execute(sql, params)
                logger.debug(f"[MySQLConnection] 执行SQL: {sql[:100]}... 影响行数: {affected_rows}")
                return affected_rows
        except pymysql.Error as e:
            logger.error(f"[MySQLConnection] SQL执行失败: {e}")
            raise DatabaseError(f"SQL执行失败: {str(e)}")

    def execute_many(self, sql: str, params_list: List[Tuple]) -> int:
        """
        批量执行 SQL 语句

        Args:
            sql: SQL 语句
            params_list: 参数元组列表

        Returns:
            int: 受影响的总行数
        """
        try:
            with self.get_cursor() as cursor:
                affected_rows = cursor.executemany(sql, params_list)
                logger.debug(f"[MySQLConnection] 批量执行SQL: {sql[:100]}... 影响行数: {affected_rows}")
                return affected_rows
        except pymysql.Error as e:
            logger.error(f"[MySQLConnection] 批量SQL执行失败: {e}")
            raise DatabaseError(f"批量SQL执行失败: {str(e)}")

    def fetch_one(self, sql: str, params: Tuple = None) -> Optional[Dict[str, Any]]:
        """
        查询单条记录

        Args:
            sql: SQL 查询语句
            params: 参数元组

        Returns:
            Optional[Dict]: 查询结果字典，无结果返回 None
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchone()
                logger.debug(f"[MySQLConnection] 查询单条: {sql[:100]}...")
                return result
        except pymysql.Error as e:
            logger.error(f"[MySQLConnection] 查询失败: {e}")
            raise DatabaseError(f"查询失败: {str(e)}")

    def fetch_all(self, sql: str, params: Tuple = None) -> List[Dict[str, Any]]:
        """
        查询多条记录

        Args:
            sql: SQL 查询语句
            params: 参数元组

        Returns:
            List[Dict]: 查询结果列表
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(sql, params)
                results = cursor.fetchall()
                logger.debug(f"[MySQLConnection] 查询多条: {sql[:100]}... 结果数: {len(results)}")
                return results
        except pymysql.Error as e:
            logger.error(f"[MySQLConnection] 查询失败: {e}")
            raise DatabaseError(f"查询失败: {str(e)}")

    def fetch_count(self, sql: str, params: Tuple = None) -> int:
        """
        查询记录数量

        Args:
            sql: SQL COUNT 查询语句
            params: 参数元组

        Returns:
            int: 记录数量
        """
        result = self.fetch_one(sql, params)
        if result:
            # 获取第一个值（COUNT结果）
            return list(result.values())[0]
        return 0

    def close(self):
        """关闭数据库连接"""
        if self._connection and self._connection.open:
            self._connection.close()
            self._connection = None
            logger.info("[MySQLConnection] 连接已关闭")

    def __del__(self):
        """析构时关闭连接"""
        self.close()


# 单例实例
_db_connection: Optional[MySQLConnection] = None


def get_db_connection() -> MySQLConnection:
    """
    获取全局数据库连接实例（单例模式）

    Returns:
        MySQLConnection: 数据库连接实例

    Example:
        db = get_db_connection()
        result = db.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
    """
    global _db_connection
    if _db_connection is None:
        _db_connection = MySQLConnection()
    return _db_connection
