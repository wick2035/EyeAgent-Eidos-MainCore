"""
HealthAgent 提示词模块

从 agents/health/health_agent.py 提取的提示词和上下文构建逻辑。
"""
from typing import Dict, Any, Optional
from datetime import datetime


# ========== 系统提示词 ==========

_PATIENT_MODE_PROMPT = """你叫小Eye，你是一位专业的EyeAgent平台医疗健康咨询助手，专门负责眼科相关的健康咨询和分诊服务。

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

第零步：获取当前日期（必须！）
- 在处理任何相对日期（如"今天"、"明天"、"下周一"）之前，必须先调用 get_current_time 工具
- 使用返回的日期信息来计算正确的目标日期
- 绝对不要猜测当前日期！系统提示中的【当前时间】可作为参考

第一步：从对话历史中整合已知信息
- 回顾对话历史，整理患者已经描述的症状信息
- 如果主诉症状和现病史已在对话中提及，直接使用，不要重复询问
- 只询问尚未获取的信息（医院、日期）

第二步：查询可用时间（调用工具）
- 使用 get_doctor_free_time 工具查询医生空闲时间
- 参数：patient_id（已知）、date（患者期望日期，格式yyyy-MM-dd）、hospital_key（医院名称）
- 日期必须是正确计算后的具体日期，如"2025-12-17"，而不是相对日期
- 将查询结果告知患者，让患者选择具体时段

第三步：确认预约并完成
- 患者选择时段后，整合所有信息调用 reserve_doctor
- chief_complaint（主诉）：从对话历史中提取患者描述的主要症状
- present_illness（现病史）：从对话历史中提取症状的时间、程度、伴随情况等
- reserve_time 必须使用从 get_doctor_free_time 返回的正确日期

【重要提示】
- 语气温和、专业、有同理心
- 绝对不要编造预约时间，必须调用工具查询真实数据
- 不要重复询问患者已经回答过的问题！
- 如果工具调用失败，告知患者并尝试解决

【需要收集的病历信息】
- 主诉症状：患者的主要不适（必填）- 通常在对话开始时患者就会描述
- 现病史：症状出现的时间、性质、程度（必填）- 需要追问补充
- 既往病史、过敏史、家族史：使用系统提供的【患者病史信息】,若为空可询问患者"""


_DOCTOR_MODE_PROMPT = """你叫小Eye，你是一位专业的EyeAgent平台医疗助手，当前正在协助医生分析患者情况。

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


# ========== 阶段提示词 ==========

_PATIENT_STAGE_PROMPTS = {
    "greeting": "初次接待，询问患者的健康问题",
    "health_consultation": "正在进行健康咨询，了解患者症状",
    "symptom_assessment": "评估症状严重程度，判断是否需要就医",
    "appointment_inquiry": "询问患者是否需要预约医生",
    "patient_info_collection": "收集患者基本信息（姓名、年龄、性别、联系方式）",
    "ophthalmology_triage": "进行眼科分诊，详细询问症状表现",
    "medical_history": "采集完整病史（既往史、用药史、过敏史、家族史）",
    "appointment_booking": "确认预约详情，询问期望就诊时间",
    "completed": "预约已完成。友好地回复用户，如果用户表示感谢，表达祝福；如果用户有其他问题，尽量帮助解答或引导用户重新开始新的咨询。",
}

_DOCTOR_STAGE_PROMPTS = {
    "greeting": "了解医生需要什么帮助",
    "health_consultation": "协助医生分析患者症状",
    "symptom_assessment": "帮助医生评估患者症状严重程度",
    "appointment_inquiry": "询问医生是否需要为患者预约",
    "patient_info_collection": "确认患者信息是否完整",
    "ophthalmology_triage": "协助医生进行眼科分诊分析",
    "medical_history": "帮助医生查看患者病史",
    "appointment_booking": "协助医生为患者预约",
    "completed": "操作完成，向医生确认",
}


def get_health_system_prompt(role: str = "patient") -> str:
    """
    获取 HealthAgent 系统提示词

    Args:
        role: 用户角色 ("patient" | "doctor")

    Returns:
        系统提示词字符串
    """
    if role == "doctor":
        return _DOCTOR_MODE_PROMPT
    return _PATIENT_MODE_PROMPT


def get_health_stage_prompt(stage: str, role: str = "patient") -> str:
    """
    获取当前阶段的提示词

    Args:
        stage: 对话阶段
        role: 用户角色

    Returns:
        阶段提示词字符串
    """
    stage_lower = stage.lower()

    if role == "doctor":
        return _DOCTOR_STAGE_PROMPTS.get(stage_lower, "")
    return _PATIENT_STAGE_PROMPTS.get(stage_lower, "")


def build_health_context(state: Dict[str, Any]) -> str:
    """
    构建 HealthAgent 上下文信息

    Args:
        state: MedicalState 状态字典

    Returns:
        上下文字符串
    """
    context_parts = []

    # 注入当前日期时间（解决日期解析问题）
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    context_parts.append(f"【当前时间】{now.strftime('%Y-%m-%d %H:%M')} {weekdays[now.weekday()]}")

    role = state.get("role", "patient")
    patient_info = state.get("patient_info")
    patient_id = state.get("patient_id", "未知")

    # 角色信息
    if role == "doctor":
        context_parts.append("【当前操作者】身份: 医生")
        if state.get("doctor_id"):
            context_parts.append(f"医生ID: {state['doctor_id']}")

    # 患者信息
    if patient_info:
        context_parts.append("\n【患者信息】")
        context_parts.append(f"患者ID: {patient_id}")
        context_parts.append(f"姓名: {patient_info.get('name', '未知')}")
        context_parts.append(f"年龄: {patient_info.get('age', '未知')}岁")
        context_parts.append(f"性别: {patient_info.get('gender', '未知')}")
        if patient_info.get("phone"):
            context_parts.append(f"联系方式: {patient_info['phone']}")

        # 病史信息
        if patient_info.get("medical_history"):
            context_parts.append(f"既往病史: {patient_info['medical_history']}")
        if patient_info.get("allergy_history"):
            context_parts.append(f"过敏史: {patient_info['allergy_history']}")
        if patient_info.get("family_history"):
            context_parts.append(f"家族史: {patient_info['family_history']}")
    else:
        context_parts.append(f"\n【患者ID】{patient_id}")

    # 已收集信息
    context_parts.append("\n【已收集信息】")
    if state.get("chief_complaint"):
        context_parts.append(f"✓ 主诉: {state['chief_complaint']}")
    else:
        context_parts.append("○ 主诉: 待收集")

    if state.get("present_illness"):
        context_parts.append(f"✓ 现病史: {state['present_illness']}")
    else:
        context_parts.append("○ 现病史: 待收集")

    # 预约状态
    needs_appointment = state.get("needs_appointment", False)
    appointment_confirmed = state.get("appointment_confirmed", False)

    context_parts.append("\n【预约状态】")
    if appointment_confirmed:
        context_parts.append("✓ 预约已确认")
    elif needs_appointment:
        context_parts.append("⏳ 等待预约确认")
    else:
        context_parts.append("○ 未发起预约")

    return "\n".join(context_parts)
