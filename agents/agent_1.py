"""
1号智能体 - 健康咨询、眼科分诊、医生预约
"""
import json
from enum import Enum
from typing import Dict, List, Any
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from utils.llm_config import get_llm
from utils.data_handler import PatientDataHandler


class ConversationStage(Enum):
    """对话阶段"""
    GREETING = "greeting"  # 问候阶段
    HEALTH_CONSULTATION = "health_consultation"  # 健康咨询阶段
    SYMPTOM_ASSESSMENT = "symptom_assessment"  # 症状评估阶段
    APPOINTMENT_INQUIRY = "appointment_inquiry"  # 询问是否预约
    PATIENT_INFO_COLLECTION = "patient_info_collection"  # 收集患者信息
    OPHTHALMOLOGY_TRIAGE = "ophthalmology_triage"  # 眼科分诊问诊
    MEDICAL_HISTORY = "medical_history"  # 病史采集
    APPOINTMENT_BOOKING = "appointment_booking"  # 预约医生
    COMPLETED = "completed"  # 完成


class HealthAgent:
    """1号健康咨询智能体"""
    
    def __init__(self):
        self.llm = get_llm()
        self.memory = ConversationBufferMemory(return_messages=True)
        self.data_handler = PatientDataHandler()
        self.stage = ConversationStage.GREETING
        self.conversation_history = []
        self.collected_fields = set()  # 已收集的字段
        self.needs_appointment = False  # 是否需要预约
        
        # 初始化对话链
        self.conversation_chain = self._create_conversation_chain()
    
    def _create_conversation_chain(self) -> ConversationChain:
        """创建对话链"""
        template = """你是一位专业的医疗健康咨询助手，专门负责眼科相关的健康咨询和分诊服务。

当前对话阶段：{stage}

你的职责：
1. 提供专业的健康咨询建议
2. 评估患者症状的严重程度
3. 在适当的时候主动询问患者是否需要预约医生
4. 进行详细的眼科分诊问诊，收集患者信息
5. 帮助患者完成医生预约

对话指南：
- 语气温和、专业、有同理心
- 逐步引导患者描述症状，不要一次问太多问题
- 根据症状判断严重程度，如果需要就医，主动建议预约
- 在眼科分诊阶段，系统地收集患者的基本信息、症状、病史等
- 确保收集完整的信息后再完成预约

已收集的信息字段：{collected_fields}

对话历史：
{history}

患者：{input}
助手："""
        
        prompt = PromptTemplate(
            input_variables=["stage", "collected_fields", "history", "input"],
            template=template
        )
        
        chain = ConversationChain(
            llm=self.llm,
            prompt=prompt,
            memory=self.memory,
            verbose=False
        )
        
        return chain
    
    def _get_stage_prompt(self) -> str:
        """根据当前阶段返回提示信息"""
        stage_prompts = {
            ConversationStage.GREETING: "初次接待，询问患者的健康问题",
            ConversationStage.HEALTH_CONSULTATION: "正在进行健康咨询，了解患者症状",
            ConversationStage.SYMPTOM_ASSESSMENT: "评估症状严重程度",
            ConversationStage.APPOINTMENT_INQUIRY: "询问患者是否需要预约医生",
            ConversationStage.PATIENT_INFO_COLLECTION: "收集患者基本信息（姓名、年龄、性别、联系方式）",
            ConversationStage.OPHTHALMOLOGY_TRIAGE: "进行眼科分诊问诊，详细了解眼部症状",
            ConversationStage.MEDICAL_HISTORY: "采集病史（既往病史、用药史、过敏史、家族史）",
            ConversationStage.APPOINTMENT_BOOKING: "确认预约信息（期望就诊时间、医生偏好、紧急程度）",
            ConversationStage.COMPLETED: "预约已完成，总结信息"
        }
        return stage_prompts.get(self.stage, "")
    
    def _extract_info_from_response(self, user_input: str):
        """从用户输入中提取信息并更新数据"""
        user_lower = user_input.lower()
        
        # 根据当前阶段提取不同的信息
        if self.stage == ConversationStage.HEALTH_CONSULTATION or \
           self.stage == ConversationStage.SYMPTOM_ASSESSMENT:
            # 提取主诉和症状
            if not self.data_handler.patient_data["chief_complaint"]:
                self.data_handler.update_field("chief_complaint", user_input)
                self.collected_fields.add("主诉")
        
        elif self.stage == ConversationStage.PATIENT_INFO_COLLECTION:
            # 使用LLM提取结构化信息
            self._extract_patient_info_with_llm(user_input)
        
        elif self.stage == ConversationStage.OPHTHALMOLOGY_TRIAGE:
            # 提取详细症状和现病史
            if "现病史" not in self.collected_fields:
                if self.data_handler.patient_data["present_illness"]:
                    self.data_handler.patient_data["present_illness"] += " " + user_input
                else:
                    self.data_handler.update_field("present_illness", user_input)
                self.collected_fields.add("现病史")
        
        elif self.stage == ConversationStage.MEDICAL_HISTORY:
            # 提取病史信息
            if "既往病史" not in self.collected_fields and ("病史" in user_lower or "疾病" in user_lower or "没有" in user_lower or "无" in user_lower):
                self.data_handler.update_field("medical_history", user_input)
                self.collected_fields.add("既往病史")
            elif "用药史" not in self.collected_fields and ("用药" in user_lower or "药物" in user_lower or "吃药" in user_lower):
                self.data_handler.update_field("medication_history", user_input)
                self.collected_fields.add("用药史")
            elif "过敏史" not in self.collected_fields and ("过敏" in user_lower):
                self.data_handler.update_field("allergy_history", user_input)
                self.collected_fields.add("过敏史")
        
        elif self.stage == ConversationStage.APPOINTMENT_BOOKING:
            # 提取预约信息
            self._extract_appointment_info(user_input)
    
    def _extract_patient_info_with_llm(self, user_input: str):
        """使用LLM提取患者基本信息"""
        extraction_prompt = f"""
从以下对话中提取患者的基本信息，以JSON格式返回。如果某项信息未提及，则保持为空字符串。

对话内容：{user_input}

请提取以下信息：
- name: 姓名
- age: 年龄
- gender: 性别（男/女）
- contact: 联系方式（手机号）
- id_number: 身份证号（如果提到）

只返回JSON格式，不要有其他内容：
"""
        try:
            response = self.llm.invoke(extraction_prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 尝试提取JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                extracted_data = json.loads(json_str)
                
                # 更新数据
                for field, value in extracted_data.items():
                    if value and value.strip():
                        self.data_handler.update_patient_info(field, value)
                        self.collected_fields.add(field)
        except Exception as e:
            # 如果LLM提取失败，使用简单的规则提取
            if "姓名" not in self.collected_fields:
                # 简单的姓名提取逻辑
                words = user_input.split()
                for word in words:
                    if len(word) >= 2 and len(word) <= 4:
                        self.data_handler.update_patient_info("name", word)
                        self.collected_fields.add("姓名")
                        break
    
    def _extract_appointment_info(self, user_input: str):
        """提取预约信息"""
        if "期望时间" not in self.collected_fields:
            # 检查是否包含时间相关词汇
            time_keywords = ["明天", "后天", "下周", "今天", "上午", "下午", "晚上", "点", "月", "日", "号"]
            if any(keyword in user_input for keyword in time_keywords):
                self.data_handler.update_appointment("preferred_time", user_input)
                self.collected_fields.add("期望时间")
        
        # 提取紧急程度
        if "紧急程度" not in self.collected_fields:
            if "紧急" in user_input or "急" in user_input or "严重" in user_input:
                self.data_handler.update_appointment("urgency", "紧急")
                self.collected_fields.add("紧急程度")
            elif "不急" in user_input or "普通" in user_input:
                self.data_handler.update_appointment("urgency", "普通")
                self.collected_fields.add("紧急程度")
    
    def _update_stage(self, user_input: str, ai_response: str):
        """根据对话内容更新阶段"""
        user_lower = user_input.lower()
        response_lower = ai_response.lower()
        
        if self.stage == ConversationStage.GREETING:
            # 用户描述了症状，进入健康咨询阶段
            if len(user_input) > 10:
                self.stage = ConversationStage.HEALTH_CONSULTATION
        
        elif self.stage == ConversationStage.HEALTH_CONSULTATION:
            # 进入症状评估
            self.stage = ConversationStage.SYMPTOM_ASSESSMENT
        
        elif self.stage == ConversationStage.SYMPTOM_ASSESSMENT:
            # 判断是否应该询问预约
            eye_keywords = ["眼", "视力", "模糊", "疼", "红", "痒", "流泪", "分泌物", "看不清"]
            if any(keyword in user_input for keyword in eye_keywords):
                self.stage = ConversationStage.APPOINTMENT_INQUIRY
        
        elif self.stage == ConversationStage.APPOINTMENT_INQUIRY:
            # 用户同意预约
            positive_keywords = ["是", "好", "要", "需要", "可以", "行", "对", "嗯", "预约"]
            if any(keyword in user_lower for keyword in positive_keywords):
                self.needs_appointment = True
                self.stage = ConversationStage.PATIENT_INFO_COLLECTION
            elif any(keyword in user_lower for keyword in ["不", "否", "算了", "不用"]):
                self.needs_appointment = False
                self.stage = ConversationStage.COMPLETED
        
        elif self.stage == ConversationStage.PATIENT_INFO_COLLECTION:
            # 检查是否收集了基本信息
            required = {"姓名", "年龄", "性别", "联系方式"}
            if len(required & self.collected_fields) >= 2:  # 至少收集了2项
                self.stage = ConversationStage.OPHTHALMOLOGY_TRIAGE
        
        elif self.stage == ConversationStage.OPHTHALMOLOGY_TRIAGE:
            # 眼科分诊进行一定轮次后进入病史采集
            if len(self.conversation_history) > 8:
                self.stage = ConversationStage.MEDICAL_HISTORY
        
        elif self.stage == ConversationStage.MEDICAL_HISTORY:
            # 病史采集完成后进入预约确认
            if "既往病史" in self.collected_fields or len(self.conversation_history) > 12:
                self.stage = ConversationStage.APPOINTMENT_BOOKING
        
        elif self.stage == ConversationStage.APPOINTMENT_BOOKING:
            # 预约信息收集完成
            if "期望时间" in self.collected_fields:
                self.stage = ConversationStage.COMPLETED
    
    def chat(self, user_input: str) -> str:
        """处理用户输入并返回响应"""
        # 记录对话历史
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })
        
        # 提取信息
        self._extract_info_from_response(user_input)
        
        # 生成回复
        stage_desc = self._get_stage_prompt()
        collected = ", ".join(self.collected_fields) if self.collected_fields else "暂无"
        
        response = self.conversation_chain.predict(
            stage=stage_desc,
            collected_fields=collected,
            input=user_input
        )
        
        # 记录AI响应
        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })
        
        # 更新阶段
        self._update_stage(user_input, response)
        
        # 如果完成，生成最终诊断建议
        if self.stage == ConversationStage.COMPLETED and self.needs_appointment:
            self._generate_diagnosis_suggestion()
        
        return response
    
    def _generate_diagnosis_suggestion(self):
        """生成初步诊断建议"""
        symptoms_summary = self.data_handler.patient_data["chief_complaint"]
        if symptoms_summary:
            suggestion = f"根据患者描述的症状（{symptoms_summary}），建议眼科门诊详细检查。"
            self.data_handler.update_field("diagnosis_suggestion", suggestion)
    
    def get_patient_data_json(self) -> str:
        """获取患者数据的JSON格式"""
        self.data_handler.finalize_data()
        return self.data_handler.to_json()
    
    def get_patient_data(self) -> Dict[str, Any]:
        """获取患者数据字典"""
        self.data_handler.finalize_data()
        return self.data_handler.patient_data
    
    def is_completed(self) -> bool:
        """检查对话是否完成"""
        return self.stage == ConversationStage.COMPLETED
    
    def reset(self):
        """重置智能体状态"""
        self.memory.clear()
        self.data_handler.reset()
        self.stage = ConversationStage.GREETING
        self.conversation_history = []
        self.collected_fields = set()
        self.needs_appointment = False

