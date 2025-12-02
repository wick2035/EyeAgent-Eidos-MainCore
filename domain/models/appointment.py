"""
Appointment 领域模型
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from domain.models.medical_record import MedicalRecord


class Appointment(BaseModel):
    """预约实体"""
    
    appointment_id: Optional[str] = Field(None, description="预约UUID（Agenda_ID）")
    patient_id: str = Field(..., description="患者UUID")
    doctor_id: str = Field(..., description="医生UUID")
    reserve_time: datetime = Field(..., description="预约时间")
    
    # 预约状态
    status: Optional[str] = Field("pending", description="预约状态（pending/confirmed/cancelled）")
    
    # 关联病历
    medical_record: Optional[MedicalRecord] = Field(None, description="病历信息")
    medical_record_id: Optional[str] = Field(None, description="病历UUID")
    
    # 时间戳
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "appointment_id": "apt-550e8400-e29b-41d4-a716-446655440003",
                "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                "doctor_id": "doc-550e8400-e29b-41d4-a716-446655440002",
                "reserve_time": "2025-12-15T09:00:00",
                "status": "confirmed",
                "medical_record_id": "rec-550e8400-e29b-41d4-a716-446655440001"
            }
        }

