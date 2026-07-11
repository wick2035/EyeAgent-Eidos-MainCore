"""
MySQL 数据库连接管理模块
使用 DBUtils.PooledDB 实现线程安全的连接池
"""
import os
import time
import random
import logging
import functools
from typing import Optional, Any, List, Dict, Tuple
from contextlib import contextmanager
from contextvars import ContextVar

import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB
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


# ===== 可重试错误码定义 =====
RETRYABLE_ERRORS = {
    2006,   # MySQL server has gone away
    2013,   # Lost connection to MySQL server during query
    2003,   # Can't connect to MySQL server (暂时性)
    1213,   # Deadlock found when trying to get lock
    1205,   # Lock wait timeout exceeded
    0,      # 空错误码（某些连接断开情况）
}

# 不可重试错误码
NON_RETRYABLE_ERRORS = {
    1045,   # Access denied
    1064,   # SQL syntax error
    1146,   # Table doesn't exist
    1054,   # Unknown column
    1062,   # Duplicate entry
    1452,   # Foreign key constraint fails
}


def is_retryable_error(error: Exception) -> bool:
    """
    判断是否是可重试错误

    Args:
        error: 异常对象

    Returns:
        是否可重试
    """
    if isinstance(error, pymysql.Error):
        error_code = error.args[0] if error.args else 0

        # 明确不可重试
        if error_code in NON_RETRYABLE_ERRORS:
            return False

        # 明确可重试
        if error_code in RETRYABLE_ERRORS:
            return True

        # 检查错误消息中的特征
        error_msg = str(error).lower()
        retryable_patterns = [
            'lost connection',
            'gone away',
            'packet sequence',
            'connection reset',
            'broken pipe',
            'deadlock',
            'lock wait timeout',
        ]
        return any(pattern in error_msg for pattern in retryable_patterns)

    # 检查消息中的特征（针对非 pymysql 错误）
    error_msg = str(error).lower()
    return 'connection' in error_msg or 'timeout' in error_msg


def retry_on_connection_error(max_retries: int = 3, base_delay: float = 0.5, max_delay: float = 10.0):
    """
    连接错误重试装饰器

    使用指数退避策略：delay = base_delay * (2 ** attempt) + random_jitter

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return func(self, *args, **kwargs)
                except Exception as e:
                    last_error = e

                    # 检查是否可重试
                    if not is_retryable_error(e):
                        logger.error(f"[MySQLPool] 不可重试错误: {e}")
                        raise

                    # 最后一次尝试，不再重试
                    if attempt >= max_retries:
                        logger.error(
                            f"[MySQLPool] 重试{max_retries}次后仍失败: {e}"
                        )
                        raise

                    # 计算延迟（指数退避 + 随机抖动）
                    delay = min(
                        base_delay * (2 ** attempt) + random.uniform(0, 0.5),
                        max_delay
                    )

                    logger.warning(
                        f"[MySQLPool] 操作失败，{delay:.2f}秒后重试 "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(delay)

            # 理论上不会到这里
            raise last_error

        return wrapper
    return decorator


class MySQLConnectionPool:
    """
    MySQL 连接池管理器

    使用 DBUtils.PooledDB 实现线程安全的连接池。

    特性：
    - 线程安全：每个操作获取独立连接
    - 自动重连：ping 检测失效连接
    - 重试机制：可重试错误自动重试
    - 连接复用：使用完毕自动归还池
    """

    def __init__(self):
        """初始化连接池配置"""
        self._pool: Optional[PooledDB] = None
        self._transaction_cursor: ContextVar[Optional[Any]] = ContextVar(
            f"mysql_transaction_cursor_{id(self)}",
            default=None,
        )
        self._config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 3306)),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("DB_NAME", "eye_agent_db"),
            "charset": os.getenv("DB_CHARSET", "utf8mb4"),
            "cursorclass": DictCursor,
        }

        # 连接池配置
        self._pool_config = {
            "mincached": int(os.getenv("DB_POOL_MIN", 5)),      # 最小空闲连接
            "maxcached": int(os.getenv("DB_POOL_MAX", 20)),     # 最大空闲连接
            "maxconnections": int(os.getenv("DB_POOL_MAX_CONN", 30)),  # 最大连接数
            "blocking": True,          # 连接数达上限时阻塞等待
            "maxusage": 1000,          # 单连接最大重用次数
            "ping": 1,                 # 每次使用前 ping 检查
        }

        self._init_pool()

    def _init_pool(self):
        """初始化连接池"""
        try:
            self._pool = PooledDB(
                creator=pymysql,
                **self._pool_config,
                **self._config,
            )
            logger.info(
                f"[MySQLPool] 连接池初始化完成 - "
                f"host={self._config['host']}:{self._config['port']}, "
                f"min={self._pool_config['mincached']}, "
                f"max={self._pool_config['maxconnections']}"
            )
        except Exception as e:
            logger.error(f"[MySQLPool] 连接池初始化失败: {e}")
            raise ConnectionError(f"数据库连接池初始化失败: {str(e)}")

    def _get_connection(self) -> pymysql.Connection:
        """
        从连接池获取连接

        Returns:
            数据库连接对象
        """
        if self._pool is None:
            self._init_pool()
        return self._pool.connection()

    @contextmanager
    def get_cursor(self):
        """
        获取数据库游标的上下文管理器

        自动处理连接获取、归还和事务提交/回滚。

        Yields:
            DictCursor: 字典游标对象
        """
        transaction_cursor = self._transaction_cursor.get()
        if transaction_cursor is not None:
            yield transaction_cursor
            return

        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            yield cursor
            connection.commit()
        except Exception as e:
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass
            logger.error(f"[MySQLPool] 事务回滚: {e}")
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if connection:
                try:
                    connection.close()  # 归还到池，不是真正关闭
                except Exception:
                    pass

    @contextmanager
    def transaction(self):
        """在当前执行上下文中复用同一连接，并仅由最外层提交或回滚。"""
        transaction_cursor = self._transaction_cursor.get()
        if transaction_cursor is not None:
            yield
            return

        connection = self._get_connection()
        cursor = connection.cursor()
        token = self._transaction_cursor.set(cursor)
        try:
            yield
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            self._transaction_cursor.reset(token)
            cursor.close()
            connection.close()

    @retry_on_connection_error(max_retries=3, base_delay=0.5)
    def execute(self, sql: str, params: Tuple = None) -> int:
        """
        执行 SQL 语句（INSERT/UPDATE/DELETE）

        带自动重试机制。

        Args:
            sql: SQL 语句
            params: 参数元组

        Returns:
            int: 受影响的行数
        """
        try:
            with self.get_cursor() as cursor:
                affected_rows = cursor.execute(sql, params)
                logger.debug(f"[MySQLPool] 执行SQL: {sql[:100]}... 影响行数: {affected_rows}")
                return affected_rows
        except pymysql.Error as e:
            # 重试装饰器会处理可重试错误
            logger.error(f"[MySQLPool] SQL执行失败: {e}")
            raise DatabaseError(f"SQL执行失败: {str(e)}")

    @retry_on_connection_error(max_retries=3, base_delay=0.5)
    def execute_many(self, sql: str, params_list: List[Tuple]) -> int:
        """
        批量执行 SQL 语句

        带自动重试机制。
        """
        try:
            with self.get_cursor() as cursor:
                affected_rows = cursor.executemany(sql, params_list)
                logger.debug(f"[MySQLPool] 批量执行SQL: {sql[:100]}... 影响行数: {affected_rows}")
                return affected_rows
        except pymysql.Error as e:
            logger.error(f"[MySQLPool] 批量SQL执行失败: {e}")
            raise DatabaseError(f"批量SQL执行失败: {str(e)}")

    @retry_on_connection_error(max_retries=3, base_delay=0.5)
    def fetch_one(self, sql: str, params: Tuple = None) -> Optional[Dict[str, Any]]:
        """
        查询单条记录

        带自动重试机制。
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchone()
                logger.debug(f"[MySQLPool] 查询单条: {sql[:100]}...")
                return result
        except pymysql.Error as e:
            logger.error(f"[MySQLPool] 查询失败: {e}")
            raise DatabaseError(f"查询失败: {str(e)}")

    @retry_on_connection_error(max_retries=3, base_delay=0.5)
    def fetch_all(self, sql: str, params: Tuple = None) -> List[Dict[str, Any]]:
        """
        查询多条记录

        带自动重试机制。
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(sql, params)
                results = cursor.fetchall()
                logger.debug(f"[MySQLPool] 查询多条: {sql[:100]}... 结果数: {len(results)}")
                return results
        except pymysql.Error as e:
            logger.error(f"[MySQLPool] 查询失败: {e}")
            raise DatabaseError(f"查询失败: {str(e)}")

    def fetch_count(self, sql: str, params: Tuple = None) -> int:
        """
        查询记录数量
        """
        result = self.fetch_one(sql, params)
        if result:
            return list(result.values())[0]
        return 0

    def close(self):
        """关闭连接池"""
        if self._pool:
            try:
                self._pool.close()
            except Exception:
                pass
            self._pool = None
            logger.info("[MySQLPool] 连接池已关闭")

    def __del__(self):
        """析构时关闭连接池"""
        self.close()


# 保持向后兼容的别名
MySQLConnection = MySQLConnectionPool


# 单例实例
_db_pool: Optional[MySQLConnectionPool] = None


def get_db_connection() -> MySQLConnectionPool:
    """
    获取全局数据库连接池实例（单例模式）

    Returns:
        MySQLConnectionPool: 数据库连接池实例
    """
    global _db_pool
    if _db_pool is None:
        _db_pool = MySQLConnectionPool()
    return _db_pool


def close_db_connection():
    """
    关闭全局数据库连接池

    应在应用关闭时调用。
    """
    global _db_pool
    if _db_pool:
        _db_pool.close()
        _db_pool = None
