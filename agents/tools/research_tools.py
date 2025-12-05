"""
ResearchAgent 专用工具
科研数据查询、网页搜索、机构数据库访问

Created: 2025-12-03
"""
import json
import logging
from typing import Optional
from langchain.tools import tool

from infrastructure.api.backend_client import get_api_client, APIError, NetworkError

logger = logging.getLogger(__name__)


# ========== 机构数据库查询工具 ==========

@tool
def get_institution_research_data(
    doctor_id: str,
    data_type: str,
    date_range_start: Optional[str] = None,
    date_range_end: Optional[str] = None,
    limit: int = 100
) -> str:
    """
    获取机构数据库全部内容进行科研分析。

    【权限要求】仅医生可调用，需要机构数据库访问权限开关开启。

    Args:
        doctor_id: 医生UUID
        data_type: 数据类型，可选值：
            - "patients": 患者基础信息
            - "appointments": 预约记录
            - "prescriptions": 处方记录
            - "scans": 扫描检查数据
            - "all": 全部数据
        date_range_start: 开始日期，格式 yyyy-MM-dd（可选）
        date_range_end: 结束日期，格式 yyyy-MM-dd（可选）
        limit: 返回记录数限制（默认100）

    Returns:
        JSON格式的机构数据，包含total_count、data、metadata字段

    使用场景：
        - 疾病流行病学研究
        - 治疗效果统计分析
        - 药物使用模式分析
        - 患者队列研究

    数据脱敏说明：
        - 所有患者数据默认经过后端脱敏处理
        - 患者姓名、电话、身份证等敏感信息已脱敏
    """
    try:
        logger.info(f"[ResearchTool] get_institution_research_data: doctor={doctor_id}, type={data_type}")

        # 验证data_type
        valid_types = ["patients", "appointments", "prescriptions", "scans", "all"]
        if data_type not in valid_types:
            return json.dumps({
                "error": True,
                "message": f"无效的数据类型: {data_type}，有效值: {valid_types}"
            }, ensure_ascii=False)

        client = get_api_client()

        # TODO: 调用后端API获取机构数据（等待Java后端实现该接口）
        # result = client.get_institution_research_data(doctor_id, data_type, date_range_start, date_range_end, limit)

        # 临时返回：提示接口待实现
        result = {
            "status": "pending",
            "message": "机构数据库接口待后端实现，请联系开发团队",
            "request_info": {
                "doctor_id": doctor_id,
                "data_type": data_type,
                "date_range": {
                    "start": date_range_start,
                    "end": date_range_end
                },
                "limit": limit
            }
        }

        return json.dumps(result, ensure_ascii=False)

    except (APIError, NetworkError) as e:
        error_msg = f"获取机构数据失败: {str(e)}"
        logger.error(f"[ResearchTool Error] {error_msg}")
        return json.dumps({"error": True, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"获取机构数据异常: {str(e)}"
        logger.error(f"[ResearchTool Error] {error_msg}", exc_info=True)
        return json.dumps({"error": True, "message": error_msg}, ensure_ascii=False)


# ========== 网页搜索工具 ==========

@tool
def web_search_medical(
    query: str,
    search_types: str = "general",
    max_results: int = 5,
    crawl_content: bool = False
) -> str:
    """
    搜索医学文献和最新研究。

    【权限要求】需要网页搜索开关开启。

    Args:
        query: 搜索关键词
        search_types: 搜索类型，多个用逗号分隔，可选值：
            - "general": 通用网页搜索（Google）
            - "pubmed": PubMed医学文献数据库
            - "scholar": Google Scholar学术搜索
            示例: "general,pubmed" 同时搜索通用和PubMed
        max_results: 每种类型的最大结果数（默认5，最大20）
        crawl_content: 是否爬取页面完整内容（默认False，开启会消耗更多时间和资源）

    Returns:
        JSON格式的搜索结果，按类型分组：
        {{
            "query": "搜索词",
            "total_results": 15,
            "results_by_type": {{
                "general": [{{"title", "url", "snippet"}}, ...],
                "pubmed": [{{"title", "url", "snippet"}}, ...]
            }}
        }}

    使用场景：
        - 查找最新研究进展
        - 文献综述准备
        - 治疗方案参考
        - 临床指南更新
        - 了解疾病最新诊疗信息

    搜索建议：
        - 使用专业医学术语可获得更精确的结果
        - PubMed搜索适合查找临床研究和循证医学证据
        - Scholar搜索适合查找学术论文和引用
    """
    try:
        logger.info(f"[ResearchTool] web_search_medical: query='{query}', types='{search_types}'")

        # 解析搜索类型
        types_list = [t.strip().lower() for t in search_types.split(",") if t.strip()]
        if not types_list:
            types_list = ["general"]

        # 验证搜索类型
        valid_types = {"general", "pubmed", "scholar"}
        invalid_types = [t for t in types_list if t not in valid_types]
        if invalid_types:
            logger.warning(f"[ResearchTool] 无效的搜索类型将被忽略: {invalid_types}")
            types_list = [t for t in types_list if t in valid_types]

        if not types_list:
            return json.dumps({
                "error": True,
                "message": f"没有有效的搜索类型，有效值: {valid_types}"
            }, ensure_ascii=False)

        # 限制max_results
        max_results = min(max(1, max_results), 20)

        # 使用Search1API进行搜索
        from infrastructure.api.search1api_client import get_search1api_client

        client = get_search1api_client()

        if not client.is_available():
            return json.dumps({
                "error": True,
                "message": "网页搜索服务未配置，请联系管理员配置SEARCH1API_KEY"
            }, ensure_ascii=False)

        # 同步调用并行搜索
        crawl_results = 1 if crawl_content else 0
        results = client.search_sync(query, types_list, max_results, crawl_results)

        # 格式化结果
        formatted_results = {}
        for search_type, items in results.items():
            formatted_results[search_type] = [
                {
                    "title": item.title,
                    "url": item.url,
                    "snippet": item.snippet,
                    "content": item.content[:500] + "..." if item.content and len(item.content) > 500 else item.content
                }
                for item in items
            ]

        total_count = sum(len(items) for items in formatted_results.values())

        response = {
            "query": query,
            "search_types": types_list,
            "total_results": total_count,
            "results_by_type": formatted_results
        }

        logger.info(f"[ResearchTool] 搜索完成，共{total_count}条结果")
        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        error_msg = f"网页搜索失败: {str(e)}"
        logger.error(f"[ResearchTool Error] {error_msg}", exc_info=True)
        return json.dumps({"error": True, "message": error_msg}, ensure_ascii=False)


# ========== 继承自现有Agent的工具（排除报告生成）==========

from agents.tools.agent_tools import (
    # 通用工具
    get_current_time,
    # Agent 1 工具
    get_patient_prescription,
    get_doctor_free_time,
    reserve_doctor,
    # Agent 2 工具（排除PDF生成）
    get_patient_prescription_limit,
    get_patient_prescription_detail,
    get_patient_scan_data,
    # 排除: generate_medical_record_pdf
    # 排除: generate_prescription_pdf
    # Agent 3 工具
    get_patient_reminder,
    get_patient_reminder_config,
    init_patient_reminder_config,
    modify_patient_reminder_config,
    create_reminder,
)


# ========== 阶段二工具导入 ==========

from agents.tools.research_tools_v2 import (
    statistical_analysis,
    summarize_medical_literature,
    generate_research_visualization,
    design_research_protocol,
    PHASE2_TOOLS,
)


# ========== 阶段三工具导入 ==========

from agents.tools.research_tools_v3 import (
    assist_paper_writing,
    search_clinical_guidelines,
    check_drug_interactions,
    find_similar_cases,
    ethics_review_assistant,
    export_research_data,
    PHASE3_TOOLS,
)


# ========== 工具列表 ==========

# 继承的工具列表（排除报告生成）
INHERITED_TOOLS = [
    # 通用工具
    get_current_time,
    # Agent 1 - 预约相关
    get_patient_prescription,
    get_doctor_free_time,
    reserve_doctor,
    # Agent 2 - 处方/扫描数据（排除PDF生成）
    get_patient_prescription_limit,
    get_patient_prescription_detail,
    get_patient_scan_data,
    # Agent 3 - 提醒管理
    get_patient_reminder,
    get_patient_reminder_config,
    init_patient_reminder_config,
    modify_patient_reminder_config,
    create_reminder,
]

# 科研专用工具（阶段一）
RESEARCH_PHASE1_TOOLS = [
    get_institution_research_data,
    web_search_medical,
]

# 科研专用工具（阶段二）
RESEARCH_PHASE2_TOOLS = PHASE2_TOOLS  # [statistical_analysis, summarize_medical_literature, generate_research_visualization, design_research_protocol]

# 科研专用工具（阶段三）
RESEARCH_PHASE3_TOOLS = PHASE3_TOOLS  # [assist_paper_writing, search_clinical_guidelines, check_drug_interactions, find_similar_cases, ethics_review_assistant, export_research_data]

# 所有科研专用工具
RESEARCH_SPECIFIC_TOOLS = RESEARCH_PHASE1_TOOLS + RESEARCH_PHASE2_TOOLS + RESEARCH_PHASE3_TOOLS

# ResearchAgent 完整工具列表
RESEARCH_AGENT_TOOLS = INHERITED_TOOLS + RESEARCH_SPECIFIC_TOOLS


# ========== 模块信息 ==========
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Research Tools 模块信息")
    print("=" * 50)
    print(f"继承工具数量: {len(INHERITED_TOOLS)}")
    print(f"阶段一科研工具: {len(RESEARCH_PHASE1_TOOLS)}")
    print(f"阶段二科研工具: {len(RESEARCH_PHASE2_TOOLS)}")
    print(f"总工具数量: {len(RESEARCH_AGENT_TOOLS)}")

    print("\n继承的工具:")
    for i, tool in enumerate(INHERITED_TOOLS, 1):
        print(f"  {i}. {tool.name}")

    print("\n阶段一科研工具:")
    for i, tool in enumerate(RESEARCH_PHASE1_TOOLS, 1):
        print(f"  {i}. {tool.name}")

    print("\n阶段二科研工具:")
    for i, tool in enumerate(RESEARCH_PHASE2_TOOLS, 1):
        print(f"  {i}. {tool.name}")
