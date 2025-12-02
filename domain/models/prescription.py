"""
Prescription 领域模型
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class PrescriptionDetail(BaseModel):
    """处方明细"""
    
    drug_name: str = Field(..., description="药品名称")
    dosage: str = Field(..., description="剂量")
    frequency: str = Field(..., description="用药频率")
    duration: str = Field(..., description="用药时长")
    usage: Optional[str] = Field(None, description="用法")
    notes: Optional[str] = Field(None, description="备注")


class Prescription(BaseModel):
    """处方实体"""
    
    prescription_id: str = Field(..., description="处方UUID")
    patient_id: str = Field(..., description="患者UUID")
    doctor_id: Optional[str] = Field(None, description="医生UUID")
    medical_record_id: Optional[str] = Field(None, description="病历UUID")
    
    # 处方信息
    prescription_number: Optional[str] = Field(None, description="处方编号")
    prescription_date: Optional[datetime] = Field(None, description="开方日期")
    
    # 处方明细
    details: List[PrescriptionDetail] = Field(default_factory=list, description="处方明细列表")
    
    # 备注
    notes: Optional[str] = Field(None, description="处方备注")
    
    # 时间戳
    created_at: Optional[datetime] = Field(None, description="创建时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prescription_id": "presc-550e8400-e29b-41d4-a716-446655440004",
                "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                "doctor_id": "doc-550e8400-e29b-41d4-a716-446655440002",
                "prescription_number": "RX20251201001",
                "prescription_date": "2025-12-01T10:00:00",
                "details": [
                    {
                        "drug_name": "左氧氟沙星滴眼液",
                        "dosage": "1滴",
                        "frequency": "每日3次",
                        "duration": "7天",
                        "usage": "滴眼"
                    }
                ]
            }
        }

