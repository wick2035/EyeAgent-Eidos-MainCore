"""
ReportAgent - 病例报告生成和历史分析
基于BaseAgent重构，集成后端API工具
"""
from typing import Dict, Any, Optional, TYPE_CHECKING
import logging

from agents.base.base_agent import BaseAgent
from domain.enums.agent_type import AgentType
from domain.enums.conversation_stage import ConversationStage
from agents.tools.agent_tools import AGENT_2_TOOLS

if TYPE_CHECKING:
    from application.services.chat_persistence_service import ChatPersistenceService

logger = logging.getLogger(__name__)


class ReportAgent(BaseAgent):
    """
    2号病例报告智能体
    
    职责：
    - 生成病历和处方PDF
    - 分析患者历史记录
    - 对比多次就诊数据
    
    使用工具：
    - get_patient_prescription_limit: 获取处方摘要
    - get_patient_prescription_detail: 获取处方详情
    - get_patient_scan_data: 获取扫描数据
    - generate_medical_record_pdf: 生成病历PDF
    - generate_prescription_pdf: 生成处方PDF
    """
    
    def __init__(
        self,
        patient_id: str,
        session_id: str = None,
        role: str = "patient",
        conversation_id: Optional[str] = None,
        persistence_service: Optional["ChatPersistenceService"] = None
    ):
        """
        初始化ReportAgent

        Args:
            patient_id: 患者UUID
            session_id: 会话ID
            role: 用户角色（patient/doctor）
            conversation_id: 数据库会话ID（用于继续对话）
            persistence_service: 持久化服务
        """
        import uuid
        session_id = session_id or f"report_{uuid.uuid4().hex[:8]}"

        super().__init__(
            patient_id=patient_id,
            session_id=session_id,
            agent_type=AgentType.REPORT,
            role=role,
            tools=AGENT_2_TOOLS,
            conversation_id=conversation_id,
            persistence_service=persistence_service
        )
        
        # ReportAgent特有状态
        self.selected_action = None
        self.selected_record_id = None
        
        logger.info(f"[ReportAgent] 初始化完成: patient={patient_id}")
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词"""
        return """你是小Report，一位专业的医疗报告助手，负责帮助患者和医生查看病历、处方和历史记录。

当前对话阶段：{stage}
用户角色：{role}

你的职责：
1. 生成病历和处方的PDF报告
2. 分析患者的历史就诊记录
3. 对比不同时期的检查结果
4. 回答关于病历和处方的问题

【重要提示】
- 如果用户是患者（patient），只能查看自己的报告，不能生成PDF（需要医生权限）
- 如果用户是医生（doctor），可以查看报告并生成PDF
- 对于敏感医疗信息要谨慎处理，确保数据安全

【可用操作】
1. 查看最近的处方记录
2. 查看详细的处方药品信息
3. 生成病历PDF报告（仅医生）
4. 生成处方PDF报告（仅医生）
5. 分析历史就诊趋势

{additional_context}

对话历史：
{history}

用户：{input}
助手："""
    
    def _get_stage_prompt(self) -> str:
        """获取当前阶段提示"""
        stage = self.conversation.stage
        
        stage_prompts = {
            ConversationStage.GREETING: "问候用户，了解需求",
            ConversationStage.SELECT_ACTION: "询问用户想要进行什么操作",
            ConversationStage.GENERATE_REPORT: "正在生成报告",
            ConversationStage.ANALYZE_HISTORY: "正在分析历史记录",
            ConversationStage.ANSWER_QUESTION: "回答用户关于报告的问题",
            ConversationStage.COMPARE_RECORDS: "对比不同时期的记录",
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
            if any(kw in user_lower for kw in ["生成", "导出", "pdf", "报告"]):
                self.conversation.stage = ConversationStage.GENERATE_REPORT
            elif any(kw in user_lower for kw in ["历史", "记录", "趋势", "分析"]):
                self.conversation.stage = ConversationStage.ANALYZE_HISTORY
            elif any(kw in user_lower for kw in ["对比", "比较"]):
                self.conversation.stage = ConversationStage.COMPARE_RECORDS
        
        elif stage in [ConversationStage.GENERATE_REPORT, 
                      ConversationStage.ANALYZE_HISTORY,
                      ConversationStage.COMPARE_RECORDS]:
            # 检查是否有后续问题
            if any(kw in user_lower for kw in ["谢谢", "好的", "明白", "知道了"]):
                self.conversation_manager.mark_completed()
    
    def _extract_info_from_input(self, user_input: str) -> Dict[str, Any]:
        """从用户输入中提取信息"""
        extracted = {}
        
        # 检测医疗记录ID（简化实现）
        if "记录" in user_input or "病历" in user_input:
            extracted["has_record_reference"] = True
        
        # 检测PDF请求
        if "pdf" in user_input.lower() or "生成" in user_input:
            extracted["wants_pdf"] = True
        
        return extracted
    
    def _build_additional_context(self, extracted_info: Dict[str, Any]) -> str:
        """构建额外上下文（覆盖父类方法）"""
        # 先调用父类方法获取患者基本信息
        context = super()._build_additional_context(extracted_info)

        # 添加ReportAgent特有的上下文
        context += f"【用户角色】{self.role}\n"

        if self.role == "patient":
            context += "权限: 只能查看报告，不能生成PDF\n"
        else:
            context += "权限: 可以查看和生成PDF报告\n"

        if extracted_info:
            context += f"\n【提取信息】{extracted_info}\n"

        return context

