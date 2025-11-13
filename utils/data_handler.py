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
    
    def extract_from_conversation(self, conversation_history: List[Dict[str, str]]):
        """
        从对话历史中提取结构化数据
        这是一个智能提取方法，会分析对话内容
        """
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in conversation_history
        ])
        
        # 这里可以使用LLM进行智能提取，暂时先保留当前数据
        # 实际应用中，可以调用LLM分析对话历史并填充字段
        pass
    
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

