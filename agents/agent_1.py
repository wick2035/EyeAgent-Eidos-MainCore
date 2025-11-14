"""
1号智能体 - 健康咨询、眼科分诊、医生预约
"""
import json
from enum import Enum
from typing import Dict, List, Any
from langchain.chains import LLMChain
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
        self.data_handler = PatientDataHandler()
        self.stage = ConversationStage.GREETING
        self.conversation_history = []
        self.collected_fields = set()  # 已收集的字段
        self.needs_appointment = False  # 是否需要预约
        
        # 初始化对话链
        self.conversation_chain = self._create_conversation_chain()
    
    def _create_conversation_chain(self):
        """创建对话链 - 使用LLMChain代替ConversationChain以支持自定义变量"""
        from langchain.chains import LLMChain
        
        template = """你叫小Eye，你是一位专业的EyeAgent平台医疗健康咨询助手，专门负责眼科相关的健康咨询和分诊服务。

当前对话阶段：{stage}

你的职责：
1. 提供专业的健康咨询建议
2. 评估患者症状的严重程度
3. 在适当的时候主动询问患者是否需要预约医生
4. 进行详细的眼科分诊问诊，收集患者信息
5. 帮助患者完成医生预约

【重要】一旦确定患者需要预约，你必须竭尽全力收集以下所有信息：
- 患者基本信息：姓名、年龄、性别、联系方式、身份证号
- 主诉症状：患者的主要不适
- 现病史：症状出现的时间、性质、程度、诱因、缓解因素等
- 详细症状：视力变化、眼痛、眼红、分泌物、其他症状
- 既往病史：过往的眼科疾病或其他疾病
- 用药史：正在使用或曾经使用的眼药或其他药物
- 过敏史：药物过敏、食物过敏等
- 家族史：家族中是否有眼科疾病或遗传病
- 预约信息：期望就诊时间、医生偏好、紧急程度

对话指南：
- 语气温和、专业、有同理心
- 逐步引导患者描述症状，每次询问1-2个相关问题
- 根据症状判断严重程度，如果需要就医，主动建议预约
- 在收集信息时要有针对性，结合患者回答追问细节
- 对于缺失的重要信息，要主动询问
- 确保收集完整的信息后再完成预约

已收集的信息字段：{collected_fields}
缺失的关键信息：{missing_fields}

对话历史：
{history}

患者：{input}
助手："""
        
        prompt = PromptTemplate(
            input_variables=["stage", "collected_fields", "missing_fields", "history", "input"],
            template=template
        )
        
        chain = LLMChain(
            llm=self.llm,
            prompt=prompt,
            verbose=False
        )
        
        return chain
    
    def _get_stage_prompt(self) -> str:
        """根据当前阶段返回提示信息"""
        stage_prompts = {
            ConversationStage.GREETING: "初次接待，询问患者的健康问题",
            ConversationStage.HEALTH_CONSULTATION: "正在进行健康咨询，了解患者症状。主动询问症状的详细情况。",
            ConversationStage.SYMPTOM_ASSESSMENT: "评估症状严重程度，判断是否需要就医",
            ConversationStage.APPOINTMENT_INQUIRY: "询问患者是否需要预约医生",
            ConversationStage.PATIENT_INFO_COLLECTION: "【重要】收集患者基本信息。必须询问并记录：姓名、年龄、性别、联系方式（手机号）。可以一次询问多项。",
            ConversationStage.OPHTHALMOLOGY_TRIAGE: "【重要】进行眼科分诊。详细询问：症状出现时间、症状持续多久、症状的具体表现、有无诱因、是否加重或减轻。",
            ConversationStage.MEDICAL_HISTORY: "【重要】采集完整病史。必须询问：既往眼科疾病或其他疾病、正在使用的药物、药物过敏史、家族遗传病史。即使患者说'无'也要明确记录。",
            ConversationStage.APPOINTMENT_BOOKING: "【重要】确认预约详情。必须询问：期望就诊时间、症状紧急程度、是否有医生偏好。",
            ConversationStage.COMPLETED: "预约已完成，总结信息并告知患者"
        }
        return stage_prompts.get(self.stage, "")
    
    def _extract_info_from_response(self, user_input: str):
        """从用户输入中提取信息并更新数据"""
        user_lower = user_input.lower()
        
        # 如果已经确定需要预约，使用全面的信息提取
        if self.needs_appointment:
            self._extract_comprehensive_info(user_input)
        
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
                field_name_map = {
                    "name": "姓名",
                    "age": "年龄", 
                    "gender": "性别",
                    "contact": "联系方式",
                    "id_number": "身份证号"
                }
                
                for field, value in extracted_data.items():
                    if value and value.strip():
                        self.data_handler.update_patient_info(field, value)
                        chinese_name = field_name_map.get(field, field)
                        self.collected_fields.add(chinese_name)
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
        
        # 提取医生偏好
        if "医生偏好" not in self.collected_fields:
            doctor_keywords = ["专家", "教授", "主任", "医生", "大夫"]
            if any(keyword in user_input for keyword in doctor_keywords):
                self.data_handler.update_appointment("doctor_preference", user_input)
                self.collected_fields.add("医生偏好")
    
    def _get_missing_critical_fields(self) -> List[str]:
        """获取缺失的关键信息字段"""
        missing = []
        
        # 患者基本信息
        if not self.data_handler.patient_data["patient_info"]["name"]:
            missing.append("姓名")
        if not self.data_handler.patient_data["patient_info"]["age"]:
            missing.append("年龄")
        if not self.data_handler.patient_data["patient_info"]["gender"]:
            missing.append("性别")
        if not self.data_handler.patient_data["patient_info"]["contact"]:
            missing.append("联系方式")
        
        # 症状信息
        if not self.data_handler.patient_data["chief_complaint"]:
            missing.append("主诉症状")
        if not self.data_handler.patient_data["present_illness"]:
            missing.append("现病史")
        
        # 病史信息
        if not self.data_handler.patient_data["medical_history"]:
            missing.append("既往病史")
        if not self.data_handler.patient_data["allergy_history"]:
            missing.append("过敏史")
        
        # 预约信息（仅在需要预约时检查）
        if self.needs_appointment:
            if not self.data_handler.patient_data["appointment"]["preferred_time"]:
                missing.append("期望就诊时间")
            if not self.data_handler.patient_data["appointment"]["urgency"]:
                missing.append("紧急程度")
        
        return missing
    
    def _extract_comprehensive_info(self, user_input: str):
        """使用LLM全面提取用户输入中的所有信息"""
        extraction_prompt = f"""
【重要】请从以下用户的回答中提取所有医疗和个人信息。

用户回答：{user_input}

提取规则：
1. 提取用户明确提到的所有信息
2. 如果用户说"无"、"没有"，该字段填写"无"或"没有"
3. 如果没提到的信息，字段值为空字符串 ""
4. 特别注意：姓名、年龄、性别、手机号等基本信息

请提取以下信息（如果存在）：
1. 患者基本信息：
   - name: 姓名（人名）
   - age: 年龄（数字）
   - gender: 性别（男/女）
   - contact: 联系方式（手机号）
   - id_number: 身份证号

2. 症状相关：
   - symptoms: 症状描述（详细）
   - duration: 症状持续时间
   - severity: 严重程度

3. 病史相关：
   - medical_history: 既往病史（眼科或其他疾病）
   - medication_history: 用药史（正在使用或曾用的药物）
   - allergy_history: 过敏史（药物或食物过敏）
   - family_history: 家族史（遗传病、眼科疾病等）

4. 预约相关：
   - preferred_time: 期望就诊时间（具体日期时间）
   - urgency: 紧急程度（紧急/普通/不急）
   - doctor_preference: 医生偏好（专家/主任等）

只返回JSON格式，不要有其他说明：
{{"name": "", "age": "", "symptoms": "", "medical_history": "", "allergy_history": ""}}
"""
        try:
            response = self.llm.invoke(extraction_prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 提取JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                extracted_data = json.loads(json_str)
                
                # 更新患者基本信息 - 只要提取到有效值就更新
                for field in ["name", "age", "gender", "contact", "id_number"]:
                    if field in extracted_data and extracted_data[field] and extracted_data[field].strip():
                        self.data_handler.update_patient_info(field, extracted_data[field])
                        field_cn_map = {
                            "name": "姓名", "age": "年龄", "gender": "性别",
                            "contact": "联系方式", "id_number": "身份证号"
                        }
                        self.collected_fields.add(field_cn_map[field])
                
                # 更新症状信息
                if "symptoms" in extracted_data and extracted_data["symptoms"] and extracted_data["symptoms"].strip():
                    current_illness = self.data_handler.patient_data["present_illness"]
                    if current_illness:
                        # 避免重复添加相同内容
                        if extracted_data["symptoms"] not in current_illness:
                            self.data_handler.update_field("present_illness", current_illness + " " + extracted_data["symptoms"])
                    else:
                        self.data_handler.update_field("present_illness", extracted_data["symptoms"])
                    self.collected_fields.add("症状描述")
                
                if "duration" in extracted_data and extracted_data["duration"] and extracted_data["duration"].strip():
                    current_illness = self.data_handler.patient_data["present_illness"]
                    duration_text = "，持续时间：" + extracted_data["duration"]
                    # 避免重复添加持续时间
                    if "持续时间" not in current_illness:
                        self.data_handler.update_field("present_illness", current_illness + duration_text)
                    self.collected_fields.add("症状持续时间")
                
                # 更新病史 - 总是使用最新提取的信息
                if "medical_history" in extracted_data and extracted_data["medical_history"] and extracted_data["medical_history"].strip():
                    self.data_handler.update_field("medical_history", extracted_data["medical_history"])
                    self.collected_fields.add("既往病史")
                
                if "medication_history" in extracted_data and extracted_data["medication_history"] and extracted_data["medication_history"].strip():
                    self.data_handler.update_field("medication_history", extracted_data["medication_history"])
                    self.collected_fields.add("用药史")
                
                if "allergy_history" in extracted_data and extracted_data["allergy_history"] and extracted_data["allergy_history"].strip():
                    self.data_handler.update_field("allergy_history", extracted_data["allergy_history"])
                    self.collected_fields.add("过敏史")
                
                if "family_history" in extracted_data and extracted_data["family_history"] and extracted_data["family_history"].strip():
                    self.data_handler.update_field("family_history", extracted_data["family_history"])
                    self.collected_fields.add("家族史")
                
                # 更新预约信息
                if "preferred_time" in extracted_data and extracted_data["preferred_time"] and extracted_data["preferred_time"].strip():
                    self.data_handler.update_appointment("preferred_time", extracted_data["preferred_time"])
                    self.collected_fields.add("期望时间")
                
                if "urgency" in extracted_data and extracted_data["urgency"] and extracted_data["urgency"].strip():
                    self.data_handler.update_appointment("urgency", extracted_data["urgency"])
                    self.collected_fields.add("紧急程度")
                
                if "doctor_preference" in extracted_data and extracted_data["doctor_preference"] and extracted_data["doctor_preference"].strip():
                    self.data_handler.update_appointment("doctor_preference", extracted_data["doctor_preference"])
                    self.collected_fields.add("医生偏好")
                    
        except Exception as e:
            # 如果提取失败，静默处理
            pass
    
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
            # 检查是否收集了基本信息（要求更高，至少3项）
            required = {"姓名", "年龄", "性别", "联系方式"}
            if len(required & self.collected_fields) >= 3:  # 至少收集了3项
                self.stage = ConversationStage.OPHTHALMOLOGY_TRIAGE
        
        elif self.stage == ConversationStage.OPHTHALMOLOGY_TRIAGE:
            # 眼科分诊要收集更多症状详情
            symptom_related = {"症状描述", "症状持续时间", "现病史"}
            if len(symptom_related & self.collected_fields) >= 2:
                self.stage = ConversationStage.MEDICAL_HISTORY
        
        elif self.stage == ConversationStage.MEDICAL_HISTORY:
            # 病史采集要求更完整
            history_related = {"既往病史", "用药史", "过敏史"}
            # 至少收集了2项病史相关信息
            if len(history_related & self.collected_fields) >= 2:
                self.stage = ConversationStage.APPOINTMENT_BOOKING
        
        elif self.stage == ConversationStage.APPOINTMENT_BOOKING:
            # 预约信息收集完成，检查关键信息是否齐全
            appointment_related = {"期望时间", "紧急程度"}
            critical_missing = self._get_missing_critical_fields()
            
            # 只有预约信息齐全且关键必填项不超过2个缺失时才完成
            if len(appointment_related & self.collected_fields) >= 2 and len(critical_missing) <= 2:
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
        
        # 获取缺失的关键字段
        missing_fields = self._get_missing_critical_fields()
        missing_desc = "、".join(missing_fields) if missing_fields else "无"
        
        # 构建对话历史文本
        history_text = ""
        for msg in self.conversation_history[:-1]:  # 不包括当前用户输入
            role = "患者" if msg["role"] == "user" else "助手"
            history_text += f"{role}：{msg['content']}\n"
        
        # 调用LLMChain
        response = self.conversation_chain.run(
            stage=stage_desc,
            collected_fields=collected,
            missing_fields=missing_desc,
            history=history_text,
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
        """生成初步诊断建议，并进行最终的全面信息提取"""
        # 在生成诊断前，使用LLM从完整对话历史中提取所有可能遗漏的信息
        self.data_handler.extract_from_conversation(self.conversation_history, self.llm)
        
        # 智能填充症状细节
        self._fill_symptom_details()
        
        symptoms_summary = self.data_handler.patient_data["chief_complaint"]
        if symptoms_summary:
            suggestion = f"根据患者描述的症状（{symptoms_summary}），建议眼科门诊详细检查。"
            self.data_handler.update_field("diagnosis_suggestion", suggestion)
    
    def _fill_symptom_details(self):
        """智能填充症状详情字段"""
        present_illness = self.data_handler.patient_data["present_illness"]
        chief_complaint = self.data_handler.patient_data["chief_complaint"]
        
        if not present_illness and not chief_complaint:
            return
        
        symptom_text = f"{chief_complaint} {present_illness}"
        
        fill_prompt = f"""
根据患者的症状描述，提取并分类症状信息。

症状描述：{symptom_text}

请提取以下具体症状类别（如果提到，否则为空字符串）：
- vision_change: 视力变化（如视力下降、模糊、看不清等）
- eye_pain: 眼痛（眼睛疼痛、不适等）
- redness: 眼红（眼睛发红、充血等）
- discharge: 分泌物（眼屎、流泪、分泌物等）
- other: 其他症状（痒、干涩、畏光等）

返回JSON格式：
{{"vision_change": "", "eye_pain": "", "redness": "", "discharge": "", "other": ""}}
"""
        try:
            response = self.llm.invoke(fill_prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                symptom_details = json.loads(json_str)
                
                for field, value in symptom_details.items():
                    if value and value.strip():
                        self.data_handler.update_symptoms(field, value)
        except Exception as e:
            pass
    
    def get_patient_data_json(self) -> str:
        """获取患者数据的JSON格式"""
        self.data_handler.finalize_data()
        return self.data_handler.to_json()
    
    def get_patient_data(self) -> Dict[str, Any]:
        """获取患者数据字典"""
        print(f"\n[调试] 开始导出患者数据，当前对话历史共 {len(self.conversation_history)} 条消息")
        
        # 导出前再次从完整对话历史中提取信息，确保不遗漏
        if self.conversation_history:
            print("[调试] 正在从对话历史中提取信息...")
            self.data_handler.extract_from_conversation(self.conversation_history, self.llm)
        
        self.data_handler.finalize_data()
        
        print(f"[调试] 最终患者数据:")
        print(json.dumps(self.data_handler.patient_data, ensure_ascii=False, indent=2))
        
        return self.data_handler.patient_data
    
    def is_completed(self) -> bool:
        """检查对话是否完成"""
        return self.stage == ConversationStage.COMPLETED
    
    def reset(self):
        """重置智能体状态"""
        self.data_handler.reset()
        self.stage = ConversationStage.GREETING
        self.conversation_history = []
        self.collected_fields = set()
        self.needs_appointment = False

