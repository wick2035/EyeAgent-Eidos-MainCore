"""
ResearchAgent - 医问通科研Agent
专为医生用户设计的科研支持Agent

Created: 2025-12-03
"""
from typing import Dict, Any, Optional, List, TYPE_CHECKING
import logging
import uuid as uuid_lib

from agents.base.base_agent import BaseAgent
from domain.enums.agent_type import AgentType
from domain.enums.conversation_stage import ConversationStage
from agents.tools.research_tools import RESEARCH_AGENT_TOOLS

if TYPE_CHECKING:
    from application.services.chat_persistence_service import ChatPersistenceService

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """
    医问通科研Agent

    职责：
    - 机构数据库科研分析（需权限开启）
    - 医学文献搜索（支持多类型并行搜索）
    - 统计分析辅助（阶段二实现）
    - 研究方案设计（阶段二实现）
    - 继承患者管理功能（排除报告生成）

    特点：
    - 仅医生用户可访问
    - 支持机构数据库开关控制
    - 支持多类型网页搜索（general/pubmed/scholar）
    """

    def __init__(
        self,
        doctor_id: str,
        session_id: str = None,
        patient_id: Optional[str] = None,
        enable_institution_data: bool = False,
        enable_web_search: bool = False,
        web_search_types: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
        persistence_service: Optional["ChatPersistenceService"] = None
    ):
        """
        初始化ResearchAgent

        Args:
            doctor_id: 医生UUID（必需）
            session_id: 会话ID
            patient_id: 患者UUID（可选，查看特定患者数据时需要）
            enable_institution_data: 机构数据库访问开关
            enable_web_search: 网页搜索开关
            web_search_types: 搜索类型列表 ["general", "pubmed", "scholar"]
            conversation_id: 数据库会话ID
            persistence_service: 持久化服务
        """
        # 生成session_id
        session_id = session_id or f"research_{uuid_lib.uuid4().hex[:8]}"

        # ResearchAgent使用doctor_id作为主要ID
        # 为了与BaseAgent兼容，将doctor_id传给patient_id参数
        super().__init__(
            patient_id=doctor_id,  # BaseAgent需要patient_id，这里用doctor_id
            session_id=session_id,
            agent_type=AgentType.RESEARCH,
            role="doctor",  # ResearchAgent固定为doctor角色
            tools=RESEARCH_AGENT_TOOLS,
            conversation_id=conversation_id,
            persistence_service=persistence_service
        )

        # ResearchAgent特有属性
        self.doctor_id = doctor_id
        self.target_patient_id = patient_id  # 目标患者ID（可选）
        self.enable_institution_data = enable_institution_data
        self.enable_web_search = enable_web_search
        self.web_search_types = web_search_types or []

        # 状态追踪
        self.current_research_task = None
        self.collected_data = {}
        self.search_history = []  # 搜索历史

        logger.info(
            f"[ResearchAgent] 初始化完成: doctor={doctor_id}, "
            f"patient={patient_id}, institution_data={enable_institution_data}, "
            f"web_search={enable_web_search}, search_types={web_search_types}"
        )

    def _create_system_prompt(self) -> str:
        """创建系统提示词"""
        return """你是医问通科研助手，专门为医生用户提供科研支持。

## 你的身份
- 专业的医学研究助手
- 严格遵守数据隐私和伦理规范
- 提供准确、可靠的科研支持

## 核心能力

### 阶段一：基础数据与搜索

#### 1. 机构数据库科研分析
- 可以访问机构数据库进行科研分析（需权限开启）
- 所有数据查询默认启用脱敏保护
- 支持多维度数据查询和统计分析
- 使用工具: get_institution_research_data

#### 2. 医学文献搜索
- 搜索最新医学文献和研究进展
- 支持三种搜索类型:
  * general: 通用网页搜索
  * pubmed: PubMed医学文献数据库
  * scholar: Google Scholar学术搜索
- 可同时进行多类型搜索并合并结果
- 使用工具: web_search_medical

### 阶段二：统计与分析

#### 3. 统计分析
- 描述性统计（均值、标准差、中位数、四分位数）
- 相关性分析（Pearson/Spearman）
- t检验（独立样本/配对样本）
- 卡方检验
- 线性回归分析
- 方差分析（ANOVA）
- 生存分析（基础）
- 使用工具: statistical_analysis

#### 4. 文献处理
- 生成文献摘要
- 提取关键发现
- 医学文献翻译
- 提取研究方法和结论
- 使用工具: summarize_medical_literature

#### 5. 数据可视化
- 柱状图、折线图、散点图
- 饼图、箱线图、直方图
- 热力图
- 图片自动上传到Minio存储
- 使用工具: generate_research_visualization

#### 6. 研究方案设计
- 推荐研究类型（RCT、队列、病例对照等）
- 样本量估算建议
- 入排标准设计
- 统计分析计划
- 伦理考虑提醒
- 使用工具: design_research_protocol

### 阶段三：高级科研功能

#### 7. 论文写作助手
- 提供各章节写作模板和指导
- 支持章节: abstract, introduction, methods, results, discussion
- 支持模板类型: imrad, case_report, systematic_review
- 使用工具: assist_paper_writing

#### 8. 临床指南查询
- 查询WHO、NICE、中华医学会等权威指南
- 获取推荐意见、证据等级
- 支持疾病/治疗关键词搜索
- 使用工具: search_clinical_guidelines

#### 9. 药物相互作用检查
- 检查药物-药物相互作用
- 检查药物-疾病禁忌
- 提供严重程度和处理建议
- 使用工具: check_drug_interactions

#### 10. 病例相似度匹配
- 基于诊断、症状、检查结果匹配相似病例
- 返回相似病例列表和匹配依据
- 支持机构数据库匹配（需权限）
- 使用工具: find_similar_cases

#### 11. 伦理审查助手
- 生成伦理审查清单
- 提供知情同意书模板
- 风险评估报告
- 数据管理计划
- 使用工具: ethics_review_assistant

#### 12. 科研数据导出
- 支持格式: excel, csv, spss, json
- 数据脱敏和水印标记
- 导出记录追踪
- 使用工具: export_research_data

### 患者管理辅助
- 查询患者处方和病历信息
- 管理预约和提醒
- 查看扫描检查数据

## 工具使用规则

### 网页搜索 (web_search_medical)
- 仅在 enable_web_search=True 时可用
- search_types 参数用逗号分隔多个类型，如 "general,pubmed"
- 根据搜索结果为医生总结关键发现
- 提供文献的标题、链接和关键内容摘要

### 机构数据库 (get_institution_research_data)
- 仅在 enable_institution_data=True 时可用
- 支持数据类型: patients, appointments, prescriptions, scans, all
- 数据已经过脱敏处理

### 统计分析 (statistical_analysis)
- 数据格式: JSON数组或对象
- 分析类型: descriptive, correlation, ttest, chi_square, regression, anova, survival
- 返回统计量、p值、置信区间等

### 数据可视化 (generate_research_visualization)
- 数据格式: JSON，包含labels/values或x/y
- 图表类型: bar, line, scatter, pie, boxplot, histogram, heatmap
- 返回base64编码图片和Minio URL（如可用）

### 文献处理 (summarize_medical_literature)
- 任务类型: summarize, extract_key_findings, translate, extract_methods, extract_conclusions
- 返回处理指导，由你根据指导完成文献分析

### 研究方案设计 (design_research_protocol)
- 输入研究问题，获取完整研究方案模板
- 包含入排标准、样本量估算、统计分析计划

### 论文写作助手 (assist_paper_writing)
- section: abstract/introduction/methods/results/discussion
- template_type: imrad/case_report/systematic_review
- 返回写作指导和结构模板

### 临床指南查询 (search_clinical_guidelines)
- 输入疾病名称或治疗关键词
- 返回权威指南推荐意见和证据等级

### 药物相互作用检查 (check_drug_interactions)
- 输入药物列表（逗号分隔）和疾病列表（可选）
- 返回相互作用警告和处理建议

### 病例相似度匹配 (find_similar_cases)
- 输入诊断、症状、检查结果
- 返回匹配策略和相似病例（如有权限）

### 伦理审查助手 (ethics_review_assistant)
- 输入研究标题和类型
- document_type: checklist/consent_form/risk_assessment/data_management
- 返回相应伦理文档模板

### 数据导出 (export_research_data)
- 输入数据和目标格式
- 返回base64编码文件和下载链接

### 患者相关工具
- 查询处方: get_patient_prescription
- 处方摘要: get_patient_prescription_limit
- 处方详情: get_patient_prescription_detail
- 扫描数据: get_patient_scan_data
- 预约医生: reserve_doctor (需配合 get_doctor_free_time)
- 提醒管理: get_patient_reminder 等

## 重要原则

### 数据安全
1. **数据脱敏**: 所有患者数据默认脱敏
2. **权限控制**: 仅在有权限时访问机构数据库和网页搜索
3. **审计追踪**: 所有数据访问都会被记录

### 科研伦理
1. **知情同意**: 提醒医生注意研究伦理要求
2. **结果解释**: 统计结果需准确解释，避免误导
3. **引用规范**: 引用文献时标注来源

## 对话风格
- 专业、严谨、客观
- 使用医学术语，但解释清晰
- 提供具体建议和操作步骤
- 主动提醒注意事项和权限限制

## 禁止事项
- 生成或修改医疗报告（这是ReportAgent的职责）
- 在无权限时访问机构数据库或进行网页搜索
- 提供未脱敏的患者数据
- 违反数据隐私和伦理规范的操作"""

    def _get_stage_prompt(self) -> str:
        """获取当前阶段提示"""
        stage = self.conversation.stage

        stage_prompts = {
            ConversationStage.GREETING: "初次接待，了解医生的科研需求",
            ConversationStage.RESEARCH_INIT: "正在了解研究目标和数据需求",
            ConversationStage.DATA_QUERY: "正在进行机构数据查询和分析",
            ConversationStage.WEB_SEARCH: "正在搜索相关医学文献",
            ConversationStage.STATISTICAL_ANALYSIS: "正在进行统计分析",
            ConversationStage.LITERATURE_REVIEW: "正在进行文献综述",
            ConversationStage.RESEARCH_DESIGN: "正在辅助研究方案设计",
            ConversationStage.PAPER_WRITING: "正在辅助论文写作",
            ConversationStage.COMPLETED: "科研任务完成"
        }

        return stage_prompts.get(stage, "科研助手待命中")

    def _handle_stage_transition(self, user_input: str, ai_response: str):
        """处理阶段转换逻辑"""
        stage = self.conversation.stage
        user_lower = user_input.lower()

        # 关键词检测
        data_keywords = ["数据", "患者", "统计", "分析", "查询", "机构"]
        search_keywords = ["文献", "搜索", "查找", "论文", "研究", "pubmed", "scholar"]
        stats_keywords = ["统计", "回归", "相关", "分析", "描述性"]
        design_keywords = ["方案", "设计", "样本量", "研究设计"]
        writing_keywords = ["论文", "写作", "摘要", "引言", "讨论"]

        # 阶段转换
        if stage == ConversationStage.GREETING:
            # 从问候进入研究初始化
            self.conversation.stage = ConversationStage.RESEARCH_INIT

        elif stage == ConversationStage.RESEARCH_INIT:
            # 根据用户意图转换阶段
            if any(kw in user_lower for kw in data_keywords):
                if self.enable_institution_data:
                    self.conversation.stage = ConversationStage.DATA_QUERY
                else:
                    # 即使没权限也进入该阶段，工具会提示权限问题
                    self.conversation.stage = ConversationStage.DATA_QUERY
            elif any(kw in user_lower for kw in search_keywords):
                self.conversation.stage = ConversationStage.WEB_SEARCH
            elif any(kw in user_lower for kw in stats_keywords):
                self.conversation.stage = ConversationStage.STATISTICAL_ANALYSIS
            elif any(kw in user_lower for kw in design_keywords):
                self.conversation.stage = ConversationStage.RESEARCH_DESIGN
            elif any(kw in user_lower for kw in writing_keywords):
                self.conversation.stage = ConversationStage.PAPER_WRITING

        elif stage == ConversationStage.DATA_QUERY:
            # 数据查询中，检测其他意图
            if any(kw in user_lower for kw in search_keywords):
                self.conversation.stage = ConversationStage.WEB_SEARCH
            elif any(kw in user_lower for kw in stats_keywords):
                self.conversation.stage = ConversationStage.STATISTICAL_ANALYSIS
            elif any(kw in user_lower for kw in ["谢谢", "完成", "够了", "结束"]):
                self.conversation.stage = ConversationStage.COMPLETED

        elif stage == ConversationStage.WEB_SEARCH:
            # 文献搜索中
            if any(kw in user_lower for kw in data_keywords):
                self.conversation.stage = ConversationStage.DATA_QUERY
            elif any(kw in user_lower for kw in stats_keywords):
                self.conversation.stage = ConversationStage.STATISTICAL_ANALYSIS
            elif any(kw in user_lower for kw in ["谢谢", "完成", "够了", "结束"]):
                self.conversation.stage = ConversationStage.COMPLETED

        elif stage == ConversationStage.STATISTICAL_ANALYSIS:
            if any(kw in user_lower for kw in ["谢谢", "完成", "够了", "结束"]):
                self.conversation.stage = ConversationStage.COMPLETED

        elif stage == ConversationStage.RESEARCH_DESIGN:
            if any(kw in user_lower for kw in ["谢谢", "完成", "够了", "结束"]):
                self.conversation.stage = ConversationStage.COMPLETED

        elif stage == ConversationStage.PAPER_WRITING:
            if any(kw in user_lower for kw in ["谢谢", "完成", "够了", "结束"]):
                self.conversation.stage = ConversationStage.COMPLETED

    def _extract_info_from_input(self, user_input: str) -> Dict[str, Any]:
        """从用户输入中提取信息"""
        extracted = {}

        # 检测数据类型需求
        data_keywords = {
            "patients": ["患者", "病人", "病历"],
            "appointments": ["预约", "就诊", "门诊"],
            "prescriptions": ["处方", "用药", "药物", "药品"],
            "scans": ["扫描", "检查", "影像", "CT", "MRI"]
        }

        for data_type, keywords in data_keywords.items():
            if any(kw in user_input for kw in keywords):
                extracted["data_type"] = data_type
                break

        # 检测搜索类型需求
        if "pubmed" in user_input.lower():
            extracted["search_type"] = "pubmed"
        elif "scholar" in user_input.lower():
            extracted["search_type"] = "scholar"
        elif any(kw in user_input for kw in ["文献", "论文", "研究"]):
            extracted["search_intent"] = True

        # 检测统计分析类型
        stats_types = {
            "descriptive": ["描述性", "均值", "标准差", "中位数"],
            "correlation": ["相关", "相关性", "pearson", "spearman"],
            "regression": ["回归", "线性回归", "逻辑回归"],
            "survival": ["生存", "kaplan", "cox", "生存率"]
        }

        for analysis_type, keywords in stats_types.items():
            if any(kw.lower() in user_input.lower() for kw in keywords):
                extracted["analysis_type"] = analysis_type
                break

        # 检测日期范围
        import re
        date_pattern = r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})'
        dates = re.findall(date_pattern, user_input)
        if len(dates) >= 2:
            extracted["date_range"] = {"start": dates[0], "end": dates[1]}
        elif len(dates) == 1:
            extracted["date"] = dates[0]

        return extracted

    def _build_additional_context(self, extracted_info: Dict[str, Any]) -> str:
        """构建额外上下文"""
        context_parts = []

        # 医生信息
        context_parts.append("【医生信息】")
        context_parts.append(f"医生ID: {self.doctor_id}")

        # 权限状态
        context_parts.append("")
        context_parts.append("【权限状态 - 请根据权限决定是否调用相关工具】")
        context_parts.append(f"机构数据库访问: {'已开启 - 可使用 get_institution_research_data' if self.enable_institution_data else '未开启 - 不可查询机构数据'}")
        context_parts.append(f"网页搜索: {'已开启 - 可使用 web_search_medical' if self.enable_web_search else '未开启 - 不可进行网页搜索'}")
        if self.enable_web_search and self.web_search_types:
            context_parts.append(f"搜索类型: {', '.join(self.web_search_types)}")

        # 目标患者（如果有）
        if self.target_patient_id:
            context_parts.append("")
            context_parts.append("【目标患者】")
            context_parts.append(f"患者ID: {self.target_patient_id}")
            context_parts.append("可使用患者相关工具查询此患者的数据")

        # 搜索历史
        if self.search_history:
            context_parts.append("")
            context_parts.append("【本次会话搜索历史】")
            for i, search in enumerate(self.search_history[-5:], 1):  # 最近5次
                context_parts.append(f"{i}. {search}")

        # 提取的信息
        if extracted_info:
            context_parts.append("")
            context_parts.append(f"【当前轮次提取】{extracted_info}")

        context_parts.append("")
        return "\n".join(context_parts)

    def update_permissions(
        self,
        enable_institution_data: Optional[bool] = None,
        enable_web_search: Optional[bool] = None,
        web_search_types: Optional[List[str]] = None
    ):
        """
        更新权限设置

        Args:
            enable_institution_data: 机构数据库访问开关
            enable_web_search: 网页搜索开关
            web_search_types: 搜索类型列表
        """
        if enable_institution_data is not None:
            self.enable_institution_data = enable_institution_data
        if enable_web_search is not None:
            self.enable_web_search = enable_web_search
        if web_search_types is not None:
            self.web_search_types = web_search_types

        logger.info(
            f"[ResearchAgent] 权限更新: institution_data={self.enable_institution_data}, "
            f"web_search={self.enable_web_search}, types={self.web_search_types}"
        )

    def add_search_history(self, query: str, search_types: List[str]):
        """记录搜索历史"""
        self.search_history.append(f"'{query}' ({','.join(search_types)})")
