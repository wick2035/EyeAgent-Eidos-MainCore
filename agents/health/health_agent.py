"""
HealthAgent - 健康咨询、眼科分诊、医生预约
基于BaseAgent重构，集成后端API工具
"""
from typing import Dict, Any, Optional, TYPE_CHECKING
import logging

from agents.base.base_agent import BaseAgent
from domain.enums.agent_type import AgentType
from domain.enums.conversation_stage import ConversationStage
from agents.tools.agent_tools import AGENT_1_TOOLS

if TYPE_CHECKING:
    from application.services.chat_persistence_service import ChatPersistenceService

logger = logging.getLogger(__name__)


class HealthAgent(BaseAgent):
    """
    1号健康咨询智能体
    
    职责：
    - 健康咨询和症状评估
    - 眼科分诊问诊
    - 预约医生
    
    使用工具：
    - get_patient_prescription: 查询处方
    - get_doctor_free_time: 查询医生空闲时间
    - reserve_doctor: 预约医生
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
        初始化HealthAgent

        Args:
            patient_id: 患者UUID
            session_id: 会话ID（如果为空会自动生成）
            role: 用户角色（patient/doctor）
            doctor_id: 医生UUID（医生模式下使用）
            conversation_id: 数据库会话ID（用于继续对话）
            persistence_service: 持久化服务
        """
        import uuid
        session_id = session_id or f"health_{uuid.uuid4().hex[:8]}"

        # 调用父类初始化，传入Agent 1的工具
        super().__init__(
            patient_id=patient_id,
            session_id=session_id,
            agent_type=AgentType.HEALTH,
            role=role,
            doctor_id=doctor_id,
            tools=AGENT_1_TOOLS,
            conversation_id=conversation_id,
            persistence_service=persistence_service
        )
        
        # HealthAgent特有的状态
        self.needs_appointment = False
        self.appointment_confirmed = False
        self.collected_fields = set()

        # 已收集的病历信息（从对话中提取）
        self.chief_complaint_text = ""  # 主诉
        self.present_illness_text = ""  # 现病史

        logger.info(f"[HealthAgent] 初始化完成: patient={patient_id}")
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词（根据角色返回不同版本）"""
        if self.role == "doctor":
            return self._create_doctor_mode_prompt()
        return self._create_patient_mode_prompt()

    def _create_patient_mode_prompt(self) -> str:
        """患者模式提示词"""
        return """你叫小Eye，你是一位专业的EyeAgent平台医疗健康咨询助手，专门负责眼科相关的健康咨询和分诊服务。

你的职责：
1. 提供专业的健康咨询建议
2. 评估患者症状的严重程度
3. 在适当的时候主动询问患者是否需要预约医生
4. 进行详细的眼科分诊问诊，收集患者信息
5. 帮助患者完成医生预约

【⚠️ 极其重要：利用对话历史 ⚠️】
在回复之前，你必须仔细阅读【对话历史】中的所有内容！
- 如果患者之前已经描述过症状，不要重复询问
- 从对话历史中提取：主诉症状、现病史、症状持续时间等信息
- 调用工具时，使用对话历史中已收集的信息作为参数

【预约流程 - 必须遵守】
当患者表达预约意愿时，按以下步骤操作：

第一步：从对话历史中整合已知信息
- 回顾对话历史，整理患者已经描述的症状信息
- 如果主诉症状和现病史已在对话中提及，直接使用，不要重复询问
- 只询问尚未获取的信息（医院、日期）

第二步：查询可用时间（调用工具）
- 使用 get_doctor_free_time 工具查询医生空闲时间
- 参数：patient_id（已知）、date（患者期望日期，格式yyyy-MM-dd）、hospital_key（医院名称）
- 将查询结果告知患者，让患者选择具体时段

第三步：确认预约并完成
- 患者选择时段后，整合所有信息调用 reserve_doctor
- chief_complaint（主诉）：从对话历史中提取患者描述的主要症状
- present_illness（现病史）：从对话历史中提取症状的时间、程度、伴随情况等

【重要提示】
- 语气温和、专业、有同理心
- 绝对不要编造预约时间，必须调用工具查询真实数据
- 不要重复询问患者已经回答过的问题！
- 如果工具调用失败，告知患者并尝试解决

【需要收集的病历信息】
- 主诉症状：患者的主要不适（必填）- 通常在对话开始时患者就会描述
- 现病史：症状出现的时间、性质、程度（必填）- 需要追问补充
- 既往病史、过敏史、家族史：使用系统提供的【患者病史信息】,若为空可询问患者"""

    def _create_doctor_mode_prompt(self) -> str:
        """医生模式提示词"""
        return """你叫小Eye，你是一位专业的EyeAgent平台医疗助手，当前正在协助医生分析患者情况。

【⚠️ 重要】当前使用者是医生，不是患者！
- 对话历史中标记为"医生"的是医生的提问和指令
- 你的任务是帮助医生分析【患者信息】中的这位患者
- 绝对不要把医生当成患者，不要问医生"您有什么不适"或"您的症状是什么"

你的职责（医生模式）：
1. 协助医生分析患者的健康状况和症状
2. 根据医生要求提供专业的诊断建议和分析
3. 帮助医生查询患者的病史、处方、预约记录等数据
4. 协助医生为患者进行预约操作
5. 回答医生关于患者情况的问题

【工具使用】
- 所有工具中的 patient_id 使用【患者信息】中提供的患者ID
- 医生可以指示你查询患者的各项数据
- 预约时，预约的是【患者信息】中的患者，不是医生

【交互风格】
- 专业、简洁、高效
- 直接回答医生的问题，提供有价值的分析
- 不需要表达过多关怀语句（医生不是患者）
- 可以使用更专业的医学术语

【预约流程（医生模式）】
当医生要求为患者预约时：
1. 确认患者信息（从【患者信息】获取）
2. 询问医生期望的就诊日期和医院
3. 调用 get_doctor_free_time 查询可用时段
4. 医生确认后调用 reserve_doctor 完成预约"""
    
    def _get_stage_prompt(self) -> str:
        """获取当前阶段提示（根据角色返回不同版本）"""
        stage = self.conversation.stage

        if self.role == "doctor":
            # 医生模式的阶段提示
            stage_prompts = {
                ConversationStage.GREETING: "了解医生需要什么帮助",
                ConversationStage.HEALTH_CONSULTATION: "协助医生分析患者症状",
                ConversationStage.SYMPTOM_ASSESSMENT: "帮助医生评估患者症状严重程度",
                ConversationStage.APPOINTMENT_INQUIRY: "询问医生是否需要为患者预约",
                ConversationStage.PATIENT_INFO_COLLECTION: "确认患者信息是否完整",
                ConversationStage.OPHTHALMOLOGY_TRIAGE: "协助医生进行眼科分诊分析",
                ConversationStage.MEDICAL_HISTORY: "帮助医生查看患者病史",
                ConversationStage.APPOINTMENT_BOOKING: "协助医生为患者预约",
                ConversationStage.COMPLETED: "操作完成，向医生确认"
            }
        else:
            # 患者模式的阶段提示
            stage_prompts = {
                ConversationStage.GREETING: "初次接待，询问患者的健康问题",
                ConversationStage.HEALTH_CONSULTATION: "正在进行健康咨询，了解患者症状",
                ConversationStage.SYMPTOM_ASSESSMENT: "评估症状严重程度，判断是否需要就医",
                ConversationStage.APPOINTMENT_INQUIRY: "询问患者是否需要预约医生",
                ConversationStage.PATIENT_INFO_COLLECTION: "收集患者基本信息（姓名、年龄、性别、联系方式）",
                ConversationStage.OPHTHALMOLOGY_TRIAGE: "进行眼科分诊，详细询问症状表现",
                ConversationStage.MEDICAL_HISTORY: "采集完整病史（既往史、用药史、过敏史、家族史）",
                ConversationStage.APPOINTMENT_BOOKING: "确认预约详情，询问期望就诊时间",
                ConversationStage.COMPLETED: "预约已完成，总结信息并告知患者"
            }

        return stage_prompts.get(stage, "")
    
    def _handle_stage_transition(self, user_input: str, ai_response: str):
        """处理阶段转换逻辑"""
        stage = self.conversation.stage
        user_lower = user_input.lower()
        
        # 检测预约意图
        if not self.needs_appointment:
            appointment_keywords = ["预约", "挂号", "看医生", "就诊", "看病", "约医生", "约诊"]
            if any(kw in user_lower for kw in appointment_keywords):
                self.needs_appointment = True
                self.conversation.stage = ConversationStage.PATIENT_INFO_COLLECTION
                logger.info("[HealthAgent] 检测到预约意图，转入信息收集")
                return
        
        # 阶段转换逻辑
        if stage == ConversationStage.GREETING:
            if len(user_input) > 10:
                self.conversation.stage = ConversationStage.HEALTH_CONSULTATION
        
        elif stage == ConversationStage.HEALTH_CONSULTATION:
            self.conversation.stage = ConversationStage.SYMPTOM_ASSESSMENT
        
        elif stage == ConversationStage.SYMPTOM_ASSESSMENT:
            eye_keywords = ["眼", "视力", "模糊", "疼", "红", "痒", "流泪", "分泌物"]
            if any(kw in user_input for kw in eye_keywords):
                self.conversation.stage = ConversationStage.APPOINTMENT_INQUIRY
        
        elif stage == ConversationStage.APPOINTMENT_INQUIRY:
            positive_keywords = ["是", "好", "要", "需要", "可以", "行", "对", "嗯", "预约"]
            if any(kw in user_lower for kw in positive_keywords):
                self.needs_appointment = True
                self.conversation.stage = ConversationStage.PATIENT_INFO_COLLECTION
        
        elif stage == ConversationStage.PATIENT_INFO_COLLECTION:
            # 检查基本信息是否收集完成（简化判断）
            message_count = self.conversation_manager.get_message_count()
            if message_count >= 6:  # 至少3轮对话
                self.conversation.stage = ConversationStage.OPHTHALMOLOGY_TRIAGE
        
        elif stage == ConversationStage.OPHTHALMOLOGY_TRIAGE:
            message_count = self.conversation_manager.get_message_count()
            if message_count >= 10:
                self.conversation.stage = ConversationStage.MEDICAL_HISTORY
        
        elif stage == ConversationStage.MEDICAL_HISTORY:
            message_count = self.conversation_manager.get_message_count()
            if message_count >= 14:
                self.conversation.stage = ConversationStage.APPOINTMENT_BOOKING
        
        elif stage == ConversationStage.APPOINTMENT_BOOKING:
            # 等待预约确认
            if self.appointment_confirmed:
                self.conversation_manager.mark_completed()
    
    def _extract_info_from_input(self, user_input: str) -> Dict[str, Any]:
        """从用户输入中提取信息并累积记录"""
        extracted = {}

        # 检测并记录症状关键词
        symptom_keywords = {
            "视力问题": ["模糊", "看不清", "视力下降", "视力模糊", "看东西模糊"],
            "眼痛": ["疼", "痛", "刺痛", "胀痛", "酸痛"],
            "眼红": ["红", "充血", "发红", "红肿"],
            "眼痒": ["痒", "发痒"],
            "流泪": ["流泪", "眼泪", "泪水"],
            "干涩": ["干", "干涩", "干燥"],
        }

        for symptom_type, keywords in symptom_keywords.items():
            if any(kw in user_input for kw in keywords):
                extracted["symptom"] = symptom_type
                self.collected_fields.add("chief_complaint")
                # 记录原始描述作为主诉（累积）
                if not self.chief_complaint_text:
                    self.chief_complaint_text = user_input
                elif user_input not in self.chief_complaint_text:
                    self.chief_complaint_text += f"；{user_input}"
                break

        # 检测时间相关描述（现病史）
        time_keywords = ["今天", "昨天", "前天", "最近", "一周", "几天", "突然", "刚才", "早上", "下午"]
        if any(kw in user_input for kw in time_keywords):
            self.collected_fields.add("present_illness")
            if not self.present_illness_text:
                self.present_illness_text = user_input
            elif user_input not in self.present_illness_text:
                self.present_illness_text += f"；{user_input}"

        # 检测预约时间偏好
        if any(kw in user_input for kw in ["明天", "后天", "下周"]):
            extracted["has_time_preference"] = True
            self.collected_fields.add("appointment_date")

        # 检测医院信息
        hospital_keywords = ["温州眼视光", "眼视光医院", "医院"]
        if any(kw in user_input for kw in hospital_keywords):
            self.collected_fields.add("hospital")

        return extracted
    
    def _build_additional_context(self, extracted_info: Dict[str, Any]) -> str:
        """构建额外上下文（覆盖父类方法）"""
        # 先调用父类方法获取患者基本信息
        context = super()._build_additional_context(extracted_info)

        # 添加已从对话中收集的信息总结
        context += "【⚠️ 已从对话中收集的信息 - 调用工具时直接使用，不要重复询问】\n"

        if hasattr(self, 'chief_complaint_text') and self.chief_complaint_text:
            context += f"✓ 主诉(chief_complaint): {self.chief_complaint_text}\n"
        else:
            context += "✗ 主诉(chief_complaint): 尚未收集\n"

        if hasattr(self, 'present_illness_text') and self.present_illness_text:
            context += f"✓ 现病史(present_illness): {self.present_illness_text}\n"
        else:
            context += "✗ 现病史(present_illness): 尚未收集\n"

        # 已收集字段列表
        if self.collected_fields:
            context += f"已收集字段: {', '.join(self.collected_fields)}\n"

        context += "\n"

        # 添加HealthAgent特有的上下文
        context += "【预约状态】\n"
        context += f"需要预约: {'是' if self.needs_appointment else '否'}\n"
        context += f"预约已确认: {'是' if self.appointment_confirmed else '否'}\n"

        if extracted_info:
            context += f"\n【当前轮次提取】\n{extracted_info}\n"

        return context
    
    def set_appointment_confirmed(self, confirmed: bool):
        """设置预约确认状态（由外部调用）"""
        self.appointment_confirmed = confirmed
        if confirmed:
            logger.info("[HealthAgent] 预约已确认")

