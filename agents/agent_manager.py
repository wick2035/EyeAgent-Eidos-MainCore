"""
智能体管理器 - 重构版
基于清洁架构和Session管理器
"""
from typing import Dict, Any, Optional
import logging

from domain.enums.agent_type import AgentType
from agents.health.health_agent import HealthAgent
from agents.report.report_agent import ReportAgent
from agents.reminder.reminder_agent import ReminderAgent
from infrastructure.session.session_manager import get_session_manager

logger = logging.getLogger(__name__)


class AgentManager:
    """
    智能体管理器（重构版）
    
    职责：
    - 创建和管理智能体实例
    - 通过SessionManager管理会话
    - 路由请求到正确的智能体
    """
    
    def __init__(self):
        """初始化AgentManager"""
        self.agents: Dict[str, Any] = {}  # agent_id -> agent实例
        self.session_manager = get_session_manager()
        logger.info("[AgentManager] 初始化完成")
    
    def create_agent(
        self, 
        session_id: str,
        patient_id: str,
        agent_type: str = "health",
        role: str = "patient"
    ) -> Any:
        """
        创建新的智能体实例
        
        Args:
            session_id: 会话ID
            patient_id: 患者UUID（必需）
            agent_type: Agent类型 (health/report/reminder)
            role: 用户角色 (patient/doctor)
        
        Returns:
            创建的Agent实例
        
        Raises:
            ValueError: 如果agent_type无效
        """
        logger.info(f"[AgentManager] 创建Agent - session={session_id}, patient={patient_id}, type={agent_type}")
        
        # 确保有patient_id
        if not patient_id:
            raise ValueError("patient_id is required for creating agents")
        
        # 创建agent实例
        agent_id = f"{agent_type}_{session_id}"
        
        try:
            agent_type_enum = AgentType.from_string(agent_type)
            
            if agent_type_enum == AgentType.HEALTH:
                agent = HealthAgent(patient_id=patient_id, session_id=session_id, role=role)
            elif agent_type_enum == AgentType.REPORT:
                agent = ReportAgent(patient_id=patient_id, session_id=session_id, role=role)
            elif agent_type_enum == AgentType.REMINDER:
                agent = ReminderAgent(patient_id=patient_id, session_id=session_id, role=role)
            else:
                raise ValueError(f"未知的智能体类型: {agent_type}")
            
            # 存储agent
            self.agents[agent_id] = agent
            
            # 在SessionManager中创建会话记录
            self.session_manager.create_session(
                session_id=session_id,
                patient_id=patient_id,
                agent_type=agent_type,
                agent_id=agent_id,
                role=role
            )
            
            logger.info(f"[AgentManager] Agent创建成功 - total_agents={len(self.agents)}")
            return agent
            
        except Exception as e:
            logger.error(f"[AgentManager] 创建Agent失败: {e}", exc_info=True)
            raise
    
    def get_agent(self, session_id: str) -> Optional[Any]:
        """
        根据session_id获取智能体实例
        
        Args:
            session_id: 会话ID
        
        Returns:
            Agent实例，如果不存在则返回None
        """
        session = self.session_manager.get_session(session_id)
        
        if not session:
            logger.warning(f"[AgentManager] Session不存在: {session_id}")
            return None
        
        agent_id = session.get("agent_id")
        if not agent_id:
            logger.warning(f"[AgentManager] Session中没有agent_id: {session_id}")
            return None
        
        agent = self.agents.get(agent_id)
        if not agent:
            logger.warning(f"[AgentManager] Agent实例不存在: {agent_id}")
            return None
        
        return agent
    
    def get_or_create_agent(
        self,
        session_id: str,
        patient_id: str,
        agent_type: str = "health",
        role: str = "patient"
    ) -> Any:
        """
        获取或创建会话对应的智能体
        
        Args:
            session_id: 会话ID
            patient_id: 患者UUID
            agent_type: Agent类型 (health/report/reminder)
            role: 用户角色 (patient/doctor)
        
        Returns:
            Agent实例
        """
        logger.debug(f"[AgentManager] get_or_create_agent - session={session_id}")
        
        # 尝试获取现有agent
        agent = self.get_agent(session_id)
        
        if agent:
            logger.debug(f"[AgentManager] 返回已存在的Agent")
            return agent
        
        # 创建新agent
        logger.debug(f"[AgentManager] 创建新Agent")
        return self.create_agent(
            session_id=session_id,
            patient_id=patient_id,
            agent_type=agent_type,
            role=role
        )
    
    def remove_agent(self, session_id: str) -> bool:
        """
        移除智能体
        
        Args:
            session_id: 会话ID
        
        Returns:
            是否移除成功
        """
        session = self.session_manager.get_session(session_id)
        
        if not session:
            return False
        
        agent_id = session.get("agent_id")
        
        # 删除agent实例
        if agent_id and agent_id in self.agents:
            del self.agents[agent_id]
            logger.info(f"[AgentManager] 删除Agent实例: {agent_id}")
        
        # 删除session
        self.session_manager.delete_session(session_id)
        logger.info(f"[AgentManager] 删除Session: {session_id}")
        
        return True
    
    def reset_agent(self, session_id: str) -> bool:
        """
        重置智能体
        
        Args:
            session_id: 会话ID
        
        Returns:
            是否重置成功
        """
        agent = self.get_agent(session_id)
        
        if agent:
            agent.reset()
            logger.info(f"[AgentManager] 重置Agent: {session_id}")
            return True
        
        return False
    
    def switch_agent_type(
        self,
        session_id: str,
        new_agent_type: str,
        patient_id: str,
        role: str = "patient"
    ) -> Any:
        """
        切换智能体类型（热切换）
        
        Args:
            session_id: 会话ID
            new_agent_type: 新的Agent类型
            patient_id: 患者UUID
            role: 用户角色
        
        Returns:
            新的Agent实例
        """
        logger.info(f"[AgentManager] 切换Agent类型: {session_id} -> {new_agent_type}")
        
        # 删除旧agent
        self.remove_agent(session_id)
        
        # 创建新agent
        return self.create_agent(
            session_id=session_id,
            patient_id=patient_id,
            agent_type=new_agent_type,
            role=role
        )
    
    def get_active_sessions_count(self) -> int:
        """获取活跃会话数量"""
        return self.session_manager.get_active_sessions_count()
    
    def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话
        
        Returns:
            清理的会话数量
        """
        expired_count = self.session_manager.cleanup_expired_sessions()
        
        if expired_count > 0:
            logger.info(f"[AgentManager] 清理了{expired_count}个过期会话")
        
        return expired_count
    
    def get_all_sessions(self) -> list:
        """获取所有会话信息"""
        return list(self.session_manager._sessions.values())
    
    def __repr__(self) -> str:
        return f"<AgentManager agents={len(self.agents)} sessions={self.get_active_sessions_count()}>"
