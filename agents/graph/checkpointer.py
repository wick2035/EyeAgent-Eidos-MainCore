"""
MySQL Checkpoint Saver 实现

基于 LangGraph BaseCheckpointSaver 接口，实现 MySQL 持久化存储。
替代默认的 SQLite 存储，支持生产环境部署。

特性：
- 软删除支持
- 乐观锁版本控制
- 可选数据压缩
"""
import pickle
import json
import uuid
import zlib
import logging
from typing import Optional, Dict, Any, Iterator, Tuple, Sequence, List
from contextlib import contextmanager

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
    get_checkpoint_id,
)

from infrastructure.database.mysql_connection import get_db_connection, MySQLConnection, DatabaseError

logger = logging.getLogger(__name__)

# 压缩阈值（字节），超过此大小自动压缩
COMPRESSION_THRESHOLD = 10 * 1024  # 10KB


class MySQLCheckpointSaver(BaseCheckpointSaver):
    """
    MySQL Checkpoint 保存器

    实现 LangGraph BaseCheckpointSaver 接口，
    将图状态持久化到 MySQL 数据库。

    表结构：
    - langgraph_checkpoint: 检查点主表
    - langgraph_checkpoint_writes: 写入缓存表
    - langgraph_thread_mapping: ID映射表

    特性：
    - 软删除：通过 is_deleted 标记删除，保留数据
    - 乐观锁：通过 version 字段实现并发控制
    - 压缩：大数据自动压缩存储
    """

    def __init__(
        self,
        db: Optional[MySQLConnection] = None,
        enable_compression: bool = True,
    ):
        """
        初始化 MySQL Checkpoint Saver

        Args:
            db: MySQL 连接实例，为空则使用全局连接
            enable_compression: 是否启用数据压缩，默认启用
        """
        super().__init__()
        self.db = db or get_db_connection()
        self.enable_compression = enable_compression
        logger.info(f"[MySQLCheckpointSaver] 初始化完成, compression={enable_compression}")

    def _compress_data(self, data: bytes) -> Tuple[bytes, bool]:
        """
        压缩数据（如果超过阈值）

        Args:
            data: 原始数据

        Returns:
            (压缩/原始数据, 是否压缩)
        """
        if not self.enable_compression or len(data) < COMPRESSION_THRESHOLD:
            return data, False

        compressed = zlib.compress(data, level=6)
        # 只有压缩后更小才使用压缩版本
        if len(compressed) < len(data):
            return compressed, True
        return data, False

    def _decompress_data(self, data: bytes, is_compressed: bool) -> bytes:
        """
        解压缩数据

        Args:
            data: 数据
            is_compressed: 是否已压缩

        Returns:
            解压后的数据
        """
        if is_compressed:
            return zlib.decompress(data)
        return data

    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """
        获取检查点元组

        Args:
            config: 配置字典，包含 {"configurable": {"thread_id": "..."}}

        Returns:
            CheckpointTuple 或 None
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config["configurable"].get("checkpoint_id")

        try:
            if checkpoint_id:
                # 获取指定检查点
                sql = """
                    SELECT thread_id, checkpoint_id, parent_checkpoint_id,
                           checkpoint_data, is_compressed, checkpoint_metadata, channel_versions
                    FROM langgraph_checkpoint
                    WHERE thread_id = %s AND checkpoint_id = %s AND is_deleted = 0
                """
                row = self.db.fetch_one(sql, (thread_id, checkpoint_id))
            else:
                # 获取最新检查点
                sql = """
                    SELECT thread_id, checkpoint_id, parent_checkpoint_id,
                           checkpoint_data, is_compressed, checkpoint_metadata, channel_versions
                    FROM langgraph_checkpoint
                    WHERE thread_id = %s AND is_deleted = 0
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                row = self.db.fetch_one(sql, (thread_id,))

            if not row:
                logger.debug(f"[MySQLCheckpointSaver] 未找到检查点: thread={thread_id}")
                return None

            # 解压缩并反序列化数据
            is_compressed = bool(row.get("is_compressed", 0))
            raw_data = self._decompress_data(row["checkpoint_data"], is_compressed)
            checkpoint = pickle.loads(raw_data)

            metadata = json.loads(row["checkpoint_metadata"]) if row["checkpoint_metadata"] else {}
            channel_versions = json.loads(row["channel_versions"]) if row["channel_versions"] else {}

            # 构建配置
            checkpoint_config = {
                "configurable": {
                    "thread_id": row["thread_id"],
                    "checkpoint_id": row["checkpoint_id"],
                }
            }

            # 获取 pending writes
            pending_writes = self._get_pending_writes(thread_id, row["checkpoint_id"])

            logger.debug(f"[MySQLCheckpointSaver] 加载检查点: thread={thread_id}, checkpoint={row['checkpoint_id']}")

            return CheckpointTuple(
                config=checkpoint_config,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_id": row["parent_checkpoint_id"],
                    }
                } if row["parent_checkpoint_id"] else None,
                pending_writes=pending_writes,
            )

        except Exception as e:
            logger.error(f"[MySQLCheckpointSaver] 获取检查点失败: {e}", exc_info=True)
            return None

    def list(
        self,
        config: Optional[Dict[str, Any]],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """
        列出检查点

        Args:
            config: 配置字典
            filter: 过滤条件
            before: 在此检查点之前
            limit: 返回数量限制

        Yields:
            CheckpointTuple
        """
        thread_id = config["configurable"]["thread_id"] if config else None

        try:
            sql_parts = [
                "SELECT thread_id, checkpoint_id, parent_checkpoint_id,",
                "       checkpoint_data, is_compressed, checkpoint_metadata, channel_versions",
                "FROM langgraph_checkpoint",
            ]
            params = []

            conditions = ["is_deleted = 0"]  # 排除软删除记录
            if thread_id:
                conditions.append("thread_id = %s")
                params.append(thread_id)

            if before:
                before_checkpoint_id = before["configurable"].get("checkpoint_id")
                if before_checkpoint_id:
                    conditions.append("created_at < (SELECT created_at FROM langgraph_checkpoint WHERE checkpoint_id = %s AND is_deleted = 0)")
                    params.append(before_checkpoint_id)

            sql_parts.append("WHERE " + " AND ".join(conditions))
            sql_parts.append("ORDER BY created_at DESC")

            if limit:
                sql_parts.append(f"LIMIT {int(limit)}")

            sql = " ".join(sql_parts)
            rows = self.db.fetch_all(sql, tuple(params) if params else None)

            for row in rows:
                # 解压缩并反序列化
                is_compressed = bool(row.get("is_compressed", 0))
                raw_data = self._decompress_data(row["checkpoint_data"], is_compressed)
                checkpoint = pickle.loads(raw_data)

                metadata = json.loads(row["checkpoint_metadata"]) if row["checkpoint_metadata"] else {}

                checkpoint_config = {
                    "configurable": {
                        "thread_id": row["thread_id"],
                        "checkpoint_id": row["checkpoint_id"],
                    }
                }

                yield CheckpointTuple(
                    config=checkpoint_config,
                    checkpoint=checkpoint,
                    metadata=metadata,
                    parent_config={
                        "configurable": {
                            "thread_id": row["thread_id"],
                            "checkpoint_id": row["parent_checkpoint_id"],
                        }
                    } if row["parent_checkpoint_id"] else None,
                )

        except Exception as e:
            logger.error(f"[MySQLCheckpointSaver] 列出检查点失败: {e}", exc_info=True)

    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> Dict[str, Any]:
        """
        保存检查点

        Args:
            config: 配置字典
            checkpoint: 检查点数据
            metadata: 元数据
            new_versions: 新的通道版本

        Returns:
            更新后的配置
        """
        thread_id = config["configurable"]["thread_id"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")
        checkpoint_id = str(uuid.uuid4())

        try:
            # 序列化并压缩数据
            raw_data = pickle.dumps(checkpoint)
            checkpoint_data, is_compressed = self._compress_data(raw_data)

            metadata_json = json.dumps(metadata) if metadata else None
            versions_json = json.dumps(new_versions) if new_versions else None

            # 插入检查点
            sql = """
                INSERT INTO langgraph_checkpoint
                (thread_id, checkpoint_id, parent_checkpoint_id, checkpoint_data, is_compressed, checkpoint_metadata, channel_versions)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                checkpoint_data = VALUES(checkpoint_data),
                is_compressed = VALUES(is_compressed),
                checkpoint_metadata = VALUES(checkpoint_metadata),
                channel_versions = VALUES(channel_versions),
                version = version + 1,
                updated_at = CURRENT_TIMESTAMP
            """
            self.db.execute(sql, (
                thread_id,
                checkpoint_id,
                parent_checkpoint_id,
                checkpoint_data,
                1 if is_compressed else 0,
                metadata_json,
                versions_json,
            ))

            logger.debug(f"[MySQLCheckpointSaver] 保存检查点: thread={thread_id}, checkpoint={checkpoint_id}, compressed={is_compressed}")

            return {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                }
            }

        except DatabaseError as e:
            # 数据库错误：记录但不抛出，返回原配置
            # 这样 LangGraph 可以继续运行，只是这次 checkpoint 未保存
            logger.error(
                f"[MySQLCheckpointSaver] 保存检查点失败（已抑制）: {e}, "
                f"thread={thread_id}"
            )
            return config  # 返回原配置，不中断流程

        except Exception as e:
            # 其他错误：同样抑制
            logger.error(
                f"[MySQLCheckpointSaver] 保存检查点异常（已抑制）: {e}, "
                f"thread={thread_id}",
                exc_info=True
            )
            return config

    def put_writes(
        self,
        config: Dict[str, Any],
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """
        保存待处理的写操作

        Args:
            config: 配置字典
            writes: 写操作列表 [(channel, value), ...]
            task_id: 任务ID
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config["configurable"].get("checkpoint_id", "")

        try:
            for channel, value in writes:
                value_data = pickle.dumps(value)
                sql = """
                    INSERT INTO langgraph_checkpoint_writes
                    (thread_id, checkpoint_id, task_id, channel, value)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    value = VALUES(value),
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP
                """
                self.db.execute(sql, (thread_id, checkpoint_id, task_id, channel, value_data))

            logger.debug(f"[MySQLCheckpointSaver] 保存写操作: thread={thread_id}, task={task_id}, count={len(writes)}")

        except DatabaseError as e:
            # 数据库错误：记录但不抛出
            logger.error(
                f"[MySQLCheckpointSaver] 保存写操作失败（已抑制）: {e}, "
                f"thread={thread_id}, task={task_id}"
            )

        except Exception as e:
            # 其他错误：同样抑制
            logger.error(
                f"[MySQLCheckpointSaver] 保存写操作异常（已抑制）: {e}, "
                f"thread={thread_id}, task={task_id}",
                exc_info=True
            )

    def _get_pending_writes(
        self,
        thread_id: str,
        checkpoint_id: str
    ) -> list:
        """
        获取待处理的写操作

        Args:
            thread_id: 线程ID
            checkpoint_id: 检查点ID

        Returns:
            写操作列表
        """
        try:
            sql = """
                SELECT task_id, channel, value
                FROM langgraph_checkpoint_writes
                WHERE thread_id = %s AND checkpoint_id = %s AND is_deleted = 0
            """
            rows = self.db.fetch_all(sql, (thread_id, checkpoint_id))

            writes = []
            for row in rows:
                value = pickle.loads(row["value"])
                writes.append((row["task_id"], row["channel"], value))

            return writes

        except Exception as e:
            logger.error(f"[MySQLCheckpointSaver] 获取写操作失败: {e}", exc_info=True)
            return []

    def delete_thread(self, thread_id: str) -> bool:
        """
        软删除线程的所有检查点

        Args:
            thread_id: 线程ID

        Returns:
            是否成功
        """
        try:
            # 软删除写操作
            self.db.execute(
                """UPDATE langgraph_checkpoint_writes
                   SET is_deleted = 1, deleted_at = NOW(), version = version + 1
                   WHERE thread_id = %s AND is_deleted = 0""",
                (thread_id,)
            )

            # 软删除检查点
            affected = self.db.execute(
                """UPDATE langgraph_checkpoint
                   SET is_deleted = 1, deleted_at = NOW(), version = version + 1
                   WHERE thread_id = %s AND is_deleted = 0""",
                (thread_id,)
            )

            # 软删除映射（更新状态为 deleted）
            self.db.execute(
                """UPDATE langgraph_thread_mapping
                   SET is_deleted = 1, deleted_at = NOW(), status = 'deleted', version = version + 1
                   WHERE thread_id = %s AND is_deleted = 0""",
                (thread_id,)
            )

            logger.info(f"[MySQLCheckpointSaver] 软删除线程: thread={thread_id}, checkpoints={affected}")
            return True

        except Exception as e:
            logger.error(f"[MySQLCheckpointSaver] 删除线程失败: {e}", exc_info=True)
            return False

    def archive_thread(self, thread_id: str) -> bool:
        """
        归档线程（标记为 archived 状态）

        Args:
            thread_id: 线程ID

        Returns:
            是否成功
        """
        try:
            self.db.execute(
                """UPDATE langgraph_thread_mapping
                   SET status = 'archived', version = version + 1, updated_at = NOW()
                   WHERE thread_id = %s AND is_deleted = 0""",
                (thread_id,)
            )
            logger.info(f"[MySQLCheckpointSaver] 归档线程: thread={thread_id}")
            return True

        except Exception as e:
            logger.error(f"[MySQLCheckpointSaver] 归档线程失败: {e}", exc_info=True)
            return False

    def save_thread_mapping(
        self,
        thread_id: str,
        patient_id: Optional[str],
        conversation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        doctor_id: Optional[str] = None,
        agent_type: str = "health",
        status: str = "active",
    ) -> bool:
        """
        保存线程ID映射

        Args:
            thread_id: LangGraph 线程ID
            patient_id: 患者UUID；科研模式为空
            conversation_id: 数据库会话ID
            session_id: 会话ID
            doctor_id: 医生UUID
            agent_type: Agent类型
            status: 状态 (active/archived/deleted)

        Returns:
            是否成功
        """
        try:
            sql = """
                INSERT INTO langgraph_thread_mapping
                (thread_id, conversation_id, session_id, patient_id, doctor_id, agent_type, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                conversation_id = VALUES(conversation_id),
                session_id = VALUES(session_id),
                doctor_id = VALUES(doctor_id),
                agent_type = VALUES(agent_type),
                status = VALUES(status),
                version = version + 1,
                updated_at = CURRENT_TIMESTAMP
            """
            self.db.execute(sql, (
                thread_id, conversation_id, session_id, patient_id, doctor_id, agent_type, status
            ))

            logger.debug(f"[MySQLCheckpointSaver] 保存映射: thread={thread_id}, patient={patient_id}, status={status}")
            return True

        except Exception as e:
            logger.error(f"[MySQLCheckpointSaver] 保存映射失败: {e}", exc_info=True)
            return False

    def get_thread_mapping(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        获取线程映射信息

        Args:
            thread_id: 线程ID

        Returns:
            映射信息字典或 None
        """
        try:
            sql = """
                SELECT thread_id, conversation_id, session_id, patient_id, doctor_id,
                       agent_type, status, version, created_at, updated_at
                FROM langgraph_thread_mapping
                WHERE thread_id = %s AND is_deleted = 0
            """
            row = self.db.fetch_one(sql, (thread_id,))

            if row:
                return dict(row)
            return None

        except Exception as e:
            logger.error(f"[MySQLCheckpointSaver] 获取映射失败: {e}", exc_info=True)
            return None

    def record_agent_switch(
        self,
        thread_id: str,
        new_agent_type: str,
        checkpoint_id: Optional[str] = None,
    ) -> bool:
        """
        记录 Agent 切换

        当对话过程中切换到新的 Agent 时，记录切换历史：
        1. 结束当前 Agent 的使用记录（设置 ended_at）
        2. 创建新 Agent 的使用记录

        Args:
            thread_id: 线程ID
            new_agent_type: 新的 Agent 类型
            checkpoint_id: 切换时的检查点ID（可选）

        Returns:
            是否成功
        """
        try:
            # 1. 结束当前 Agent 的使用记录
            self.db.execute(
                """UPDATE langgraph_thread_agent_history
                   SET ended_at = NOW(), version = version + 1, updated_at = NOW()
                   WHERE thread_id = %s AND ended_at IS NULL AND is_deleted = 0""",
                (thread_id,)
            )

            # 2. 创建新 Agent 的使用记录
            sql = """
                INSERT INTO langgraph_thread_agent_history
                (thread_id, agent_type, checkpoint_id, started_at)
                VALUES (%s, %s, %s, NOW())
            """
            self.db.execute(sql, (thread_id, new_agent_type, checkpoint_id))

            logger.debug(
                f"[MySQLCheckpointSaver] 记录 Agent 切换: "
                f"thread={thread_id}, agent={new_agent_type}, checkpoint={checkpoint_id}"
            )
            return True

        except Exception as e:
            logger.error(f"[MySQLCheckpointSaver] 记录 Agent 切换失败: {e}", exc_info=True)
            return False

    def get_agent_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        获取 Agent 使用历史

        Args:
            thread_id: 线程ID

        Returns:
            Agent 使用历史列表，按开始时间升序排列
        """
        try:
            sql = """
                SELECT id, thread_id, agent_type, checkpoint_id,
                       started_at, ended_at, created_at
                FROM langgraph_thread_agent_history
                WHERE thread_id = %s AND is_deleted = 0
                ORDER BY started_at ASC
            """
            rows = self.db.fetch_all(sql, (thread_id,))

            return [dict(row) for row in rows] if rows else []

        except Exception as e:
            logger.error(f"[MySQLCheckpointSaver] 获取 Agent 历史失败: {e}", exc_info=True)
            return []

    def get_current_agent(self, thread_id: str) -> Optional[str]:
        """
        获取当前正在使用的 Agent 类型

        Args:
            thread_id: 线程ID

        Returns:
            当前 Agent 类型或 None
        """
        try:
            sql = """
                SELECT agent_type
                FROM langgraph_thread_agent_history
                WHERE thread_id = %s AND ended_at IS NULL AND is_deleted = 0
                ORDER BY started_at DESC
                LIMIT 1
            """
            row = self.db.fetch_one(sql, (thread_id,))

            if row:
                return row["agent_type"]
            return None

        except Exception as e:
            logger.error(f"[MySQLCheckpointSaver] 获取当前 Agent 失败: {e}", exc_info=True)
            return None

    def list_checkpoints_summary(
        self,
        thread_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        获取检查点摘要列表（用于调试）

        Args:
            thread_id: 线程ID
            limit: 返回数量限制

        Returns:
            检查点摘要列表，按创建时间降序排列
        """
        try:
            sql = """
                SELECT checkpoint_id, parent_checkpoint_id, is_compressed,
                       checkpoint_metadata, created_at, updated_at
                FROM langgraph_checkpoint
                WHERE thread_id = %s AND is_deleted = 0
                ORDER BY created_at DESC
                LIMIT %s
            """
            rows = self.db.fetch_all(sql, (thread_id, limit))

            result = []
            for row in rows:
                metadata = json.loads(row["checkpoint_metadata"]) if row["checkpoint_metadata"] else {}
                result.append({
                    "checkpoint_id": row["checkpoint_id"],
                    "parent_checkpoint_id": row["parent_checkpoint_id"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                    "is_compressed": bool(row["is_compressed"]),
                    "metadata": metadata,
                })

            return result

        except Exception as e:
            logger.error(f"[MySQLCheckpointSaver] 获取检查点列表失败: {e}", exc_info=True)
            return []


# 单例实例
_checkpointer: Optional[MySQLCheckpointSaver] = None


def get_checkpointer(enable_compression: bool = True) -> MySQLCheckpointSaver:
    """
    获取 Checkpoint Saver 单例

    Args:
        enable_compression: 是否启用压缩

    Returns:
        MySQLCheckpointSaver 实例
    """
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = MySQLCheckpointSaver(enable_compression=enable_compression)
    return _checkpointer
