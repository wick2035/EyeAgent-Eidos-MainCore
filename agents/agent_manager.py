"""
智能体管理器 - 管理多个智能体实例
"""
from typing import Dict, Any
from agents.agent_1 import HealthAgent


class AgentManager:
    """智能体管理器"""
    
    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.active_sessions: Dict[str, str] = {}  # session_id -> agent_id
    
    def create_agent(self, agent_id: str, agent_type: str = "health"):
        """创建新的智能体实例"""
        if agent_type == "health":
            self.agents[agent_id] = HealthAgent()
        else:
            raise ValueError(f"未知的智能体类型: {agent_type}")
        
        return self.agents[agent_id]
    
    def get_agent(self, agent_id: str):
        """获取智能体实例"""
        return self.agents.get(agent_id)
    
    def get_or_create_agent(self, session_id: str, agent_type: str = "health"):
        """获取或创建会话对应的智能体"""
        if session_id not in self.active_sessions:
            agent_id = f"{agent_type}_{session_id}"
            self.create_agent(agent_id, agent_type)
            self.active_sessions[session_id] = agent_id
        
        agent_id = self.active_sessions[session_id]
        return self.agents[agent_id]
    
    def remove_agent(self, session_id: str):
        """移除智能体"""
        if session_id in self.active_sessions:
            agent_id = self.active_sessions[session_id]
            if agent_id in self.agents:
                del self.agents[agent_id]
            del self.active_sessions[session_id]
    
    def reset_agent(self, session_id: str):
        """重置智能体"""
        agent = self.get_or_create_agent(session_id)
        if agent:
            agent.reset()
    
    def get_active_sessions_count(self) -> int:
        """获取活跃会话数"""
        return len(self.active_sessions)

