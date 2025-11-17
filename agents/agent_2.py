"""
2号智能体 - 病例报告生成和历史分析
"""
import json
from enum import Enum
from typing import Dict, List, Any, Optional
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from utils.llm_config import get_llm
from utils.report_generator import ReportGenerator
from database.report_service import ReportService
from database.user_history_service_v2 import UserHistoryServiceV2


class ReportStage(Enum):
    """对话阶段"""
    GREETING = "greeting"  # 问候阶段
    SELECT_ACTION = "select_action"  # 选择操作
    GENERATE_REPORT = "generate_report"  # 生成报告
    ANALYZE_HISTORY = "analyze_history"  # 分析历史
    ANSWER_QUESTION = "answer_question"  # 回答问题
    COMPARE_RECORDS = "compare_records"  # 对比记录
    COMPLETED = "completed"  # 完成


class ReportAgent:
    """2号病例报告智能体"""
    
    def __init__(self, patient_id: int = None, phone_number: str = None, role: str = "patient"):
        """
        初始化报告智能体
        
        Args:
            patient_id: 用户ID（Patient_ID）
            phone_number: 手机号（推荐使用）
            role: 用户角色（patient/doctor）
        """
        self.llm = get_llm()
        self.stage = ReportStage.GREETING
        self.conversation_history = []
        
        # 用户角色
        self.role = role  # patient 或 doctor
        
        # 用户信息
        self.patient_id = patient_id
        self.phone_number = phone_number
        
        # 服务实例
        self.report_service = ReportService()
        self.history_service = UserHistoryServiceV2()
        self.report_generator = ReportGenerator()
        
        # 用户历史信息
        self.user_reports = []
        self.user_info = None
        self.load_user_data()
        
        # 当前操作相关
        self.selected_report_id = None
        self.analysis_type = None
        
        # 初始化对话链
        self.conversation_chain = self._create_conversation_chain()
    
    def load_user_data(self):
        """加载用户数据"""
        try:
            # 优先使用手机号
            if self.phone_number:
                # 获取用户信息
                self.user_info = self.history_service.get_user_by_phone(self.phone_number)
                if self.user_info:
                    self.patient_id = self.user_info['Patient_ID']
                    # 获取报告列表
                    self.user_reports = self.report_service.get_all_reports_by_phone(self.phone_number)
            elif self.patient_id:
                # 使用用户ID
                self.user_info = self.history_service.get_user_by_id(self.patient_id)
                if self.user_info:
                    self.user_reports = self.report_service.get_all_reports_by_patient(self.patient_id)
            
            print(f"[ReportAgent] 加载用户数据完成: patient_id={self.patient_id}, 报告数={len(self.user_reports)}")
            
        except Exception as e:
            print(f"[ReportAgent] 加载用户数据失败: {e}")
    
    def _create_conversation_chain(self):
        """创建对话链"""
        template = """你是小Report，一位专业的病例报告助手，负责生成病例报告和分析用户的历史就诊记录。

当前对话阶段：{stage}
当前用户角色：{role}

用户信息：
{user_info}

【权限说明】
{permission_note}

你的能力：
1. 【医生专用】生成病例报告PDF - 根据病例记录生成专业的病例报告文档
2. 分析病情趋势 - 分析用户历史病例，总结病情发展趋势
3. 对比就诊记录 - 对比多次就诊记录，发现变化和异常
4. 回答历史问题 - 回答用户关于历史病例的各种问题

【当前用户的病例报告】
{user_reports}

【对话指南】
- 语气专业、友好、耐心
- 首次对话时，简要介绍你的功能（根据权限介绍不同功能）
- 如果用户有历史报告，主动列出可以操作的报告
- 生成报告时，确认用户要生成哪一份报告（仅医生可用）
- 分析历史时，要全面、客观、易懂
- 发现异常情况时，要提醒用户注意

【重要提示】
- 当用户请求生成报告时，需要明确是哪一份病例（可以通过日期、病例ID等识别）
- 如果是患者角色尝试生成报告，礼貌地解释权限限制
- 分析病情趋势时，要按时间顺序分析，指出病情的变化
- 对比记录时，要指出主要差异和可能的原因
- 回答问题时，要基于实际的病例数据，不要臆测

对话历史：
{history}

用户：{input}
助手："""
        
        prompt = PromptTemplate(
            input_variables=["stage", "role", "permission_note", "user_info", "user_reports", "history", "input"],
            template=template
        )
        
        return LLMChain(llm=self.llm, prompt=prompt)
    
    def chat(self, user_input: str) -> tuple[str, bool]:
        """
        处理用户输入
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            (回复文本, 是否完成)
        """
        # 添加到对话历史
        self.conversation_history.append(f"用户: {user_input}")
        
        # 检测用户意图
        self._detect_intent(user_input)
        
        # 处理特殊命令
        special_response = self._handle_special_commands(user_input)
        if special_response:
            self.conversation_history.append(f"助手: {special_response}")
            return special_response, (self.stage == ReportStage.COMPLETED)
        
        # 准备对话上下文
        context = self._prepare_context()
        
        # 调用LLM
        try:
            response = self.conversation_chain.predict(
                stage=self.stage.value,
                role=context['role'],
                permission_note=context['permission_note'],
                user_info=context['user_info'],
                user_reports=context['user_reports'],
                history="\n".join(self.conversation_history[-10:]),
                input=user_input
            )
            
            self.conversation_history.append(f"助手: {response}")
            
            # 更新对话阶段
            self._update_stage(user_input, response)
            
            return response.strip(), (self.stage == ReportStage.COMPLETED)
            
        except Exception as e:
            error_msg = f"抱歉，处理您的请求时出现错误：{str(e)}"
            print(f"[ReportAgent错误] {e}")
            import traceback
            traceback.print_exc()
            return error_msg, False
    
    def _detect_intent(self, user_input: str):
        """检测用户意图"""
        user_input_lower = user_input.lower()
        
        # 生成报告相关关键词
        generate_keywords = ['生成报告', '打印报告', '导出报告', '生成病例', 'generate', 'report']
        action_keywords = ['生成', '打印', '导出', '制作', '生成下', '生成一', '生成他']
        if (
            any(keyword in user_input_lower for keyword in generate_keywords)
            or ('报告' in user_input_lower and any(action in user_input_lower for action in action_keywords))
        ):
            if self.stage == ReportStage.GREETING:
                self.stage = ReportStage.GENERATE_REPORT
        
        # 分析历史相关关键词
        elif any(keyword in user_input_lower for keyword in ['分析', '趋势', '变化', '发展', 'analyze', 'trend']):
            if self.stage == ReportStage.GREETING:
                self.stage = ReportStage.ANALYZE_HISTORY
                self.analysis_type = 'trends'
        
        # 对比相关关键词
        elif any(keyword in user_input_lower for keyword in ['对比', '比较', 'compare']):
            if self.stage == ReportStage.GREETING:
                self.stage = ReportStage.COMPARE_RECORDS
        
        # 问答相关
        elif any(keyword in user_input_lower for keyword in ['什么', '为什么', '怎么', '多少', '哪个', 'what', 'why', 'how']):
            if self.stage == ReportStage.GREETING:
                self.stage = ReportStage.ANSWER_QUESTION
    
    def _handle_special_commands(self, user_input: str) -> Optional[str]:
        """
        处理特殊命令（实际生成报告、分析等操作）
        
        Returns:
            处理结果文本，如果不是特殊命令返回None
        """
        user_input_lower = user_input.lower()
        
        # 确认生成报告
        if self.stage == ReportStage.GENERATE_REPORT:
            # 尝试提取病例ID或序号
            report_id = self._extract_report_id(user_input)
            if report_id:
                return self.generate_report(report_id)
        
        # 执行趋势分析
        if '执行趋势分析' in user_input or '开始分析' in user_input:
            if self.patient_id:
                return self.analyze_history_trends(self.patient_id)
        
        # 执行对比分析
        if '执行对比' in user_input or '开始对比' in user_input:
            # 尝试提取要对比的记录ID
            record_ids = self._extract_multiple_ids(user_input)
            if len(record_ids) >= 2:
                return self.compare_records(record_ids)
        
        # 检测异常
        if '检测异常' in user_input or '发现异常' in user_input:
            if self.patient_id:
                return self.detect_anomalies(self.patient_id)
        
        return None
    
    def _extract_report_id(self, text: str) -> Optional[int]:
        """从文本中提取病例ID"""
        import re
        
        # 优先检测明确的ID表达：ID:1, ID=1, Medical_Record_ID=1, 病例ID:1 等
        id_patterns = [
            r'(?:medical_record_)?id[:\s=]+(\d+)',  # ID:1, ID=1, Medical_Record_ID=1
            r'病例id[:\s=]+(\d+)',  # 病例ID:1
            r'record[:\s=]+(\d+)',  # Record:1
        ]
        
        for pattern in id_patterns:
            match = re.search(pattern, text.lower())
            if match:
                medical_record_id = int(match.group(1))
                print(f"[ReportAgent] 提取到明确的 Medical_Record_ID: {medical_record_id}")
                return medical_record_id
        
        # 检测"第X份"或"第X个"
        match = re.search(r'第\s*(\d+)\s*[份个]', text)
        if match:
            num = int(match.group(1))
            if 1 <= num <= len(self.user_reports):
                medical_record_id = self.user_reports[num - 1]['Medical_Record_ID']
                print(f"[ReportAgent] 提取到序号 {num}，对应 Medical_Record_ID: {medical_record_id}")
                return medical_record_id
        
        # 尝试从"最新"、"最近"等关键词
        if '最新' in text or '最近' in text or '最后' in text:
            if self.user_reports:
                medical_record_id = self.user_reports[0]['Medical_Record_ID']
                print(f"[ReportAgent] 提取到最新报告，Medical_Record_ID: {medical_record_id}")
                return medical_record_id
        
        # 最后尝试提取数字（作为序号）
        numbers = re.findall(r'\d+', text)
        if numbers:
            num = int(numbers[0])
            if num <= len(self.user_reports):
                medical_record_id = self.user_reports[num - 1]['Medical_Record_ID']
                print(f"[ReportAgent] 提取到序号 {num}，对应 Medical_Record_ID: {medical_record_id}")
                return medical_record_id
            else:
                # 可能直接是 Medical_Record_ID（数字很大）
                print(f"[ReportAgent] 将数字 {num} 作为 Medical_Record_ID")
                return num
        
        print(f"[ReportAgent] 无法从文本中提取报告ID: {text}")
        return None
    
    def _extract_multiple_ids(self, text: str) -> List[int]:
        """从文本中提取多个病例ID"""
        import re
        numbers = re.findall(r'\d+', text)
        
        ids = []
        for num_str in numbers:
            num = int(num_str)
            # 如果是序号，转换为实际ID
            if num <= len(self.user_reports):
                ids.append(self.user_reports[num - 1]['Medical_Record_ID'])
            else:
                ids.append(num)
        
        return ids
    
    def _prepare_context(self) -> Dict[str, str]:
        """准备对话上下文"""
        # 用户信息
        user_info_text = "未识别用户"
        if self.user_info:
            user_info_text = f"姓名：{self.user_info.get('Name')}，性别：{self.user_info.get('Gender')}，年龄：{self.user_info.get('Age')}"
        
        # 报告列表
        reports_text = "暂无历史报告"
        if self.user_reports:
            reports_list = []
            for idx, report in enumerate(self.user_reports[:10], 1):
                visit_date = report.get('Visit_Date', '未知日期')
                chief_complaint = report.get('Chief_Complaint', '无主诉')
                diagnosis = report.get('Diagnosis', '待诊断')
                record_id = report.get('Medical_Record_ID', '')
                reports_list.append(f"{idx}. 【ID:{record_id}】{visit_date} - {chief_complaint} ({diagnosis})")
            reports_text = "\n".join(reports_list)
            reports_text += f"\n\n共 {len(self.user_reports)} 份病例报告"
        
        # 角色和权限说明
        role_text = "医生" if self.role == "doctor" else "患者"
        if self.role == "doctor":
            permission_note = "您拥有完整权限：可以生成报告、分析历史、对比记录、回答问题。"
        else:
            permission_note = "您的权限受限：可以查看和分析现有报告、对比记录、回答问题，但不能生成新报告。"
        
        return {
            'user_info': user_info_text,
            'user_reports': reports_text,
            'role': role_text,
            'permission_note': permission_note
        }
    
    def _update_stage(self, user_input: str, response: str):
        """更新对话阶段"""
        # 根据回复内容和用户输入更新阶段
        if '再见' in user_input or '谢谢' in user_input or 'goodbye' in user_input.lower():
            self.stage = ReportStage.COMPLETED
    
    # ==================== 核心功能方法 ====================
    
    def generate_report(self, medical_record_id: int) -> str:
        """
        生成病例报告
        
        Args:
            medical_record_id: 病例ID
            
        Returns:
            操作结果消息
        """
        # 权限检查：只有医生可以生成报告
        if self.role != "doctor":
            print(f"[ReportAgent] 权限拒绝: 患者尝试生成报告")
            return "❌ 抱歉，只有医生才能生成新的病例报告。患者可以查看和分析现有的报告，但无法生成新报告。如果您需要报告，请联系您的医生。"
        
        try:
            print(f"[ReportAgent] 开始生成报告: Medical_Record_ID={medical_record_id}")
            
            # 生成报告
            pdf_path = self.report_generator.generate_report_from_db(medical_record_id)
            
            if pdf_path:
                return f"✅ 报告生成成功！\n\n文件路径：{pdf_path}\n\n您可以在该路径找到生成的报告文件。"
            else:
                return "❌ 报告生成失败，请检查病例数据是否完整。"
                
        except Exception as e:
            print(f"[ReportAgent] 生成报告失败: {e}")
            import traceback
            traceback.print_exc()
            return f"❌ 生成报告时出现错误：{str(e)}"
    
    def analyze_history_trends(self, patient_id: int) -> str:
        """
        分析病情发展趋势
        
        Args:
            patient_id: 用户ID
            
        Returns:
            分析结果文本
        """
        try:
            print(f"[ReportAgent] 开始分析病情趋势: Patient_ID={patient_id}")
            
            # 获取历史记录
            records = self.report_service.get_records_for_analysis(patient_id, limit=10)
            
            if not records:
                return "暂无历史记录可供分析。"
            
            # 构建分析提示
            analysis_prompt = self._build_trend_analysis_prompt(records)
            
            # 使用LLM分析
            analysis_chain = LLMChain(
                llm=self.llm,
                prompt=PromptTemplate(
                    input_variables=["records"],
                    template="""你是一位专业的医疗数据分析师，请分析以下病例记录，总结患者的病情发展趋势：

{records}

请从以下方面进行分析：
1. 病情发展轨迹（是改善、恶化还是稳定）
2. 主要症状的变化
3. 诊断的演变
4. 治疗效果评估
5. 需要注意的问题

分析结果："""
                )
            )
            
            analysis_result = analysis_chain.predict(records=analysis_prompt)
            
            return f"📊 病情趋势分析\n\n{analysis_result}"
            
        except Exception as e:
            print(f"[ReportAgent] 分析趋势失败: {e}")
            import traceback
            traceback.print_exc()
            return f"分析时出现错误：{str(e)}"
    
    def _build_trend_analysis_prompt(self, records: List[Dict]) -> str:
        """构建趋势分析提示"""
        prompt_parts = []
        for idx, record in enumerate(records, 1):
            visit_date = record.get('Visit_Date', '未知')
            chief_complaint = record.get('Chief_Complaint', '无')
            diagnosis = record.get('Diagnosis', '无')
            treatment = record.get('Treatment_Plan', '无')
            
            prompt_parts.append(f"""
第{idx}次就诊（{visit_date}）：
- 主诉：{chief_complaint}
- 诊断：{diagnosis}
- 治疗方案：{treatment}
""")
        
        return "\n".join(prompt_parts)
    
    def compare_records(self, record_ids: List[int]) -> str:
        """
        对比多次就诊记录
        
        Args:
            record_ids: 病例ID列表
            
        Returns:
            对比结果文本
        """
        try:
            print(f"[ReportAgent] 开始对比记录: record_ids={record_ids}")
            
            # 获取记录
            records = self.report_service.compare_records(record_ids)
            
            if len(records) < 2:
                return "需要至少两条记录才能进行对比。"
            
            # 构建对比提示
            compare_prompt = self._build_compare_prompt(records)
            
            # 使用LLM对比
            compare_chain = LLMChain(
                llm=self.llm,
                prompt=PromptTemplate(
                    input_variables=["records"],
                    template="""你是一位专业的医疗数据分析师，请对比以下病例记录，指出主要差异和变化：

{records}

请重点对比：
1. 症状的变化
2. 诊断的差异
3. 治疗方案的调整
4. 可能的原因分析

对比结果："""
                )
            )
            
            compare_result = compare_chain.predict(records=compare_prompt)
            
            return f"🔍 病例对比分析\n\n{compare_result}"
            
        except Exception as e:
            print(f"[ReportAgent] 对比记录失败: {e}")
            return f"对比时出现错误：{str(e)}"
    
    def _build_compare_prompt(self, records: List[Dict]) -> str:
        """构建对比提示"""
        prompt_parts = []
        for idx, record in enumerate(records, 1):
            visit_date = record.get('Visit_Date', '未知')
            chief_complaint = record.get('Chief_Complaint', '无')
            diagnosis = record.get('Diagnosis', '无')
            treatment = record.get('Treatment_Plan', '无')
            
            prompt_parts.append(f"""
记录{idx}（{visit_date}）：
- 主诉：{chief_complaint}
- 诊断：{diagnosis}
- 治疗方案：{treatment}
""")
        
        return "\n".join(prompt_parts)
    
    def detect_anomalies(self, patient_id: int) -> str:
        """
        检测历史记录中的异常变化
        
        Args:
            patient_id: 用户ID
            
        Returns:
            检测结果文本
        """
        try:
            print(f"[ReportAgent] 开始检测异常: Patient_ID={patient_id}")
            
            # 获取历史记录
            records = self.report_service.get_records_for_analysis(patient_id, limit=10)
            
            if len(records) < 2:
                return "需要至少两条记录才能检测异常。"
            
            # 构建检测提示
            anomaly_prompt = self._build_trend_analysis_prompt(records)
            
            # 使用LLM检测
            anomaly_chain = LLMChain(
                llm=self.llm,
                prompt=PromptTemplate(
                    input_variables=["records"],
                    template="""你是一位专业的医疗数据分析师，请检查以下病例记录，识别可能的异常变化或需要注意的问题：

{records}

请识别：
1. 病情突然恶化的情况
2. 治疗效果不佳的迹象
3. 新出现的严重症状
4. 需要紧急关注的问题
5. 可能需要进一步检查的情况

如果没有发现明显异常，也请说明。

检测结果："""
                )
            )
            
            anomaly_result = anomaly_chain.predict(records=anomaly_prompt)
            
            return f"⚠️ 异常检测结果\n\n{anomaly_result}"
            
        except Exception as e:
            print(f"[ReportAgent] 检测异常失败: {e}")
            return f"检测时出现错误：{str(e)}"
    
    def answer_history_question(self, question: str) -> str:
        """
        回答关于历史病例的问题
        
        Args:
            question: 用户问题
            
        Returns:
            回答文本
        """
        try:
            print(f"[ReportAgent] 回答历史问题: {question}")
            
            # 获取历史记录
            records = self.report_service.get_records_for_analysis(self.patient_id, limit=10)
            
            if not records:
                return "暂无历史记录可供查询。"
            
            # 构建历史信息
            history_info = self._build_trend_analysis_prompt(records)
            
            # 使用LLM回答
            qa_chain = LLMChain(
                llm=self.llm,
                prompt=PromptTemplate(
                    input_variables=["history", "question"],
                    template="""基于以下病例历史信息，回答用户的问题：

病例历史：
{history}

用户问题：{question}

请基于实际的病例数据回答，如果信息不足，请如实说明。

回答："""
                )
            )
            
            answer = qa_chain.predict(history=history_info, question=question)
            
            return answer
            
        except Exception as e:
            print(f"[ReportAgent] 回答问题失败: {e}")
            return f"回答时出现错误：{str(e)}"
    
    def get_user_reports_summary(self) -> Dict[str, Any]:
        """获取用户报告摘要"""
        return {
            'patient_id': self.patient_id,
            'phone_number': self.phone_number,
            'user_info': self.user_info,
            'total_reports': len(self.user_reports),
            'reports': self.user_reports[:5]  # 最近5份
        }
    
    def __del__(self):
        """析构函数"""
        try:
            if hasattr(self, 'report_service'):
                self.report_service.close()
            if hasattr(self, 'history_service'):
                self.history_service.close()
        except:
            pass


# ==================== 使用说明 ====================
# 
# 【创建智能体】
# agent = ReportAgent(phone_number="13900000001")
# 或
# agent = ReportAgent(patient_id=1)
# 
# 【对话交互】
# response, is_completed = agent.chat("我想生成最新的病例报告")
# 
# 【直接调用功能】
# result = agent.generate_report(medical_record_id=1)
# result = agent.analyze_history_trends(patient_id=1)
# result = agent.compare_records([1, 2, 3])
# result = agent.detect_anomalies(patient_id=1)
#

