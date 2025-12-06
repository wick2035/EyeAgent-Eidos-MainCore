"""
LangChain Tools 模块
封装所有后端 API 调用为 LangChain Tools，供 Agent 使用

Created: 2025-12-01
Author: Claude Code
"""

import json
import logging
from datetime import datetime
from langchain.tools import tool
from infrastructure.api.backend_client import get_api_client, APIError, NetworkError

logger = logging.getLogger(__name__)


# ========== Agent 1 预约相关工具 ==========

@tool
def get_patient_prescription(patient_id: str) -> str:
    """
    获取患者所有处方信息。

    Args:
        patient_id: 患者UUID

    Returns:
        处方信息JSON字符串

    使用场景：
    - 患者询问自己的处方历史
    - 预约前需要了解患者用药情况
    """
    try:
        logger.info(f"[Tool] get_patient_prescription: patient_id={patient_id}")
        client = get_api_client()
        result = client.get_patient_prescription(patient_id)
        return json.dumps(result, ensure_ascii=False)
    except (APIError, NetworkError) as e:
        error_msg = f"获取处方信息失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def get_doctor_free_time(patient_id: str, date: str, hospital_key: str) -> str:
    """
    获取指定日期医生的空闲时间段。

    Args:
        patient_id: 患者UUID
        date: 查询日期，格式 yyyy-MM-dd（如 "2025-12-15"）
        hospital_key: 医院关键字

    Returns:
        可用时间段和医生信息JSON字符串

    使用场景：
    - 患者想要预约医生，需要查询可用时间
    - 在确认预约时间前必须先调用此工具

    重要：预约前必须先调用此工具确认时间可用！
    """
    try:
        logger.info(f"[Tool] get_doctor_free_time: patient_id={patient_id}, date={date}, hospital={hospital_key}")
        client = get_api_client()
        result = client.get_doctor_free_time(patient_id, date, hospital_key)
        return json.dumps(result, ensure_ascii=False)
    except (APIError, NetworkError) as e:
        error_msg = f"查询医生空闲时间失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def reserve_doctor(
    patient_id: str,
    doctor_id: str,
    reserve_time: str,
    chief_complaint: str,
    present_illness: str,
    department: str = "眼科",
    medical_history: str = "",
    allergy_history: str = "",
    family_history: str = ""
) -> str:
    """
    为患者预约医生并创建病历记录。

    Args:
        patient_id: 患者UUID
        doctor_id: 医生UUID（从 get_doctor_free_time 返回结果中获取）
        reserve_time: 预约时间，格式 yyyy-MM-ddTHH:mm:ss（如 "2025-12-03T09:00:00"）
        chief_complaint: 主诉（必填，来自当前对话收集的信息）
        present_illness: 现病史（必填，来自当前对话收集的信息）
        department: 科室（默认"眼科"）
        medical_history: 既往史（使用系统提供的患者病史信息）
        allergy_history: 过敏史（使用系统提供的患者病史信息）
        family_history: 家族史（使用系统提供的患者病史信息）

    Returns:
        预约结果JSON字符串（包含预约ID、病历ID、患者信息等）

    使用场景：
    - 患者确认要预约医生
    - 必须先调用 get_doctor_free_time 确认时间可用后才能调用

    重要：
    1. 预约前必须先用 get_doctor_free_time 查询可用时间
    2. reserve_time 必须是查询结果中返回的可用时间段
    3. doctor_id 必须是 get_doctor_free_time 返回的 doctorId
    4. chief_complaint 和 present_illness 必须来自当前对话收集的信息
    5. medical_history/allergy_history/family_history 使用【患者病史信息】中的值
    """
    try:
        logger.info(f"[Tool] reserve_doctor: patient={patient_id}, doctor={doctor_id}, time={reserve_time}")

        # 只发送 API 文档要求的字段
        request_data = {
            "patientId": patient_id,
            "doctorId": doctor_id,
            "reserveTime": reserve_time,
            "medicalRecord": {
                "department": department,
                "chiefComplaint": chief_complaint,
                "presentIllness": present_illness,
                "medicalHistory": medical_history or "无",
                "allergyHistory": allergy_history or "无",
                "familyHistory": family_history or "无",
                "diagnosis": "待诊断"
            }
        }

        logger.info(f"[Tool] reserve_doctor 请求数据: {json.dumps(request_data, ensure_ascii=False)}")

        client = get_api_client()
        result = client.reserve_doctor(request_data)

        logger.info(f"[Tool Success] 预约成功: {result.get('id')}")
        return json.dumps(result, ensure_ascii=False)

    except (APIError, NetworkError) as e:
        error_msg = f"预约失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


# ========== Agent 2 报告/处方相关工具 ==========

@tool
def get_patient_prescription_limit(patient_id: str, limit: int = 5) -> str:
    """
    获取患者最近N份处方摘要信息。

    Args:
        patient_id: 患者UUID
        limit: 限制数量（默认5）

    Returns:
        最近N份处方摘要的JSON字符串

    使用场景：
    - 医生或患者需要查看最近的处方记录
    - 分析用药历史趋势
    """
    try:
        logger.info(f"[Tool] get_patient_prescription_limit: patient_id={patient_id}, limit={limit}")
        client = get_api_client()
        result = client.get_patient_prescription_limit(patient_id, limit)
        return json.dumps(result, ensure_ascii=False)
    except (APIError, NetworkError) as e:
        error_msg = f"获取处方列表失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def get_patient_prescription_detail(patient_id: str, limit: int = 5) -> str:
    """
    获取患者最近N份处方及详细药品信息。

    Args:
        patient_id: 患者UUID
        limit: 限制数量（默认5）

    Returns:
        包含详细药品信息的处方JSON字符串

    使用场景：
    - 需要查看具体的药品名称、剂量、用法等详细信息
    - 分析药物使用情况
    """
    try:
        logger.info(f"[Tool] get_patient_prescription_detail: patient_id={patient_id}, limit={limit}")
        client = get_api_client()
        result = client.get_patient_prescription_detail(patient_id, limit)
        return json.dumps(result, ensure_ascii=False)
    except (APIError, NetworkError) as e:
        error_msg = f"获取处方详情失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def get_patient_scan_data(medical_record_id: str) -> str:
    """
    获取患者生物力学扫描数据。

    Args:
        medical_record_id: 病历UUID

    Returns:
        生物力学扫描数据的JSON字符串

    使用场景：
    - 医生需要查看患者的眼部扫描数据
    - 分析病情时需要参考检查结果
    """
    try:
        logger.info(f"[Tool] get_patient_scan_data: medical_record_id={medical_record_id}")
        client = get_api_client()
        result = client.get_patient_scan_data(medical_record_id)
        return json.dumps(result, ensure_ascii=False)
    except (APIError, NetworkError) as e:
        error_msg = f"获取扫描数据失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def generate_medical_record_pdf(medical_record_id: str) -> str:
    """
    生成病历PDF报告。

    【重要】仅医生可调用此工具。患者调用会被拒绝。

    Args:
        medical_record_id: 病历UUID

    Returns:
        PDF文件下载URL或错误信息

    使用场景：
    - 医生需要生成正式的病历报告文件
    - 患者请求打印病历（需医生权限）
    """
    try:
        logger.info(f"[Tool] generate_medical_record_pdf: medical_record_id={medical_record_id}")
        client = get_api_client()
        url = client.generate_medical_record_pdf(medical_record_id)
        success_msg = f"✅ 病历PDF生成成功！\n\n下载地址：{url}\n\n请点击链接下载或查看报告。"
        logger.info(f"[Tool Success] PDF URL: {url}")
        return success_msg
    except (APIError, NetworkError) as e:
        error_msg = f"❌ 生成病历PDF失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def generate_prescription_pdf(medical_record_id: str) -> str:
    """
    生成处方PDF报告。

    【重要】仅医生可调用此工具。患者调用会被拒绝。

    Args:
        medical_record_id: 病历UUID

    Returns:
        PDF文件下载URL或错误信息

    使用场景：
    - 医生需要生成正式的处方单文件
    - 患者请求打印处方（需医生权限）
    """
    try:
        logger.info(f"[Tool] generate_prescription_pdf: medical_record_id={medical_record_id}")
        client = get_api_client()
        url = client.generate_prescription_pdf(medical_record_id)
        success_msg = f"✅ 处方PDF生成成功！\n\n下载地址：{url}\n\n请点击链接下载或查看处方单。"
        logger.info(f"[Tool Success] PDF URL: {url}")
        return success_msg
    except (APIError, NetworkError) as e:
        error_msg = f"❌ 生成处方PDF失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


# ========== Agent 3 提醒相关工具 ==========

@tool
def get_patient_reminder(patient_id: str, limit: int = 5) -> str:
    """
    获取患者最近的提醒信息。

    Args:
        patient_id: 患者UUID
        limit: 限制数量（默认5）

    Returns:
        包含患者信息和提醒列表的JSON字符串

    使用场景：
    - 患者查询自己的提醒事项
    - 查看预约提醒、用药提醒等
    """
    try:
        logger.info(f"[Tool] get_patient_reminder: patient_id={patient_id}, limit={limit}")
        client = get_api_client()
        result = client.get_patient_reminder(patient_id, limit)
        return json.dumps(result, ensure_ascii=False)
    except (APIError, NetworkError) as e:
        error_msg = f"获取提醒信息失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def get_patient_reminder_config(patient_id: str) -> str:
    """
    获取患者的提醒配置。

    Args:
        patient_id: 患者UUID

    Returns:
        包含患者信息和提醒配置的JSON字符串

    使用场景：
    - 查看患者的提醒偏好设置
    - 在修改配置前查看当前配置
    """
    try:
        logger.info(f"[Tool] get_patient_reminder_config: patient_id={patient_id}")
        client = get_api_client()
        result = client.get_patient_reminder_config(patient_id)
        return json.dumps(result, ensure_ascii=False)
    except (APIError, NetworkError) as e:
        error_msg = f"获取提醒配置失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def init_patient_reminder_config(
    patient_id: str,
    enable_follow_up: bool = True,
    enable_appointment: bool = True,
    enable_medication: bool = True,
    default_advance_days: int = 3,
    preferred_notification_method: str = "APP",
    quiet_hours_start: str = "22:00:00",
    quiet_hours_end: str = "08:00:00"
) -> str:
    """
    初始化患者提醒配置（仅限首次创建）。

    【重要】如果患者已存在提醒配置，会返回错误，应使用 modify_patient_reminder_config 修改。

    Args:
        patient_id: 患者UUID
        enable_follow_up: 启用复诊提醒（默认True）
        enable_appointment: 启用预约提醒（默认True）
        enable_medication: 启用用药提醒（默认True）
        default_advance_days: 默认提前天数（默认3天）
        preferred_notification_method: 首选通知方式，可选值：APP/SMS/EMAIL（默认APP）
        quiet_hours_start: 免打扰开始时间，格式 HH:mm:ss（默认22:00:00）
        quiet_hours_end: 免打扰结束时间，格式 HH:mm:ss（默认08:00:00）

    Returns:
        创建的配置JSON字符串

    使用场景：
    - 新患者第一次设置提醒偏好
    - 初始化默认提醒配置

    错误处理：
    - 如果患者已存在配置，会返回错误信息
    """
    try:
        logger.info(f"[Tool] init_patient_reminder_config: patient_id={patient_id}")

        config_data = {
            "enableFollowUp": enable_follow_up,
            "enableAppointment": enable_appointment,
            "enableMedication": enable_medication,
            "defaultAdvanceDays": default_advance_days,
            "preferredNotificationMethod": preferred_notification_method,
            "quietHoursStart": quiet_hours_start,
            "quietHoursEnd": quiet_hours_end
        }

        request_data = {
            "patientId": patient_id,
            "config": config_data
        }

        client = get_api_client()
        result = client.init_patient_reminder_config(request_data)
        return json.dumps(result, ensure_ascii=False)
    except (APIError, NetworkError) as e:
        error_msg = f"初始化提醒配置失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def modify_patient_reminder_config(
    patient_id: str,
    enable_follow_up: bool = True,
    enable_appointment: bool = True,
    enable_medication: bool = True,
    default_advance_days: int = 3,
    preferred_notification_method: str = "APP",
    quiet_hours_start: str = "22:00:00",
    quiet_hours_end: str = "08:00:00"
) -> str:
    """
    修改患者提醒配置。

    【重要】患者必须已存在提醒配置，否则会返回错误，应使用 init_patient_reminder_config 初始化。

    Args:
        patient_id: 患者UUID
        enable_follow_up: 启用复诊提醒（默认True）
        enable_appointment: 启用预约提醒（默认True）
        enable_medication: 启用用药提醒（默认True）
        default_advance_days: 默认提前天数（默认3天）
        preferred_notification_method: 首选通知方式，可选值：APP/SMS/EMAIL（默认APP）
        quiet_hours_start: 免打扰开始时间，格式 HH:mm:ss（默认22:00:00）
        quiet_hours_end: 免打扰结束时间，格式 HH:mm:ss（默认08:00:00）

    Returns:
        更新后的配置JSON字符串

    使用场景：
    - 患者想要修改提醒偏好设置
    - 调整免打扰时间、通知方式等

    错误处理：
    - 如果患者不存在配置，会返回错误信息
    """
    try:
        logger.info(f"[Tool] modify_patient_reminder_config: patient_id={patient_id}")

        config_data = {
            "enableFollowUp": enable_follow_up,
            "enableAppointment": enable_appointment,
            "enableMedication": enable_medication,
            "defaultAdvanceDays": default_advance_days,
            "preferredNotificationMethod": preferred_notification_method,
            "quietHoursStart": quiet_hours_start,
            "quietHoursEnd": quiet_hours_end
        }

        request_data = {
            "patientId": patient_id,
            "config": config_data
        }

        client = get_api_client()
        result = client.modify_patient_reminder_config(request_data)
        return json.dumps(result, ensure_ascii=False)
    except (APIError, NetworkError) as e:
        error_msg = f"修改提醒配置失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def create_reminder(
    patient_id: str,
    reminder_type: str,
    reminder_title: str,
    reminder_content: str,
    scheduled_time: str,
    advance_days: int = 1,
    priority: str = "NORMAL",
    repeat_type: str = "NONE",
    notification_method: str = "APP",
    medical_record_id: str = "",
    appointment_id: str = "",
    prescription_id: str = "",
    max_repeat_count: int = 1,
    notes: str = ""
) -> str:
    """
    创建患者提醒。

    Args:
        patient_id: 患者UUID
        reminder_type: 提醒类型，可选值：RESERVE(预约/复诊/看病)/MEDICATION(用药)
        reminder_title: 提醒标题
        reminder_content: 提醒内容
        scheduled_time: 计划提醒时间，格式 yyyy-MM-ddTHH:mm:ss（如 "2025-12-10T09:00:00"）
        advance_days: 提前天数（默认1天）
        priority: 优先级，可选值：LOW/NORMAL/HIGH/URGENT（默认NORMAL）
        repeat_type: 重复类型，可选值：NONE/DAILY/WEEKLY/MONTHLY（默认NONE）
        notification_method: 通知方式，可选值：APP/SMS/EMAIL（默认APP）
        medical_record_id: 关联病历ID（可选）
        appointment_id: 关联预约ID（可选）
        prescription_id: 关联处方ID（可选）
        max_repeat_count: 最大重复次数（默认1）
        notes: 备注（可选）

    Returns:
        创建结果JSON字符串

    使用场景：
    - 为患者创建新的提醒事项
    - 设置用药提醒、复诊提醒、预约提醒等

    示例：
    - 预约/复诊提醒：reminder_type="RESERVE", scheduled_time="2025-12-15T09:00:00"
    - 用药提醒：reminder_type="MEDICATION", repeat_type="DAILY", max_repeat_count=7
    """
    try:
        logger.info(f"[Tool] create_reminder: patient_id={patient_id}, type={reminder_type}, scheduled={scheduled_time}")

        # 转换枚举值为大写
        reminder_type = reminder_type.upper()
        priority = priority.upper()
        repeat_type = repeat_type.upper()
        notification_method = notification_method.upper()

        # 提醒类型映射（API 只接受 RESERVE/MEDICATION/SYSTEM，患者只能创建前两种）
        TYPE_MAPPING = {
            "FOLLOW_UP": "RESERVE",      # 复诊 → 预约
            "APPOINTMENT": "RESERVE",    # 预约 → 预约
            "RESERVE": "RESERVE",        # 预约 → 预约
            "MEDICATION": "MEDICATION",  # 用药 → 用药
        }
        reminder_type = TYPE_MAPPING.get(reminder_type, "RESERVE")

        reminder_data = {
            "reminderType": reminder_type,
            "reminderTitle": reminder_title,
            "reminderContent": reminder_content,
            "scheduledTime": scheduled_time,
            "advanceDays": advance_days,
            "priority": priority,
            "repeatType": repeat_type,
            "notificationMethod": notification_method,
            "maxRepeatCount": max_repeat_count,
            "notes": notes
        }

        # 添加可选的关联ID（只有非空时才添加）
        if medical_record_id:
            reminder_data["medicalRecordId"] = medical_record_id
        if appointment_id:
            reminder_data["appointmentId"] = appointment_id
        if prescription_id:
            reminder_data["prescriptionId"] = prescription_id

        request_data = {
            "patientId": patient_id,
            "reminder": reminder_data
        }

        client = get_api_client()
        result = client.create_reminder(request_data)
        return json.dumps(result, ensure_ascii=False)
    except (APIError, NetworkError) as e:
        error_msg = f"创建提醒失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


# ========== 通用工具 ==========

@tool
def get_current_time() -> str:
    """
    获取当前系统时间。

    Returns:
        包含当前日期和时间的JSON字符串，格式：
        {{
            "datetime": "2025-12-05T14:30:00",
            "date": "2025-12-05",
            "time": "14:30:00",
            "weekday": "星期四",
            "timestamp": 1733391000
        }}

    使用场景：
    - 预约时需要知道当前日期，判断用户请求的是哪一天
    - 创建提醒时需要确认时间的合理性
    - 用户询问"今天"、"明天"等相对时间时进行转换
    """
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

    result = {
        "datetime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": weekdays[now.weekday()],
        "timestamp": int(now.timestamp())
    }

    logger.info(f"[Tool] get_current_time: {result['datetime']}")
    return json.dumps(result, ensure_ascii=False)


# ========== 工具列表（按 Agent 分类）==========

# 通用工具（所有 Agent 共享）
COMMON_TOOLS = [
    get_current_time,
]

AGENT_1_TOOLS = COMMON_TOOLS + [
    get_patient_prescription,
    get_doctor_free_time,
    reserve_doctor,
]

AGENT_2_TOOLS = COMMON_TOOLS + [
    get_patient_prescription_limit,
    get_patient_prescription_detail,
    get_patient_scan_data,
    generate_medical_record_pdf,
    generate_prescription_pdf,
]

AGENT_3_TOOLS = COMMON_TOOLS + [
    get_patient_reminder,
    get_patient_reminder_config,
    init_patient_reminder_config,
    modify_patient_reminder_config,
    create_reminder,
]

# 所有工具的组合
ALL_TOOLS = AGENT_1_TOOLS + AGENT_2_TOOLS + AGENT_3_TOOLS


# ========== 使用示例 ==========
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO)

    print("Agent Tools 模块创建成功！")
    print(f"Agent 1 工具数量: {len(AGENT_1_TOOLS)}")
    print(f"Agent 2 工具数量: {len(AGENT_2_TOOLS)}")
    print(f"Agent 3 工具数量: {len(AGENT_3_TOOLS)}")
    print(f"总工具数量: {len(ALL_TOOLS)}")

    # 列出所有工具
    print("\n所有可用工具:")
    for i, tool in enumerate(ALL_TOOLS, 1):
        print(f"{i}. {tool.name}: {tool.description[:50]}...")
