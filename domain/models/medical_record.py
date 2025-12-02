"""
MedicalRecord 领域模型
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class MedicalRecord(BaseModel):
    """病历实体"""
    
    record_id: Optional[str] = Field(None, description="病历UUID")
    patient_id: str = Field(..., description="患者UUID")
    doctor_id: Optional[str] = Field(None, description="医生UUID")
    department: str = Field(default="眼科", description="科室")
    
    # 主诉和病史
    chief_complaint: str = Field(..., description="主诉")
    present_illness: str = Field(..., description="现病史")
    medical_history: Optional[str] = Field("无", description="既往史")
    allergy_history: Optional[str] = Field("无", description="过敏史")
    family_history: Optional[str] = Field("无", description="家族史")
    medication_history: Optional[str] = Field("无", description="用药史")
    
    # 检查结果
    physical_examination: Optional[str] = Field("", description="体格检查")
    eye_exam_results: Optional[str] = Field("", description="眼科检查结果")
    special_exams: Optional[str] = Field("", description="特殊检查")
    auxiliary_exams: Optional[str] = Field("", description="辅助检查")
    
    # 诊断和治疗
    diagnosis: Optional[str] = Field("", description="诊断")
    treatment_plan: Optional[str] = Field("", description="治疗方案")
    
    # 时间戳
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "record_id": "rec-550e8400-e29b-41d4-a716-446655440001",
                "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                "doctor_id": "doc-550e8400-e29b-41d4-a716-446655440002",
                "department": "眼科",
                "chief_complaint": "视力模糊",
                "present_illness": "近1周出现视力下降，看东西模糊",
                "medical_history": "无",
                "allergy_history": "无",
                "diagnosis": "待查",
                "treatment_plan": "进一步检查"
            }
        }

