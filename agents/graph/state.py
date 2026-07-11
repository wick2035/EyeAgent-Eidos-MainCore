"""
MedicalState - LangGraph 全局状态定义

该模块定义了医疗Agent系统的全局状态结构，
所有节点通过读取和更新此状态进行通信。
"""
from typing import TypedDict, List, Optional, Annotated, Any, Dict
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class MedicalState(TypedDict):
    """
    医疗Agent系统的全局状态

    设计原则：
    1. 消息使用 add_messages reducer 自动合并
    2. 其他字段使用覆盖更新
    3. 保持与原 Conversation 模型兼容
    """

    # ========== 消息历史 ==========
    # 使用 add_messages 实现消息自动追加
    messages: Annotated[List[BaseMessage], add_messages]

    # ========== 用户身份 ==========
    patient_id: Optional[str]                # 患者UUID；科研模式为空
    doctor_id: Optional[str]                 # 医生UUID（医生模式/科研模式）
    role: str                                # "patient" | "doctor"
    session_id: str                          # 会话ID
    conversation_id: Optional[str]           # 数据库会话ID（持久化用）

    # ========== 患者数据缓存 ==========
    patient_info: Optional[Dict[str, Any]]   # 患者基本信息
    patient_full_data: Optional[Dict[str, Any]]  # 患者完整数据（含病历）

    # ========== 对话状态 ==========
    current_agent: str                       # "health" | "report" | "reminder" | "research" | "compliance"
    stage: str                               # 当前对话阶段
    is_completed: bool                       # 对话是否完成
    is_streaming: bool                       # 是否流式模式

    # ========== 路由相关 ==========
    route_result: Optional[Dict[str, Any]]   # 路由决策结果
    should_switch_agent: bool                # 是否需要切换Agent

    # ========== HealthAgent 特有字段 ==========
    needs_appointment: bool                  # 是否需要预约
    collected_fields: List[str]              # 已收集的字段列表
    chief_complaint: str                     # 主诉症状
    present_illness: str                     # 现病史
    appointment_confirmed: bool              # 预约是否已确认

    # ========== ReportAgent 特有字段 ==========
    report_type: Optional[str]               # 报告类型
    selected_records: List[str]              # 选中的病历ID列表

    # ========== ReminderAgent 特有字段 ==========
    reminder_type: Optional[str]             # 提醒类型
    reminder_created: bool                   # 提醒是否已创建

    # ========== ComplianceAgent 特有字段 ==========
    compliance_review_type: Optional[str]        # 审查类型: "prescription" | "diagnosis" | "record" | "examination" | "full"
    compliance_review_completed: bool            # 审查是否完成

    # ========== RecommendationAgent 特有字段 ==========
    recommendation_mode: Optional[str]                      # "doctor" | "patient"
    recommendation_ui_elements: Optional[Dict[str, Any]]    # UI元素数据（产品卡片/选项）
    recommendation_completed: bool                          # 推荐流程是否完成
    selected_products: List[str]                            # 已选产品ID列表

    # ========== ResearchAgent 特有字段 ==========
    enable_institution_data: bool            # 机构数据库访问开关
    enable_web_search: bool                  # 网页搜索开关
    web_search_types: List[str]              # 搜索类型列表
    search_history: List[str]                # 搜索历史
    current_research_task: Optional[str]     # 当前研究任务
    collected_data: Dict[str, Any]           # 收集的研究数据

    # ========== 安全相关 ==========
    security_blocked: bool                   # 是否被安全拦截
    security_events: List[Dict[str, Any]]    # 安全事件记录

    # ========== 多模态附件 ==========
    attachments: Optional[List[Dict[str, Any]]]  # 附件引用列表（AttachmentRef 序列化）
    attachment_analysis: Optional[str]           # 附件预分析文字结果（由 chat_router 注入）
    platform_prepared: bool                      # 两阶段平台流；禁止从 state 读取分析正文

    # ========== 响应输出 ==========
    response: str                            # 最终响应文本（旧字段，保留兼容）
    last_response: str                       # 各 Agent 节点写入的最终响应文本，response_node / graph_manager 读取
    error: Optional[str]                     # 错误信息


def create_initial_state(
    patient_id: Optional[str],
    session_id: str,
    role: str = "patient",
    doctor_id: Optional[str] = None,
    agent_type: str = "health",
    conversation_id: Optional[str] = None,
    **kwargs
) -> MedicalState:
    """
    创建初始状态

    Args:
        patient_id: 患者UUID
        session_id: 会话ID
        role: 用户角色 ("patient" | "doctor")
        doctor_id: 医生UUID（医生模式下使用）
        agent_type: 初始Agent类型
        conversation_id: 数据库会话ID
        **kwargs: 其他初始化参数

    Returns:
        MedicalState: 初始化后的状态字典
    """
    return MedicalState(
        # 消息历史
        messages=[],

        # 用户身份
        patient_id=patient_id,
        doctor_id=doctor_id,
        role=role,
        session_id=session_id,
        conversation_id=conversation_id,

        # 患者数据
        patient_info=None,
        patient_full_data=None,

        # 对话状态
        current_agent=agent_type,
        stage="greeting",
        is_completed=False,
        is_streaming=kwargs.get("is_streaming", False),

        # 路由
        route_result=None,
        should_switch_agent=False,

        # HealthAgent
        needs_appointment=False,
        collected_fields=[],
        chief_complaint="",
        present_illness="",
        appointment_confirmed=False,

        # ReportAgent
        report_type=None,
        selected_records=[],

        # ReminderAgent
        reminder_type=None,
        reminder_created=False,

        # ComplianceAgent
        compliance_review_type=None,
        compliance_review_completed=False,

        # RecommendationAgent
        recommendation_mode=None,
        recommendation_ui_elements=None,
        recommendation_completed=False,
        selected_products=[],

        # ResearchAgent
        enable_institution_data=kwargs.get("enable_institution_data", False),
        enable_web_search=kwargs.get("enable_web_search", False),
        web_search_types=kwargs.get("web_search_types", []),
        search_history=[],
        current_research_task=None,
        collected_data={},

        # 安全
        security_blocked=False,
        security_events=[],

        # 多模态附件
        attachments=kwargs.get("attachments", None),
        attachment_analysis=kwargs.get("attachment_analysis", None),
        platform_prepared=kwargs.get("platform_prepared", False),

        # 响应
        response="",
        last_response="",
        error=None,
    )


def get_state_summary(state: MedicalState) -> Dict[str, Any]:
    """
    获取状态摘要（用于日志和调试）

    Args:
        state: 当前状态

    Returns:
        状态摘要字典
    """
    return {
        "patient_id": state.get("patient_id"),
        "session_id": state.get("session_id"),
        "current_agent": state.get("current_agent"),
        "stage": state.get("stage"),
        "is_completed": state.get("is_completed"),
        "message_count": len(state.get("messages", [])),
        "needs_appointment": state.get("needs_appointment"),
        "appointment_confirmed": state.get("appointment_confirmed"),
    }
