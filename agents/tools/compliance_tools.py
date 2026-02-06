"""
ComplianceAgent 专用工具
合规性审查：处方审查、诊断审查、病历文书审查、检查合理性审查

复用已有工具 + 新增审查结果保存/导出（stub 占位）
"""
import json
import logging
import uuid
from datetime import datetime
from langchain.tools import tool

logger = logging.getLogger(__name__)


# ========== 新增合规审查工具（stub 占位） ==========

@tool
def save_compliance_review(
    patient_id: str,
    doctor_id: str,
    review_type: str,
    review_content: str
) -> str:
    """
    保存合规性审查结果到后端。

    Args:
        patient_id: 患者UUID
        doctor_id: 医生UUID
        review_type: 审查类型，可选值：
            - "prescription": 处方合规审查
            - "diagnosis": 诊断合规审查
            - "record": 病历文书合规审查
            - "examination": 检查合理性审查
            - "full": 全面合规审查
        review_content: 审查内容（JSON格式字符串，包含审查结果详情）

    Returns:
        JSON格式的保存结果，包含 review_id 和保存状态

    使用场景：
    - 医生完成审查后保存审查记录
    - 需要留存审查结果作为质控依据
    """
    try:
        logger.info(
            f"[Tool] save_compliance_review: patient={patient_id}, "
            f"doctor={doctor_id}, type={review_type}"
        )

        if not patient_id or not doctor_id:
            return "保存失败: 缺少患者ID或医生ID"

        valid_types = ["prescription", "diagnosis", "record", "examination", "full"]
        if review_type not in valid_types:
            return f"保存失败: 无效的审查类型 '{review_type}'，可选值: {valid_types}"

        # TODO: 替换为真实后端 API 调用
        # client = get_api_client()
        # result = client.save_compliance_review(patient_id, doctor_id, review_type, review_content)
        review_id = str(uuid.uuid4())
        result = {
            "success": True,
            "review_id": review_id,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "review_type": review_type,
            "saved_at": datetime.now().isoformat(),
            "message": "审查结果已保存（stub模拟）"
        }

        logger.info(f"[Tool Success] save_compliance_review: review_id={review_id}")
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        error_msg = f"保存审查结果失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def generate_compliance_report_pdf(
    patient_id: str,
    doctor_id: str,
    review_content: str
) -> str:
    """
    生成合规性审查报告PDF文件。

    Args:
        patient_id: 患者UUID
        doctor_id: 医生UUID
        review_content: 审查报告内容（完整的审查结果文本）

    Returns:
        JSON格式的结果，包含PDF下载链接

    使用场景：
    - 医生需要导出审查报告作为正式文件
    - 质控记录存档
    """
    try:
        logger.info(
            f"[Tool] generate_compliance_report_pdf: patient={patient_id}, "
            f"doctor={doctor_id}"
        )

        if not patient_id or not doctor_id:
            return "生成失败: 缺少患者ID或医生ID"

        if not review_content:
            return "生成失败: 审查内容不能为空"

        # TODO: 替换为真实后端 API 调用
        # client = get_api_client()
        # result = client.generate_compliance_report_pdf(patient_id, doctor_id, review_content)
        report_id = str(uuid.uuid4())
        result = {
            "success": True,
            "report_id": report_id,
            "pdf_url": f"/api/compliance/reports/{report_id}/download",
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "generated_at": datetime.now().isoformat(),
            "message": "合规审查报告PDF已生成（stub模拟）"
        }

        logger.info(f"[Tool Success] generate_compliance_report_pdf: report_id={report_id}")
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        error_msg = f"生成审查报告PDF失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


# ========== 工具列表组装 ==========

# 从通用工具导入
from agents.tools.agent_tools import (
    get_current_time,
    get_patient_prescription_detail,
    get_patient_prescription_limit,
    get_patient_scan_data,
)

# 从科研工具导入联网搜索
from agents.tools.research_tools import web_search_medical

# 通用工具
COMPLIANCE_COMMON_TOOLS = [
    get_current_time,
]

# 数据获取工具（复用）
COMPLIANCE_DATA_TOOLS = [
    get_patient_prescription_detail,
    get_patient_prescription_limit,
    get_patient_scan_data,
]

# 搜索工具（复用）
COMPLIANCE_SEARCH_TOOLS = [
    web_search_medical,
]

# 合规审查专用工具（新增 stub）
COMPLIANCE_SPECIFIC_TOOLS = [
    save_compliance_review,
    generate_compliance_report_pdf,
]

# ComplianceAgent 完整工具列表
AGENT_5_TOOLS = (
    COMPLIANCE_COMMON_TOOLS
    + COMPLIANCE_DATA_TOOLS
    + COMPLIANCE_SEARCH_TOOLS
    + COMPLIANCE_SPECIFIC_TOOLS
)


# ========== 模块信息 ==========
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Compliance Tools 模块信息")
    print("=" * 50)
    print(f"通用工具数量: {len(COMPLIANCE_COMMON_TOOLS)}")
    print(f"数据获取工具: {len(COMPLIANCE_DATA_TOOLS)}")
    print(f"搜索工具: {len(COMPLIANCE_SEARCH_TOOLS)}")
    print(f"专用工具: {len(COMPLIANCE_SPECIFIC_TOOLS)}")
    print(f"总工具数量: {len(AGENT_5_TOOLS)}")

    print("\n所有可用工具:")
    for i, t in enumerate(AGENT_5_TOOLS, 1):
        print(f"  {i}. {t.name}: {t.description[:50]}...")
