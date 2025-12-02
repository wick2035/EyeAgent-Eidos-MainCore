"""
ConversationStage 枚举
"""
from enum import Enum


class ConversationStage(str, Enum):
    """对话阶段枚举（所有智能体通用）"""
    
    # ========== Health Agent 阶段 ==========
    GREETING = "greeting"  # 问候阶段
    HEALTH_CONSULTATION = "health_consultation"  # 健康咨询
    SYMPTOM_ASSESSMENT = "symptom_assessment"  # 症状评估
    APPOINTMENT_INQUIRY = "appointment_inquiry"  # 询问是否预约
    PATIENT_INFO_COLLECTION = "patient_info_collection"  # 收集患者信息
    OPHTHALMOLOGY_TRIAGE = "ophthalmology_triage"  # 眼科分诊
    MEDICAL_HISTORY = "medical_history"  # 病史采集
    APPOINTMENT_BOOKING = "appointment_booking"  # 预约医生
    
    # ========== Report Agent 阶段 ==========
    SELECT_ACTION = "select_action"  # 选择操作
    GENERATE_REPORT = "generate_report"  # 生成报告
    ANALYZE_HISTORY = "analyze_history"  # 分析历史
    ANSWER_QUESTION = "answer_question"  # 回答问题
    COMPARE_RECORDS = "compare_records"  # 对比记录
    
    # ========== Reminder Agent 阶段 ==========
    VIEW_REMINDERS = "view_reminders"  # 查看提醒
    CREATE_REMINDER = "create_reminder"  # 创建提醒
    UPDATE_REMINDER = "update_reminder"  # 更新提醒
    CONFIG_SETTINGS = "config_settings"  # 配置设置
    GENERATE_BIOMECHANICS_REPORT = "generate_biomechanics_report"  # 生成生物力学报告
    
    # ========== 通用阶段 ==========
    COMPLETED = "completed"  # 完成
    
    def __str__(self):
        return self.value
    
    @classmethod
    def from_string(cls, value: str) -> "ConversationStage":
        """从字符串创建枚举"""
        value_lower = value.lower()
        for stage in cls:
            if stage.value == value_lower:
                return stage
        raise ValueError(f"无效的对话阶段: {value}")
    
    def is_health_stage(self) -> bool:
        """是否是健康咨询智能体的阶段"""
        health_stages = [
            self.GREETING,
            self.HEALTH_CONSULTATION,
            self.SYMPTOM_ASSESSMENT,
            self.APPOINTMENT_INQUIRY,
            self.PATIENT_INFO_COLLECTION,
            self.OPHTHALMOLOGY_TRIAGE,
            self.MEDICAL_HISTORY,
            self.APPOINTMENT_BOOKING,
        ]
        return self in health_stages
    
    def is_report_stage(self) -> bool:
        """是否是报告分析智能体的阶段"""
        report_stages = [
            self.GREETING,
            self.SELECT_ACTION,
            self.GENERATE_REPORT,
            self.ANALYZE_HISTORY,
            self.ANSWER_QUESTION,
            self.COMPARE_RECORDS,
        ]
        return self in report_stages
    
    def is_reminder_stage(self) -> bool:
        """是否是提醒管理智能体的阶段"""
        reminder_stages = [
            self.GREETING,
            self.SELECT_ACTION,
            self.VIEW_REMINDERS,
            self.CREATE_REMINDER,
            self.UPDATE_REMINDER,
            self.CONFIG_SETTINGS,
            self.GENERATE_BIOMECHANICS_REPORT,
        ]
        return self in reminder_stages

