"""
智能体管理器 - 重构版
基于清洁架构和Session管理器
支持对话历史持久化
"""
from typing import Dict, Any, Optional, TYPE_CHECKING
import logging

from domain.enums.agent_type import AgentType
from agents.health.health_agent import HealthAgent
from agents.report.report_agent import ReportAgent
from agents.reminder.reminder_agent import ReminderAgent
from agents.research.research_agent import ResearchAgent
from infrastructure.session.session_manager import get_session_manager

if TYPE_CHECKING:
    from application.services.chat_persistence_service import ChatPersistenceService

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
        role: str = "patient",
        conversation_id: Optional[str] = None,
        persistence_service: Optional["ChatPersistenceService"] = None
    ) -> Any:
        """
        创建新的智能体实例

        Args:
            session_id: 会话ID
            patient_id: 患者UUID（必需）
            agent_type: Agent类型 (health/report/reminder)
            role: 用户角色 (patient/doctor)
            conversation_id: 数据库会话ID（用于继续对话）
            persistence_service: 持久化服务

        Returns:
            创建的Agent实例

        Raises:
            ValueError: 如果agent_type无效
        """
        logger.info(f"[AgentManager] 创建Agent - session={session_id}, patient={patient_id}, type={agent_type}, conversation_id={conversation_id}")

        # 确保有patient_id
        if not patient_id:
            raise ValueError("patient_id is required for creating agents")

        # ========== 新增：ID转换逻辑 ==========
        # 使用ID映射服务将数字ID转换为UUID（如果需要）
        try:
            from infrastructure.services.id_mapping_service import get_id_mapping_service

            id_mapping = get_id_mapping_service()
            original_patient_id = patient_id

            # 尝试获取UUID（如果已经是UUID会直接返回）
            uuid_patient_id = id_mapping.get_uuid(patient_id)

            if uuid_patient_id:
                if uuid_patient_id != original_patient_id:
                    logger.info(f"[AgentManager] ID映射: {original_patient_id} → {uuid_patient_id}")
                patient_id = uuid_patient_id
            else:
                # 映射失败，记录警告但继续使用原ID（让后端API报错）
                logger.warning(
                    f"[AgentManager] 无法找到患者ID {original_patient_id} 对应的UUID，"
                    f"将使用原始ID继续（可能导致后续API调用失败）"
                )
        except Exception as e:
            logger.error(f"[AgentManager] ID映射服务异常: {e}", exc_info=True)
            # 继续使用原始ID
        # ======================================

        # 创建agent实例
        agent_id = f"{agent_type}_{session_id}"
        
        try:
            agent_type_enum = AgentType.from_string(agent_type)

            if agent_type_enum == AgentType.HEALTH:
                agent = HealthAgent(
                    patient_id=patient_id,
                    session_id=session_id,
                    role=role,
                    conversation_id=conversation_id,
                    persistence_service=persistence_service
                )
            elif agent_type_enum == AgentType.REPORT:
                agent = ReportAgent(
                    patient_id=patient_id,
                    session_id=session_id,
                    role=role,
                    conversation_id=conversation_id,
                    persistence_service=persistence_service
                )
            elif agent_type_enum == AgentType.REMINDER:
                agent = ReminderAgent(
                    patient_id=patient_id,
                    session_id=session_id,
                    role=role,
                    conversation_id=conversation_id,
                    persistence_service=persistence_service
                )
            elif agent_type_enum == AgentType.RESEARCH:
                # ResearchAgent: patient_id实际上是doctor_id
                agent = ResearchAgent(
                    doctor_id=patient_id,  # 对于ResearchAgent，这里传入的是doctor_id
                    session_id=session_id,
                    conversation_id=conversation_id,
                    persistence_service=persistence_service
                )
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
        role: str = "patient",
        conversation_id: Optional[str] = None,
        persistence_service: Optional["ChatPersistenceService"] = None
    ) -> Any:
        """
        获取或创建会话对应的智能体

        Args:
            session_id: 会话ID
            patient_id: 患者UUID
            agent_type: Agent类型 (health/report/reminder)
            role: 用户角色 (patient/doctor)
            conversation_id: 数据库会话ID（用于继续对话）
            persistence_service: 持久化服务

        Returns:
            Agent实例
        """
        logger.debug(f"[AgentManager] get_or_create_agent - session={session_id}, conversation_id={conversation_id}")

        # 尝试获取现有agent
        agent = self.get_agent(session_id)

        if agent:
            logger.debug(f"[AgentManager] 返回已存在的Agent")
            # 如果有持久化服务但agent还没设置，则设置
            if persistence_service and conversation_id and not agent.db_conversation_id:
                agent.set_persistence(persistence_service, conversation_id)
            return agent

        # 创建新agent
        logger.debug(f"[AgentManager] 创建新Agent")
        return self.create_agent(
            session_id=session_id,
            patient_id=patient_id,
            agent_type=agent_type,
            role=role,
            conversation_id=conversation_id,
            persistence_service=persistence_service
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

    def get_conversation(self, session_id: str) -> Optional[Any]:
        """
        获取用于对话导出的agent

        Args:
            session_id: 会话ID

        Returns:
            Agent实例，如果不存在则返回None
        """
        return self.get_agent(session_id)

    def __repr__(self) -> str:
        return f"<AgentManager agents={len(self.agents)} sessions={self.get_active_sessions_count()}>"
