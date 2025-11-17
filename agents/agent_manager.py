"""
智能体管理器 - 管理多个智能体实例
"""
from typing import Dict, Any
from agents.agent_1 import HealthAgent
from agents.agent_2 import ReportAgent


class AgentManager:
    """智能体管理器"""
    
    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.active_sessions: Dict[str, str] = {}  # session_id -> agent_id
    
    def create_agent(self, agent_id: str, agent_type: str = "health", user_id: int = None, phone_number: str = None, role: str = "patient"):
        """创建新的智能体实例"""
        print(f"[AgentManager] 创建新Agent - agent_id={agent_id}, type={agent_type}, user_id={user_id}, phone_number={phone_number}, role={role}")
        
        if agent_type == "health":
            self.agents[agent_id] = HealthAgent(user_id=user_id, phone_number=phone_number, role=role)
        elif agent_type == "report":
            self.agents[agent_id] = ReportAgent(patient_id=user_id, phone_number=phone_number, role=role)
        else:
            raise ValueError(f"未知的智能体类型: {agent_type}")
        
        print(f"[AgentManager] Agent创建完成 - total_agents={len(self.agents)}")
        return self.agents[agent_id]
    
    def get_agent(self, agent_id: str):
        """获取智能体实例"""
        return self.agents.get(agent_id)
    
    def get_or_create_agent(self, session_id: str, agent_type: str = "health", user_id: int = None, phone_number: str = None, role: str = "patient"):
        """获取或创建会话对应的智能体"""
        print(f"[AgentManager] get_or_create_agent 被调用 - session_id={session_id}, agent_type={agent_type}, user_id={user_id}, phone_number={phone_number}, role={role}")
        print(f"[AgentManager] 当前 active_sessions: {list(self.active_sessions.keys())}")
        
        if session_id not in self.active_sessions:
            print(f"[AgentManager] Session不存在，创建新Agent")
            agent_id = f"{agent_type}_{session_id}"
            self.create_agent(agent_id, agent_type, user_id=user_id, phone_number=phone_number, role=role)
            self.active_sessions[session_id] = agent_id
        else:
            print(f"[AgentManager] Session已存在，返回已有Agent")
        
        agent_id = self.active_sessions[session_id]
        agent = self.agents[agent_id]
        if hasattr(agent, 'user_id') and hasattr(agent, 'phone_number'):
            print(f"[AgentManager] 返回Agent - agent.user_id={agent.user_id}, agent.phone_number={agent.phone_number}")
        else:
            print(f"[AgentManager] 返回Agent - agent.patient_id={getattr(agent, 'patient_id', None)}")
        return agent
    
    def remove_agent(self, session_id: str):
        """移除智能体"""
        if session_id in self.active_sessions:
            agent_id = self.active_sessions[session_id]
            if agent_id in self.agents:
                del self.agents[agent_id]
            del self.active_sessions[session_id]
    
    def reset_agent(self, session_id: str):
        """重置智能体 - 完全删除并等待重新创建"""
        # 完全删除agent，下次get_or_create_agent时会重新创建
        # 这样可以确保切换用户后能加载新用户的历史信息
        self.remove_agent(session_id)
    
    def get_active_sessions_count(self) -> int:
        """获取活跃会话数"""
        return len(self.active_sessions)

