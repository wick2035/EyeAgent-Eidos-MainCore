"""
Session管理器 - 负责会话的创建、存储和检索
注意：当前使用内存存储，生产环境应替换为Redis或后端API
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Session管理器
    
    职责：
    - 创建和管理会话
    - 存储会话数据
    - 会话过期管理
    
    注意：当前实现使用内存字典，生产环境应使用Redis或后端API
    """
    
    def __init__(self, ttl_minutes: int = 120):
        """
        初始化SessionManager

        Args:
            ttl_minutes: 会话过期时间（分钟），默认120分钟（2小时）
        """
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        logger.info(f"[SessionManager] 初始化完成，TTL={ttl_minutes}分钟")
    
    def create_session(self, session_id: str, patient_id: str, 
                      agent_type: str, **kwargs) -> Dict[str, Any]:
        """
        创建新会话
        
        Args:
            session_id: 会话ID
            patient_id: 患者UUID
            agent_type: Agent类型
            **kwargs: 其他会话数据
        
        Returns:
            会话数据字典
        """
        session_data = {
            "session_id": session_id,
            "patient_id": patient_id,
            "agent_type": agent_type,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "is_active": True,
            **kwargs
        }
        
        self._sessions[session_id] = session_data
        logger.info(f"[SessionManager] 创建会话: {session_id}, patient={patient_id}, agent={agent_type}")
        return session_data
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话数据
        
        Args:
            session_id: 会话ID
        
        Returns:
            会话数据字典，如果不存在或已过期则返回None
        """
        session = self._sessions.get(session_id)
        
        if not session:
            logger.warning(f"[SessionManager] 会话不存在: {session_id}")
            return None
        
        # 检查是否过期
        if self._is_expired(session):
            logger.info(f"[SessionManager] 会话已过期: {session_id}")
            self.delete_session(session_id)
            return None
        
        # 更新最后活动时间
        session["last_activity"] = datetime.now()
        return session
    
    def update_session(self, session_id: str, **kwargs) -> bool:
        """
        更新会话数据
        
        Args:
            session_id: 会话ID
            **kwargs: 要更新的字段
        
        Returns:
            是否更新成功
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.update(kwargs)
        session["last_activity"] = datetime.now()
        logger.debug(f"[SessionManager] 更新会话: {session_id}")
        return True
    
    def delete_session(self, session_id: str) -> bool:
        """
        删除会话
        
        Args:
            session_id: 会话ID
        
        Returns:
            是否删除成功
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"[SessionManager] 删除会话: {session_id}")
            return True
        return False
    
    def _is_expired(self, session: Dict[str, Any]) -> bool:
        """检查会话是否过期"""
        last_activity = session.get("last_activity")
        if not last_activity:
            return True
        return datetime.now() - last_activity > self._ttl
    
    def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话
        
        Returns:
            清理的会话数量
        """
        expired_sessions = [
            sid for sid, session in self._sessions.items()
            if self._is_expired(session)
        ]
        
        for session_id in expired_sessions:
            self.delete_session(session_id)
        
        if expired_sessions:
            logger.info(f"[SessionManager] 清理了{len(expired_sessions)}个过期会话")
        
        return len(expired_sessions)
    
    def get_active_sessions_count(self) -> int:
        """获取活跃会话数量"""
        return len(self._sessions)
    
    def get_sessions_by_patient(self, patient_id: str) -> list:
        """
        获取患者的所有会话

        Args:
            patient_id: 患者UUID

        Returns:
            会话列表
        """
        return [
            session for session in self._sessions.values()
            if session.get("patient_id") == patient_id
        ]

    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有活动会话（用于调试和监控）

        Returns:
            包含所有会话信息的字典
        """
        # 先清理过期会话
        self.cleanup_expired_sessions()

        # 返回会话摘要信息
        return {
            sid: {
                "session_id": sid,
                "created_at": sess["created_at"].isoformat() if isinstance(sess["created_at"], datetime) else str(sess["created_at"]),
                "last_activity": sess["last_activity"].isoformat() if isinstance(sess["last_activity"], datetime) else str(sess["last_activity"]),
                "patient_id": sess.get("patient_id"),
                "agent_type": sess.get("agent_type"),
                "role": sess.get("role"),
                "is_active": sess.get("is_active", True)
            }
            for sid, sess in self._sessions.items()
        }


# 全局单例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """
    获取全局SessionManager实例（单例模式）
    
    Returns:
        SessionManager实例
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
        logger.info("[SessionManager] 全局实例已初始化")
    return _session_manager

