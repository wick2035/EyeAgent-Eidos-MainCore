"""
AgentType 枚举
"""
from enum import Enum


class AgentType(str, Enum):
    """智能体类型枚举"""
    
    HEALTH = "health"  # 1号智能体 - 健康咨询和预约
    REPORT = "report"  # 2号智能体 - 病例报告和历史分析
    REMINDER = "reminder"  # 3号智能体 - 提醒管理
    
    def __str__(self):
        return self.value
    
    @classmethod
    def from_string(cls, value: str) -> "AgentType":
        """从字符串创建枚举"""
        value_lower = value.lower()
        for agent_type in cls:
            if agent_type.value == value_lower:
                return agent_type
        raise ValueError(f"无效的智能体类型: {value}")
    
    def get_display_name(self) -> str:
        """获取显示名称"""
        display_names = {
            AgentType.HEALTH: "健康咨询智能体",
            AgentType.REPORT: "报告分析智能体",
            AgentType.REMINDER: "提醒管理智能体",
        }
        return display_names.get(self, self.value)

