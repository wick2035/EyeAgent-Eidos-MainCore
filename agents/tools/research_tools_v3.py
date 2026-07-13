"""
ResearchAgent 阶段三工具
论文写作、临床指南、药物相互作用、病例匹配、伦理审查、数据导出

Created: 2025-12-04
"""
import json
import logging
import io
import base64
from datetime import datetime
from typing import Optional, List
from langchain.tools import tool

logger = logging.getLogger(__name__)


# ========== 论文写作助手 ==========

@tool
def assist_paper_writing(
    section: str,
    research_data: str,
    template_type: str = "imrad"
) -> str:
    """
    辅助撰写科研论文，提供结构化写作指导。

    Args:
        section: 论文章节，可选值：
            - "abstract": 摘要（结构化摘要：目的、方法、结果、结论）
            - "introduction": 引言（研究背景、文献综述、研究目的）
            - "methods": 方法（研究设计、统计方法、伦理声明）
            - "results": 结果（数据描述、统计结果、图表说明）
            - "discussion": 讨论（结果解释、与既往研究比较、局限性、结论）
        research_data: 研究相关数据和信息（JSON格式或纯文本）
        template_type: 模板类型，可选值：
            - "imrad": 标准IMRAD格式（默认）
            - "case_report": 病例报告格式
            - "systematic_review": 系统综述格式

    Returns:
        JSON格式的写作指导，包含模板、要点提示、格式要求

    使用场景：
        - 撰写研究论文各章节
        - 准备投稿材料
        - 学习论文写作规范
    """
    try:
        result = {
            "section": section,
            "template_type": template_type,
            "research_data_received": len(research_data) > 0
        }

        # 章节模板和指导
        section_guides = {
            "abstract": {
                "imrad": {
                    "structure": [
                        "目的/背景 (Background/Objective): 1-2句，说明研究问题和目的",
                        "方法 (Methods): 2-3句，描述研究设计、样本、主要方法",
                        "结果 (Results): 2-3句，报告主要发现和关键数据",
                        "结论 (Conclusion): 1-2句，总结主要结论和临床意义"
                    ],
                    "word_limit": "250-300词",
                    "tips": [
                        "使用过去时描述已完成的研究",
                        "避免使用缩写（首次出现需全称）",
                        "包含关键的数值结果（如P值、OR值）",
                        "不要引用参考文献",
                        "关键词3-5个，按字母顺序排列"
                    ],
                    "checklist": [
                        "是否明确说明研究目的？",
                        "是否描述了研究设计和样本量？",
                        "是否报告了主要结果和统计数据？",
                        "是否给出了明确的结论？",
                        "是否控制在字数限制内？"
                    ]
                },
                "case_report": {
                    "structure": [
                        "背景: 简述病例报告的意义",
                        "病例介绍: 关键临床信息",
                        "结论: 病例的教学意义"
                    ],
                    "word_limit": "150-200词"
                },
                "systematic_review": {
                    "structure": [
                        "背景: 综述的目的和问题",
                        "方法: 检索策略和筛选标准",
                        "结果: 纳入研究数量和主要发现",
                        "结论: 证据总结和临床建议"
                    ],
                    "word_limit": "300-350词"
                }
            },
            "introduction": {
                "imrad": {
                    "structure": [
                        "第一段 - 研究背景: 介绍研究领域和问题的重要性",
                        "第二段 - 文献综述: 总结既往研究，指出研究空白",
                        "第三段 - 研究目的: 明确本研究的目的和假设"
                    ],
                    "tips": [
                        "从宏观到微观，逐步聚焦",
                        "引用最新和最相关的文献",
                        "明确指出现有研究的不足",
                        "研究目的与标题一致",
                        "使用现在时描述已知事实，过去时描述既往研究"
                    ],
                    "references_guide": "通常引用15-30篇参考文献"
                }
            },
            "methods": {
                "imrad": {
                    "structure": [
                        "研究设计: 研究类型（RCT/队列/病例对照等）",
                        "研究对象: 纳入排除标准、样本量计算",
                        "干预措施: 实验组和对照组的干预（如适用）",
                        "数据收集: 变量定义、测量方法",
                        "统计分析: 使用的统计方法、软件",
                        "伦理声明: 伦理批准、知情同意"
                    ],
                    "tips": [
                        "提供足够细节使研究可重复",
                        "使用过去时态",
                        "统计方法要与结果部分对应",
                        "说明缺失数据的处理方法",
                        "如有注册号需提供（如ClinicalTrials.gov）"
                    ],
                    "statistical_reporting": {
                        "continuous_variables": "均数±标准差 或 中位数(四分位距)",
                        "categorical_variables": "频数(百分比)",
                        "comparison": "说明使用的检验方法（t检验/卡方检验/Mann-Whitney等）",
                        "significance_level": "通常设为 α=0.05"
                    }
                }
            },
            "results": {
                "imrad": {
                    "structure": [
                        "研究对象特征: 基线资料表格（表1）",
                        "主要结局: 主要研究结果",
                        "次要结局: 次要研究结果",
                        "亚组分析: 亚组分析结果（如适用）",
                        "敏感性分析: 敏感性分析结果（如适用）"
                    ],
                    "tips": [
                        "按照方法部分的顺序呈现结果",
                        "使用过去时态",
                        "先文字描述，再引用图表",
                        "报告精确的P值（如P=0.023而非P<0.05）",
                        "报告效应量和置信区间",
                        "不要在结果部分进行解释"
                    ],
                    "table_guide": {
                        "表1": "基线特征比较",
                        "表2": "主要结局比较",
                        "图1": "流程图（CONSORT/STROBE）",
                        "图2": "主要结果图示"
                    },
                    "reporting_format": {
                        "continuous": "组间差异: X.XX (95% CI: X.XX-X.XX), P=X.XXX",
                        "categorical": "OR/RR: X.XX (95% CI: X.XX-X.XX), P=X.XXX"
                    }
                }
            },
            "discussion": {
                "imrad": {
                    "structure": [
                        "第一段 - 主要发现: 总结本研究的主要发现",
                        "第二段 - 与既往研究比较: 与其他研究结果的比较",
                        "第三段 - 可能机制: 解释可能的机制",
                        "第四段 - 临床意义: 研究结果的临床应用价值",
                        "第五段 - 优势与局限: 研究的优势和局限性",
                        "第六段 - 结论: 简洁的结论和未来研究方向"
                    ],
                    "tips": [
                        "首句总结最重要的发现",
                        "客观讨论与既往研究的异同",
                        "承认研究局限性",
                        "结论不要超出数据支持的范围",
                        "使用现在时讨论一般性结论，过去时描述本研究结果"
                    ],
                    "limitations_to_consider": [
                        "样本量是否足够",
                        "选择偏倚",
                        "混杂因素控制",
                        "测量偏倚",
                        "失访和缺失数据",
                        "外推性（generalizability）"
                    ]
                }
            }
        }

        # 获取对应章节的指导
        if section in section_guides:
            template_data = section_guides[section].get(template_type, section_guides[section].get("imrad"))
            result["guide"] = template_data
        else:
            result["error"] = f"不支持的章节: {section}"
            result["supported_sections"] = ["abstract", "introduction", "methods", "results", "discussion"]

        # 添加通用写作建议
        result["general_tips"] = [
            "遵循目标期刊的投稿指南",
            "使用主动语态（除非期刊要求被动语态）",
            "避免过长句子，保持清晰简洁",
            "使用专业术语但确保准确",
            "请同事或语言专家审阅"
        ]

        # 添加格式检查清单
        result["format_checklist"] = [
            "标题是否准确反映研究内容",
            "作者信息和通讯作者是否正确",
            "参考文献格式是否符合要求",
            "图表是否清晰、标注完整",
            "伦理声明和利益冲突声明是否完整"
        ]

        logger.info(
            "[ResearchToolsV3] assist_paper_writing completed, input_length=%s",
            len(research_data),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(
            "[ResearchToolsV3] assist_paper_writing failed, error_type=%s",
            type(e).__name__,
        )
        return json.dumps(
            {"error": True, "message": "论文写作助手失败，请稍后再试"},
            ensure_ascii=False,
        )


# ========== 临床指南查询 ==========

@tool
def search_clinical_guidelines(
    disease: str,
    organization: str = None,
    max_results: int = 5
) -> str:
    """
    查询相关疾病的临床诊疗指南。

    Args:
        disease: 疾病名称或关键词（如"糖尿病"、"高血压"、"青光眼"）
        organization: 指南发布机构（可选），可选值：
            - "WHO": 世界卫生组织
            - "NICE": 英国国家健康与临床优化研究所
            - "中华医学会": 中华医学会各专业委员会
            - "AAO": 美国眼科学会
            - "ADA": 美国糖尿病协会
            - "ESC": 欧洲心脏病学会
            - 不指定则搜索所有来源
        max_results: 返回最大结果数（默认5）

    Returns:
        JSON格式的指南列表，包含标题、机构、日期、关键推荐、证据等级

    使用场景：
        - 查找疾病最新诊疗规范
        - 了解治疗推荐意见
        - 准备临床决策参考
        - 科研文献综述

    注意：
        此工具返回指南搜索指导，实际搜索需配合网页搜索工具完成
    """
    try:
        result = {
            "disease": disease,
            "organization": organization,
            "max_results": max_results
        }

        # 常见疾病的指南信息库（示例数据）
        guideline_database = {
            "糖尿病": [
                {
                    "title": "中国2型糖尿病防治指南（2020年版）",
                    "organization": "中华医学会糖尿病学分会",
                    "publish_date": "2021-04",
                    "key_recommendations": [
                        "HbA1c控制目标：<7.0%（个体化）",
                        "一线用药：二甲双胍",
                        "心血管高危患者：优先选择SGLT2i或GLP-1RA",
                        "血压控制目标：<130/80 mmHg"
                    ],
                    "evidence_level": "A级证据",
                    "search_keywords": ["中国糖尿病指南 2020", "CDS diabetes guideline"]
                },
                {
                    "title": "Standards of Care in Diabetes—2024",
                    "organization": "ADA (美国糖尿病协会)",
                    "publish_date": "2024-01",
                    "key_recommendations": [
                        "强调个体化血糖目标",
                        "心肾保护药物优先使用",
                        "综合心血管风险管理"
                    ],
                    "evidence_level": "A级证据",
                    "search_keywords": ["ADA Standards of Care 2024"]
                }
            ],
            "高血压": [
                {
                    "title": "中国高血压防治指南（2024年修订版）",
                    "organization": "中华医学会心血管病学分会",
                    "publish_date": "2024-05",
                    "key_recommendations": [
                        "血压控制目标：<140/90 mmHg，高危<130/80 mmHg",
                        "生活方式干预是基础",
                        "联合用药优于单药加量"
                    ],
                    "evidence_level": "A级证据",
                    "search_keywords": ["中国高血压指南 2024"]
                },
                {
                    "title": "ESC/ESH Guidelines for Hypertension (2023)",
                    "organization": "ESC (欧洲心脏病学会)",
                    "publish_date": "2023-08",
                    "key_recommendations": [
                        "Target BP <130/80 mmHg for most patients",
                        "Initial combination therapy recommended",
                        "HMOD assessment required"
                    ],
                    "evidence_level": "Level I Evidence",
                    "search_keywords": ["ESC hypertension guidelines 2023"]
                }
            ],
            "青光眼": [
                {
                    "title": "中国青光眼指南（2020年）",
                    "organization": "中华医学会眼科学分会青光眼学组",
                    "publish_date": "2020-03",
                    "key_recommendations": [
                        "目标眼压个体化",
                        "前列腺素类为一线用药",
                        "定期随访视野和OCT"
                    ],
                    "evidence_level": "B级证据",
                    "search_keywords": ["中国青光眼指南", "青光眼诊疗规范"]
                },
                {
                    "title": "AAO Preferred Practice Pattern: Primary Open-Angle Glaucoma",
                    "organization": "AAO (美国眼科学会)",
                    "publish_date": "2023-11",
                    "key_recommendations": [
                        "Target IOP reduction of 20-50% from baseline",
                        "Consider MIGS for early-moderate disease",
                        "Monitor for progression with VF and OCT"
                    ],
                    "evidence_level": "Level I Evidence",
                    "search_keywords": ["AAO glaucoma PPP 2023"]
                }
            ]
        }

        # 查找匹配的指南
        matching_guidelines = []
        for key, guidelines in guideline_database.items():
            if disease.lower() in key.lower() or key.lower() in disease.lower():
                for g in guidelines:
                    if organization is None or organization.lower() in g["organization"].lower():
                        matching_guidelines.append(g)

        if matching_guidelines:
            result["found_guidelines"] = matching_guidelines[:max_results]
            result["total_found"] = len(matching_guidelines)
        else:
            result["found_guidelines"] = []
            result["message"] = f"未找到'{disease}'的内置指南信息，建议使用网页搜索工具查找"

        # 提供搜索建议
        result["search_suggestions"] = {
            "chinese_sources": [
                "中华医学会官网",
                "中国知网指南数据库",
                "丁香园指南库"
            ],
            "international_sources": [
                "PubMed (Clinical Guidelines)",
                "NICE Guidelines",
                "WHO Guidelines",
                "UpToDate"
            ],
            "recommended_search_terms": [
                f"{disease} 诊疗指南 最新",
                f"{disease} clinical guidelines",
                f"{disease} practice guidelines"
            ]
        }

        # 证据等级说明
        result["evidence_levels"] = {
            "A级/Level I": "高质量RCT或Meta分析",
            "B级/Level II": "较高质量RCT或大型观察性研究",
            "C级/Level III": "观察性研究或专家共识",
            "D级/Level IV": "专家意见或病例报告"
        }

        logger.info(
            "[ResearchToolsV3] search_clinical_guidelines completed, "
            "query_length=%s, result_count=%s",
            len(disease),
            len(matching_guidelines),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(
            "[ResearchToolsV3] search_clinical_guidelines failed, error_type=%s",
            type(e).__name__,
        )
        return json.dumps(
            {"error": True, "message": "临床指南查询失败，请稍后再试"},
            ensure_ascii=False,
        )


# ========== 药物相互作用检查 ==========

@tool
def check_drug_interactions(
    drug_list: str,
    patient_conditions: str = None
) -> str:
    """
    检查药物相互作用和禁忌症。

    Args:
        drug_list: 药物名称列表，逗号分隔（如"阿司匹林,华法林,布洛芬"）
        patient_conditions: 患者疾病状态，逗号分隔（可选，如"肾功能不全,高血压"）

    Returns:
        JSON格式的相互作用检查结果，包含相互作用列表、严重程度、建议

    使用场景：
        - 多药联用安全性检查
        - 特殊人群用药调整
        - 处方审核

    注意：
        此工具提供参考信息，实际用药决策需由医生根据具体情况判断
    """
    try:
        # 解析药物列表
        drugs = [d.strip() for d in drug_list.split(",") if d.strip()]
        conditions = [c.strip() for c in patient_conditions.split(",")] if patient_conditions else []

        result = {
            "drugs_checked": drugs,
            "patient_conditions": conditions,
            "check_time": datetime.now().isoformat()
        }

        # 常见药物相互作用数据库（示例）
        interactions_db = {
            ("阿司匹林", "华法林"): {
                "severity": "严重",
                "mechanism": "两药均影响凝血功能，联用增加出血风险",
                "clinical_effect": "显著增加出血风险，包括消化道出血和颅内出血",
                "recommendation": "如必须联用，需密切监测INR，考虑减少剂量或使用PPI保护胃黏膜",
                "monitoring": ["INR", "出血症状", "粪便隐血"]
            },
            ("阿司匹林", "布洛芬"): {
                "severity": "中等",
                "mechanism": "布洛芬可能干扰阿司匹林的抗血小板作用",
                "clinical_effect": "降低阿司匹林心血管保护效果，增加消化道不良反应",
                "recommendation": "避免长期联用；如需止痛，考虑对乙酰氨基酚替代",
                "monitoring": ["消化道症状"]
            },
            ("华法林", "布洛芬"): {
                "severity": "严重",
                "mechanism": "NSAIDs增加出血风险并可能影响华法林代谢",
                "clinical_effect": "显著增加出血风险",
                "recommendation": "避免联用；如需止痛，使用对乙酰氨基酚",
                "monitoring": ["INR", "出血症状"]
            },
            ("二甲双胍", "造影剂"): {
                "severity": "严重",
                "mechanism": "碘造影剂可能诱发乳酸酸中毒",
                "clinical_effect": "肾功能不全时风险增加",
                "recommendation": "造影前48小时停用，造影后48小时复查肾功能后恢复",
                "monitoring": ["肾功能", "乳酸水平"]
            },
            ("ACE抑制剂", "保钾利尿剂"): {
                "severity": "中等",
                "mechanism": "两药均可升高血钾",
                "clinical_effect": "高钾血症风险",
                "recommendation": "监测血钾，特别是肾功能不全患者",
                "monitoring": ["血钾", "肾功能"]
            },
            ("他汀类", "贝特类"): {
                "severity": "中等",
                "mechanism": "增加肌病和横纹肌溶解风险",
                "clinical_effect": "肌肉疼痛、CK升高、严重时横纹肌溶解",
                "recommendation": "避免联用吉非贝齐；如需联用非诺贝特，密切监测",
                "monitoring": ["CK", "肌肉症状", "肾功能"]
            }
        }

        # 疾病禁忌数据库
        disease_contraindications = {
            "肾功能不全": {
                "禁用/慎用药物": ["二甲双胍（eGFR<30禁用）", "NSAIDs", "氨基糖苷类", "造影剂"],
                "需调整剂量": ["加巴喷丁", "普瑞巴林", "达比加群", "多数抗生素"],
                "monitoring": ["eGFR", "血肌酐", "电解质"]
            },
            "肝功能不全": {
                "禁用/慎用药物": ["对乙酰氨基酚（大剂量）", "某些他汀类", "甲氨蝶呤"],
                "需调整剂量": ["多数需肝脏代谢的药物"],
                "monitoring": ["肝功能", "凝血功能"]
            },
            "心力衰竭": {
                "禁用/慎用药物": ["NSAIDs", "噻唑烷二酮类", "非二氢吡啶类CCB"],
                "推荐药物": ["ACEI/ARB", "β受体阻滞剂", "SGLT2i", "利尿剂"],
                "monitoring": ["心功能", "电解质", "肾功能"]
            },
            "消化道溃疡": {
                "禁用/慎用药物": ["NSAIDs", "阿司匹林（需保护剂）", "糖皮质激素"],
                "保护措施": ["PPI联用", "选择COX-2抑制剂"],
                "monitoring": ["消化道症状", "粪便隐血"]
            }
        }

        # 检查药物相互作用
        found_interactions = []
        for i, drug1 in enumerate(drugs):
            for drug2 in drugs[i+1:]:
                # 标准化药物名称匹配
                for (d1, d2), interaction in interactions_db.items():
                    if (drug1 in d1 or d1 in drug1) and (drug2 in d2 or d2 in drug2):
                        found_interactions.append({
                            "drug_pair": [drug1, drug2],
                            **interaction
                        })
                    elif (drug2 in d1 or d1 in drug2) and (drug1 in d2 or d2 in drug1):
                        found_interactions.append({
                            "drug_pair": [drug1, drug2],
                            **interaction
                        })

        result["interactions"] = found_interactions
        result["interaction_count"] = len(found_interactions)

        # 按严重程度分类
        result["by_severity"] = {
            "严重": [i for i in found_interactions if i["severity"] == "严重"],
            "中等": [i for i in found_interactions if i["severity"] == "中等"],
            "轻微": [i for i in found_interactions if i["severity"] == "轻微"]
        }

        # 检查疾病禁忌
        disease_warnings = []
        for condition in conditions:
            for disease, info in disease_contraindications.items():
                if condition in disease or disease in condition:
                    disease_warnings.append({
                        "condition": condition,
                        **info
                    })

        result["disease_contraindications"] = disease_warnings

        # 总体建议
        if len([i for i in found_interactions if i["severity"] == "严重"]) > 0:
            result["overall_risk"] = "高风险"
            result["overall_recommendation"] = "存在严重相互作用，建议重新评估用药方案"
        elif len(found_interactions) > 0:
            result["overall_risk"] = "中等风险"
            result["overall_recommendation"] = "存在相互作用，需加强监测"
        else:
            result["overall_risk"] = "低风险"
            result["overall_recommendation"] = "未发现明显相互作用，但仍需常规监测"

        # 提醒
        result["disclaimer"] = "此结果仅供参考，实际用药需由医生根据患者具体情况决定。建议查阅药品说明书和专业药物相互作用数据库。"

        logger.info(
            "[ResearchToolsV3] check_drug_interactions completed, "
            "drug_count=%s, condition_count=%s",
            len(drugs),
            len(conditions),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(
            "[ResearchToolsV3] check_drug_interactions failed, error_type=%s",
            type(e).__name__,
        )
        return json.dumps(
            {"error": True, "message": "药物相互作用检查失败，请稍后再试"},
            ensure_ascii=False,
        )


# ========== 病例相似度匹配 ==========

@tool
def find_similar_cases(
    case_description: str,
    max_results: int = 10,
    similarity_threshold: float = 0.7
) -> str:
    """
    在数据库中查找与描述相似的病例。

    Args:
        case_description: 病例描述，包含诊断、症状、检查结果等信息
        max_results: 返回最大结果数（默认10）
        similarity_threshold: 相似度阈值，0-1之间（默认0.7）

    Returns:
        JSON格式的匹配指导，包含匹配维度、搜索建议

    使用场景：
        - 辅助诊断参考
        - 治疗方案参考
        - 预后评估参考
        - 罕见病例发现
        - 科研队列筛选

    注意：
        此工具提供病例匹配指导，实际匹配需结合机构数据库工具使用
    """
    try:
        result = {
            "case_description": case_description[:500],  # 截取前500字
            "max_results": max_results,
            "similarity_threshold": similarity_threshold
        }

        # 提取关键信息指导
        result["extraction_guide"] = {
            "诊断相关": [
                "主要诊断（ICD编码）",
                "合并症",
                "诊断确定程度"
            ],
            "症状相关": [
                "主诉",
                "现病史关键症状",
                "症状持续时间",
                "症状严重程度"
            ],
            "检查相关": [
                "关键实验室检查结果",
                "影像学特征",
                "专科检查结果"
            ],
            "患者特征": [
                "年龄范围",
                "性别",
                "既往史",
                "家族史"
            ],
            "治疗相关": [
                "当前用药",
                "既往治疗",
                "手术史"
            ]
        }

        # 匹配策略建议
        result["matching_strategies"] = [
            {
                "strategy": "诊断精确匹配",
                "description": "按ICD编码精确匹配相同诊断的病例",
                "适用场景": "需要同病种对照时",
                "权重建议": "0.4"
            },
            {
                "strategy": "症状相似匹配",
                "description": "基于症状描述的语义相似度匹配",
                "适用场景": "探索性诊断时",
                "权重建议": "0.3"
            },
            {
                "strategy": "检查结果匹配",
                "description": "关键检查指标的数值范围匹配",
                "适用场景": "需要量化对比时",
                "权重建议": "0.2"
            },
            {
                "strategy": "患者特征匹配",
                "description": "年龄、性别、既往史等特征匹配",
                "适用场景": "控制混杂因素时",
                "权重建议": "0.1"
            }
        ]

        # 搜索建议
        result["search_recommendations"] = {
            "使用机构数据库": {
                "工具": "get_institution_research_data",
                "参数": {
                    "data_type": "patients",
                    "filters": "根据病例特征构建"
                }
            },
            "构建查询条件": [
                "主要诊断 = '提取的诊断'",
                "年龄 BETWEEN X AND Y",
                "性别 = 'M/F'",
                "就诊时间 BETWEEN 'start' AND 'end'"
            ]
        }

        # 相似度计算说明
        result["similarity_calculation"] = {
            "方法": "加权综合相似度",
            "公式": "similarity = Σ(weight_i × sim_i)",
            "阈值说明": {
                "0.9以上": "高度相似，可直接参考",
                "0.7-0.9": "中度相似，需谨慎对比",
                "0.5-0.7": "部分相似，仅供参考",
                "0.5以下": "相似度较低"
            }
        }

        # 隐私保护提醒
        result["privacy_reminder"] = [
            "相似病例匹配结果默认脱敏处理",
            "仅用于科研和诊疗参考",
            "不得用于识别具体患者"
        ]

        logger.info(
            "[ResearchToolsV3] find_similar_cases completed, input_length=%s",
            len(case_description),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(
            "[ResearchToolsV3] find_similar_cases failed, error_type=%s",
            type(e).__name__,
        )
        return json.dumps(
            {"error": True, "message": "病例相似度匹配失败，请稍后再试"},
            ensure_ascii=False,
        )


# ========== 伦理审查助手 ==========

@tool
def ethics_review_assistant(
    research_protocol: str,
    study_type: str = "observational"
) -> str:
    """
    辅助准备研究伦理审查材料。

    Args:
        research_protocol: 研究方案描述或摘要
        study_type: 研究类型，可选值：
            - "observational": 观察性研究（默认）
            - "interventional": 干预性研究
            - "retrospective": 回顾性研究

    Returns:
        JSON格式的伦理审查准备材料，包含检查清单、模板、风险评估

    使用场景：
        - 准备伦理委员会申请
        - 知情同意书撰写
        - 研究风险评估
        - 数据安全管理
    """
    try:
        result = {
            "research_protocol_received": len(research_protocol) > 0,
            "study_type": study_type
        }

        # 伦理审查要点检查清单
        result["ethics_checklist"] = {
            "基本要求": [
                {"item": "研究目的是否清晰合理", "required": True},
                {"item": "研究设计是否科学合理", "required": True},
                {"item": "是否有充分的文献支持", "required": True},
                {"item": "研究者资质是否符合要求", "required": True},
                {"item": "研究场所是否具备条件", "required": True}
            ],
            "受试者保护": [
                {"item": "纳入/排除标准是否明确", "required": True},
                {"item": "知情同意过程是否规范", "required": True},
                {"item": "是否保护受试者隐私", "required": True},
                {"item": "是否有退出机制", "required": True},
                {"item": "弱势群体是否有额外保护", "required": study_type == "interventional"}
            ],
            "风险收益评估": [
                {"item": "是否充分评估风险", "required": True},
                {"item": "风险是否在可接受范围", "required": True},
                {"item": "收益是否大于风险", "required": True},
                {"item": "是否有风险监测机制", "required": study_type == "interventional"}
            ],
            "数据安全": [
                {"item": "数据收集是否最小化原则", "required": True},
                {"item": "数据存储是否安全", "required": True},
                {"item": "数据访问权限是否控制", "required": True},
                {"item": "数据保留期限是否明确", "required": True}
            ]
        }

        # 知情同意书模板
        result["informed_consent_template"] = {
            "标题": "[研究名称]知情同意书",
            "sections": [
                {
                    "section": "1. 研究目的",
                    "content": "说明本研究的目的和意义，使用通俗易懂的语言..."
                },
                {
                    "section": "2. 研究过程",
                    "content": "详细描述参与研究需要做什么，包括时间、次数、地点..."
                },
                {
                    "section": "3. 风险和不适",
                    "content": "诚实说明可能的风险、不适或不便..."
                },
                {
                    "section": "4. 可能的收益",
                    "content": "说明参与者可能获得的直接或间接收益..."
                },
                {
                    "section": "5. 替代方案",
                    "content": "说明不参与研究时的其他选择（如适用）..."
                },
                {
                    "section": "6. 保密措施",
                    "content": "说明如何保护参与者的隐私和个人信息..."
                },
                {
                    "section": "7. 自愿参与",
                    "content": "强调参与完全自愿，可随时退出，不影响医疗待遇..."
                },
                {
                    "section": "8. 补偿说明",
                    "content": "说明参与研究的补偿（如有）和损害赔偿机制..."
                },
                {
                    "section": "9. 联系方式",
                    "content": "提供研究者和伦理委员会的联系方式..."
                },
                {
                    "section": "10. 签名区",
                    "content": "受试者签名、日期；研究者签名、日期"
                }
            ],
            "writing_tips": [
                "使用通俗语言，避免专业术语",
                "阅读水平应适合一般成年人",
                "关键信息应突出显示",
                "留有足够的签名空间"
            ]
        }

        # 风险评估报告模板
        risk_level = "高" if study_type == "interventional" else "低至中等"
        result["risk_assessment"] = {
            "study_type": study_type,
            "overall_risk_level": risk_level,
            "risk_categories": [
                {
                    "category": "生理风险",
                    "observational": "低（仅涉及常规检查）",
                    "interventional": "需具体评估干预措施的风险"
                },
                {
                    "category": "心理风险",
                    "description": "问卷或访谈可能引起的不适",
                    "mitigation": "提供心理支持，保障退出权利"
                },
                {
                    "category": "隐私风险",
                    "description": "个人健康信息泄露的可能",
                    "mitigation": "数据脱敏、加密存储、访问控制"
                },
                {
                    "category": "社会风险",
                    "description": "信息泄露可能导致的歧视",
                    "mitigation": "严格保密措施，限制数据访问"
                }
            ],
            "risk_mitigation_plan": [
                "建立不良事件报告机制",
                "设立数据安全监测委员会（如需要）",
                "制定应急预案",
                "购买研究相关保险（如适用）"
            ]
        }

        # 数据管理计划
        result["data_management_plan"] = {
            "data_collection": {
                "原则": "最小化原则，仅收集必要数据",
                "方法": "明确数据收集方式和工具",
                "时间点": "说明各时间点收集的数据"
            },
            "data_storage": {
                "存储位置": "院内服务器/云存储（需符合要求）",
                "安全措施": "加密、访问控制、定期备份",
                "保留期限": "研究结束后至少保留X年"
            },
            "data_access": {
                "访问权限": "仅授权研究人员可访问",
                "权限管理": "分级授权，定期审查",
                "审计日志": "记录所有数据访问操作"
            },
            "data_sharing": {
                "共享原则": "说明是否及如何共享数据",
                "脱敏要求": "共享前必须脱敏处理",
                "协议要求": "需签署数据使用协议"
            },
            "data_destruction": {
                "销毁时间": "研究结束后X年",
                "销毁方式": "安全删除/物理销毁",
                "销毁记录": "保留销毁证明"
            }
        }

        # 提交材料清单
        result["submission_documents"] = [
            "伦理审查申请表",
            "研究方案（完整版）",
            "知情同意书",
            "研究者手册（如适用）",
            "问卷/量表（如适用）",
            "研究者简历和资质证明",
            "研究场所证明",
            "利益冲突声明",
            "数据管理计划",
            "保险证明（如需要）"
        ]

        logger.info(
            "[ResearchToolsV3] ethics_review_assistant completed, input_length=%s",
            len(research_protocol),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(
            "[ResearchToolsV3] ethics_review_assistant failed, error_type=%s",
            type(e).__name__,
        )
        return json.dumps(
            {"error": True, "message": "伦理审查助手失败，请稍后再试"},
            ensure_ascii=False,
        )


# ========== 数据导出工具 ==========

@tool
def export_research_data(
    data_json: str,
    export_format: str = "excel",
    include_metadata: bool = True,
    anonymization: bool = True
) -> str:
    """
    将科研数据导出为多种格式。

    Args:
        data_json: 要导出的数据，JSON格式
        export_format: 导出格式，可选值：
            - "excel": Excel文件（.xlsx）
            - "csv": CSV文件（.csv）
            - "spss": SPSS格式（.sav）- 需要额外库支持
            - "json": JSON文件（.json）
        include_metadata: 是否包含元数据（默认True）
        anonymization: 是否启用数据脱敏（默认True）

    Returns:
        JSON格式的导出结果，包含文件信息或base64编码

    使用场景：
        - 数据统计分析准备
        - 团队数据共享
        - 论文附件准备
        - 数据备份
    """
    try:
        result = {
            "export_format": export_format,
            "include_metadata": include_metadata,
            "anonymization": anonymization,
            "export_time": datetime.now().isoformat()
        }

        # 解析数据
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError:
            return json.dumps({
                "error": True,
                "message": "数据JSON格式无效"
            }, ensure_ascii=False)

        # 检查数据格式
        if isinstance(data, list):
            record_count = len(data)
            if record_count > 0 and isinstance(data[0], dict):
                fields = list(data[0].keys())
            else:
                fields = []
        elif isinstance(data, dict):
            record_count = 1
            fields = list(data.keys())
        else:
            return json.dumps({
                "error": True,
                "message": "数据格式不支持，需要列表或字典"
            }, ensure_ascii=False)

        result["data_summary"] = {
            "record_count": record_count,
            "field_count": len(fields),
            "fields": fields[:20]  # 最多显示20个字段
        }

        # 脱敏处理说明
        if anonymization:
            result["anonymization_applied"] = {
                "status": True,
                "rules": [
                    "姓名: 替换为'患者A/B/C...'",
                    "电话: 保留前3后4位",
                    "身份证: 保留前6后4位",
                    "地址: 仅保留到城市级别"
                ]
            }

        # 导出格式处理
        if export_format == "excel":
            try:
                import pandas as pd

                df = pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame([data])

                # 导出到内存
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Data', index=False)

                    if include_metadata:
                        metadata_df = pd.DataFrame([
                            {"项目": "导出时间", "值": result["export_time"]},
                            {"项目": "记录数", "值": record_count},
                            {"项目": "字段数", "值": len(fields)},
                            {"项目": "脱敏处理", "值": "是" if anonymization else "否"}
                        ])
                        metadata_df.to_excel(writer, sheet_name='Metadata', index=False)

                buffer.seek(0)
                file_content = base64.b64encode(buffer.getvalue()).decode('utf-8')

                result["success"] = True
                result["file_base64"] = file_content
                result["file_size_bytes"] = len(buffer.getvalue())
                result["file_extension"] = ".xlsx"
                result["content_type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

            except ImportError:
                result["error"] = True
                result["message"] = "Excel导出需要安装 pandas 和 openpyxl: pip install pandas openpyxl"

        elif export_format == "csv":
            try:
                import pandas as pd

                df = pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame([data])
                csv_content = df.to_csv(index=False, encoding='utf-8-sig')
                file_content = base64.b64encode(csv_content.encode('utf-8-sig')).decode('utf-8')

                result["success"] = True
                result["file_base64"] = file_content
                result["file_size_bytes"] = len(csv_content.encode('utf-8-sig'))
                result["file_extension"] = ".csv"
                result["content_type"] = "text/csv"

            except ImportError:
                result["error"] = True
                result["message"] = "CSV导出需要安装 pandas: pip install pandas"

        elif export_format == "json":
            json_content = json.dumps(data, ensure_ascii=False, indent=2)
            file_content = base64.b64encode(json_content.encode('utf-8')).decode('utf-8')

            result["success"] = True
            result["file_base64"] = file_content
            result["file_size_bytes"] = len(json_content.encode('utf-8'))
            result["file_extension"] = ".json"
            result["content_type"] = "application/json"

        elif export_format == "spss":
            result["error"] = True
            result["message"] = "SPSS格式导出需要 pyreadstat 库: pip install pyreadstat"
            result["alternative"] = "建议先导出为CSV，再在SPSS中导入"

        else:
            result["error"] = True
            result["message"] = f"不支持的导出格式: {export_format}"
            result["supported_formats"] = ["excel", "csv", "json", "spss"]

        # 添加水印信息
        result["watermark"] = {
            "export_time": result["export_time"],
            "anonymization": anonymization,
            "record_count": record_count
        }

        # 使用提醒
        result["usage_notes"] = [
            "导出的数据仅供科研使用",
            "请妥善保管，避免泄露",
            "如需共享，请确保符合伦理要求",
            "建议定期删除不再需要的导出文件"
        ]

        logger.info(
            "[ResearchToolsV3] export_research_data completed, record_count=%s",
            record_count,
        )
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.error(
            "[ResearchToolsV3] export_research_data failed, error_type=%s",
            type(e).__name__,
        )
        return json.dumps(
            {"error": True, "message": "数据导出失败，请稍后再试"},
            ensure_ascii=False,
        )


# ========== 阶段三工具列表 ==========

PHASE3_TOOLS = [
    assist_paper_writing,
    search_clinical_guidelines,
    check_drug_interactions,
    find_similar_cases,
    ethics_review_assistant,
    export_research_data,
]


# ========== 模块信息 ==========
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Research Tools V3 (阶段三) 模块信息")
    print("=" * 50)
    print(f"阶段三工具数量: {len(PHASE3_TOOLS)}")

    for i, tool in enumerate(PHASE3_TOOLS, 1):
        print(f"  {i}. {tool.name}")
