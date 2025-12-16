"""
ReminderAgent - 提醒管理（复诊提醒、用药提醒、预约提醒）
基于BaseAgent重构，集成后端API工具
"""
from typing import Dict, Any, Optional, TYPE_CHECKING
import logging

from agents.base.base_agent import BaseAgent
from domain.enums.agent_type import AgentType
from domain.enums.conversation_stage import ConversationStage
from agents.tools.agent_tools import AGENT_3_TOOLS

if TYPE_CHECKING:
    from application.services.chat_persistence_service import ChatPersistenceService

logger = logging.getLogger(__name__)


class ReminderAgent(BaseAgent):
    """
    3号提醒管理智能体
    
    职责：
    - 查看和管理患者的提醒
    - 创建新的提醒（用药、复诊等）
    - 配置提醒偏好设置
    
    使用工具：
    - get_patient_reminder: 获取提醒列表
    - get_patient_reminder_config: 获取提醒配置
    - create_reminder: 创建新提醒
    """
    
    def __init__(
        self,
        patient_id: str,
        session_id: str = None,
        role: str = "patient",
        doctor_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        persistence_service: Optional["ChatPersistenceService"] = None
    ):
        """
        初始化ReminderAgent

        Args:
            patient_id: 患者UUID
            session_id: 会话ID
            role: 用户角色（patient/doctor）
            doctor_id: 医生UUID（医生模式下使用）
            conversation_id: 数据库会话ID（用于继续对话）
            persistence_service: 持久化服务
        """
        import uuid
        session_id = session_id or f"reminder_{uuid.uuid4().hex[:8]}"

        super().__init__(
            patient_id=patient_id,
            session_id=session_id,
            agent_type=AgentType.REMINDER,
            role=role,
            doctor_id=doctor_id,
            tools=AGENT_3_TOOLS,
            conversation_id=conversation_id,
            persistence_service=persistence_service
        )
        
        # ReminderAgent特有状态
        self.pending_reminder_data = {}
        
        logger.info(f"[ReminderAgent] 初始化完成: patient={patient_id}")
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词（根据角色返回不同版本）"""
        if self.role == "doctor":
            return self._create_doctor_mode_prompt()
        return self._create_patient_mode_prompt()

    def _create_patient_mode_prompt(self) -> str:
        """患者模式提示词"""
        return """你是小Reminder，一位专业的健康提醒助手，负责帮助患者管理复诊提醒、预约提醒和用药提醒。

你的职责：
1. 查看患者的所有提醒事项
2. 创建新的提醒（用药提醒、复诊提醒、预约提醒等）
3. 管理和配置提醒偏好设置
4. 提供健康管理建议

【提醒类型】
- appointment: 预约提醒
- medication: 用药提醒
- followup: 复诊提醒
- checkup: 体检提醒

【重要提示】
- 创建提醒时需要明确：提醒类型、时间、内容
- 提醒时间格式：yyyy-MM-ddTHH:mm:ss（例如：2025-12-15T09:00:00）
- 语气友好亲切，让患者感受到关怀"""

    def _create_doctor_mode_prompt(self) -> str:
        """医生模式提示词"""
        return """你是小Reminder，一位专业的健康提醒助手，当前正在协助医生管理患者的提醒事项。

【⚠️ 重要】当前使用者是医生，不是患者！
- 对话历史中标记为"医生"的是医生的提问和指令
- 你的任务是帮助医生管理【患者信息】中这位患者的提醒
- 不要把医生当成患者

你的职责（医生模式）：
1. 查看患者的所有提醒事项
2. 帮助医生为患者创建提醒（用药、复诊、预约等）
3. 查看和配置患者的提醒设置
4. 提供提醒管理的专业支持

【提醒类型】
- appointment: 预约提醒
- medication: 用药提醒
- followup: 复诊提醒
- checkup: 体检提醒

【工具使用】
- 所有工具中的 patient_id 使用【患者信息】中的患者ID
- 医生可以为患者创建和管理提醒

【重要提示】
- 创建提醒时需要明确：提醒类型、时间、内容
- 提醒时间格式：yyyy-MM-ddTHH:mm:ss（例如：2025-12-15T09:00:00）

【交互风格】
- 专业、高效
- 直接执行医生的指令
- 确认关键信息后立即操作"""
    
    def _get_stage_prompt(self) -> str:
        """获取当前阶段提示（根据角色返回不同版本）"""
        stage = self.conversation.stage

        if self.role == "doctor":
            # 医生模式的阶段提示
            stage_prompts = {
                ConversationStage.GREETING: "了解医生需要什么帮助",
                ConversationStage.SELECT_ACTION: "询问医生想要进行什么操作",
                ConversationStage.VIEW_REMINDERS: "正在查看患者的提醒列表",
                ConversationStage.CREATE_REMINDER: "正在为患者创建新提醒",
                ConversationStage.UPDATE_REMINDER: "正在更新患者的提醒",
                ConversationStage.CONFIG_SETTINGS: "正在配置患者的提醒设置",
                ConversationStage.COMPLETED: "操作完成"
            }
        else:
            # 患者模式的阶段提示
            stage_prompts = {
                ConversationStage.GREETING: "问候患者，了解需求",
                ConversationStage.SELECT_ACTION: "询问患者想要进行什么操作",
                ConversationStage.VIEW_REMINDERS: "正在查看提醒列表",
                ConversationStage.CREATE_REMINDER: "正在创建新提醒，收集必要信息",
                ConversationStage.UPDATE_REMINDER: "正在更新提醒",
                ConversationStage.CONFIG_SETTINGS: "正在配置提醒设置",
                ConversationStage.COMPLETED: "操作完成"
            }

        return stage_prompts.get(stage, "")
    
    def _handle_stage_transition(self, user_input: str, ai_response: str):
        """处理阶段转换逻辑"""
        stage = self.conversation.stage
        user_lower = user_input.lower()
        
        if stage == ConversationStage.GREETING:
            self.conversation.stage = ConversationStage.SELECT_ACTION
        
        elif stage == ConversationStage.SELECT_ACTION:
            # 检测用户意图
            if any(kw in user_lower for kw in ["查看", "看看", "有哪些", "提醒"]):
                self.conversation.stage = ConversationStage.VIEW_REMINDERS
            elif any(kw in user_lower for kw in ["创建", "新建", "添加", "设置提醒"]):
                self.conversation.stage = ConversationStage.CREATE_REMINDER
            elif any(kw in user_lower for kw in ["配置", "设置", "偏好"]):
                self.conversation.stage = ConversationStage.CONFIG_SETTINGS
        
        elif stage == ConversationStage.CREATE_REMINDER:
            # 检查是否收集了必要信息
            if self.pending_reminder_data.get("type") and \
               self.pending_reminder_data.get("time") and \
               self.pending_reminder_data.get("content"):
                self.conversation_manager.mark_completed()
        
        elif stage in [ConversationStage.VIEW_REMINDERS, 
                      ConversationStage.CONFIG_SETTINGS]:
            if any(kw in user_lower for kw in ["谢谢", "好的", "明白", "知道了"]):
                self.conversation_manager.mark_completed()
    
    def _extract_info_from_input(self, user_input: str) -> Dict[str, Any]:
        """从用户输入中提取信息"""
        extracted = {}
        
        # 检测提醒类型
        if "用药" in user_input or "吃药" in user_input:
            extracted["reminder_type"] = "medication"
        elif "预约" in user_input:
            extracted["reminder_type"] = "appointment"
        elif "复诊" in user_input:
            extracted["reminder_type"] = "followup"
        
        # 检测时间（简化实现）
        if any(kw in user_input for kw in ["明天", "后天", "下周"]):
            extracted["has_time"] = True
        
        return extracted
    
    def _build_additional_context(self, extracted_info: Dict[str, Any]) -> str:
        """构建额外上下文（覆盖父类方法）"""
        # 先调用父类方法获取患者基本信息
        context = super()._build_additional_context(extracted_info)

        # 添加ReminderAgent特有的上下文
        if self.pending_reminder_data:
            context += f"【待创建提醒】{self.pending_reminder_data}\n"

        if extracted_info:
            context += f"\n【提取信息】{extracted_info}\n"

        return context
    
    def set_pending_reminder(self, reminder_type: str, reminder_time: str, content: str):
        """设置待创建的提醒数据"""
        self.pending_reminder_data = {
            "type": reminder_type,
            "time": reminder_time,
            "content": content
        }
        logger.info(f"[ReminderAgent] 设置待创建提醒: {self.pending_reminder_data}")

