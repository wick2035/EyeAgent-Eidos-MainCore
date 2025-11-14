"""
数据处理模块 - 处理和导出患者病例JSON数据
"""
import json
from datetime import datetime
from typing import Dict, Any, List


class PatientDataHandler:
    """患者数据处理器"""
    
    def __init__(self):
        self.patient_data = self._init_patient_data()
    
    def _init_patient_data(self) -> Dict[str, Any]:
        """初始化患者数据结构"""
        return {
            "patient_info": {
                "name": "",
                "age": "",
                "gender": "",
                "contact": "",
                "id_number": ""
            },
            "chief_complaint": "",
            "present_illness": "",
            "symptoms": {
                "vision_change": "",
                "eye_pain": "",
                "redness": "",
                "discharge": "",
                "other": ""
            },
            "medical_history": "",
            "medication_history": "",
            "allergy_history": "",
            "family_history": "",
            "appointment": {
                "department": "眼科",
                "preferred_time": "",
                "doctor_preference": "",
                "urgency": ""
            },
            "diagnosis_suggestion": "",
            "timestamp": ""
        }
    
    def update_patient_info(self, field: str, value: str):
        """更新患者基本信息"""
        if field in self.patient_data["patient_info"]:
            self.patient_data["patient_info"][field] = value
    
    def update_symptoms(self, field: str, value: str):
        """更新症状信息"""
        if field in self.patient_data["symptoms"]:
            self.patient_data["symptoms"][field] = value
        elif field == "all":
            # 更新所有症状（用于批量更新）
            self.patient_data["symptoms"]["other"] = value
    
    def update_field(self, field: str, value: str):
        """更新顶级字段"""
        if field in self.patient_data:
            self.patient_data[field] = value
    
    def update_appointment(self, field: str, value: str):
        """更新预约信息"""
        if field in self.patient_data["appointment"]:
            self.patient_data["appointment"][field] = value
    
    def extract_from_conversation(self, conversation_history: List[Dict[str, str]], llm=None):
        """
        从对话历史中提取结构化数据
        这是一个智能提取方法，会分析对话内容
        """
        if not llm:
            return
        
        conversation_text = "\n".join([
            f"{'患者' if msg['role'] == 'user' else '助手'}: {msg['content']}" 
            for msg in conversation_history
        ])
        
        extraction_prompt = f"""
【重要任务】请仔细分析以下对话记录，提取患者回答过的所有医疗信息。

对话记录：
{conversation_text}

提取规则：
1. 只提取**患者明确回答过**的信息
2. 如果患者回答"无"、"没有"、"不清楚"等，该字段填写患者的原话（如"无"、"没有"）
3. 如果完全没有提及的信息，保持为空字符串 ""
4. 注意区分：患者说"无"和完全没提到是不同的
5. 姓名、年龄、性别、联系方式等基本信息要特别留意
6. 症状描述要尽可能详细完整地提取

请提取并返回以下完整结构的JSON（确保所有字段都存在）：
{{
  "patient_info": {{
    "name": "患者姓名",
    "age": "年龄（数字或描述）",
    "gender": "性别（男/女）",
    "contact": "联系方式（手机号）",
    "id_number": "身份证号"
  }},
  "chief_complaint": "主诉症状",
  "present_illness": "现病史（症状出现时间、性质、程度等）",
  "symptoms": {{
    "vision_change": "视力变化情况",
    "eye_pain": "眼痛情况",
    "redness": "眼红情况",
    "discharge": "分泌物情况",
    "other": "其他症状"
  }},
  "medical_history": "既往病史",
  "medication_history": "用药史",
  "allergy_history": "过敏史",
  "family_history": "家族史",
  "appointment": {{
    "preferred_time": "期望就诊时间",
    "doctor_preference": "医生偏好",
    "urgency": "紧急程度"
  }}
}}

只返回JSON格式，不要有任何其他说明文字：
"""
        try:
            import json
            response = llm.invoke(extraction_prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 提取JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                extracted_data = json.loads(json_str)
                
                print(f"[调试] 从对话历史提取到的数据: {json.dumps(extracted_data, ensure_ascii=False, indent=2)}")
                
                # 合并提取的数据，优先使用从对话中提取的新信息
                if "patient_info" in extracted_data:
                    for key, value in extracted_data["patient_info"].items():
                        if value and value.strip() and value != "":
                            # 如果提取到有效值，更新字段（即使已有值也更新，确保信息完整）
                            self.patient_data["patient_info"][key] = value
                
                if "symptoms" in extracted_data:
                    for key, value in extracted_data["symptoms"].items():
                        if value and value.strip() and value != "":
                            self.patient_data["symptoms"][key] = value
                
                if "appointment" in extracted_data:
                    for key, value in extracted_data["appointment"].items():
                        if value and value.strip() and value != "":
                            self.patient_data["appointment"][key] = value
                
                # 更新其他字段 - 如果提取到非空值则更新
                for field in ["chief_complaint", "present_illness", "medical_history", 
                            "medication_history", "allergy_history", "family_history"]:
                    if field in extracted_data and extracted_data[field]:
                        if extracted_data[field].strip():  # 只要不是空字符串就更新
                            self.patient_data[field] = extracted_data[field]
                            
        except Exception as e:
            # 提取失败，打印错误信息以便调试
            print(f"[警告] 从对话历史提取信息时出错: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def finalize_data(self) -> Dict[str, Any]:
        """
        完成数据收集，添加时间戳并返回最终数据
        """
        self.patient_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.patient_data
    
    def to_json(self, indent: int = 2) -> str:
        """导出为JSON字符串"""
        return json.dumps(self.patient_data, ensure_ascii=False, indent=indent)
    
    def save_to_file(self, filename: str = None):
        """保存到文件"""
        if filename is None:
            filename = f"patient_record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
        
        return filename
    
    def is_complete(self) -> bool:
        """检查必填字段是否完整"""
        required_fields = [
            self.patient_data["patient_info"]["name"],
            self.patient_data["patient_info"]["age"],
            self.patient_data["patient_info"]["gender"],
            self.patient_data["patient_info"]["contact"],
            self.patient_data["chief_complaint"],
        ]
        return all(field for field in required_fields)
    
    def get_missing_fields(self) -> List[str]:
        """获取缺失的必填字段"""
        missing = []
        
        if not self.patient_data["patient_info"]["name"]:
            missing.append("姓名")
        if not self.patient_data["patient_info"]["age"]:
            missing.append("年龄")
        if not self.patient_data["patient_info"]["gender"]:
            missing.append("性别")
        if not self.patient_data["patient_info"]["contact"]:
            missing.append("联系方式")
        if not self.patient_data["chief_complaint"]:
            missing.append("主诉症状")
        
        return missing
    
    def reset(self):
        """重置数据"""
        self.patient_data = self._init_patient_data()

