"""
Patient 领域模型
"""
from typing import Optional
from pydantic import BaseModel, Field, validator
import uuid


class Patient(BaseModel):
    """患者实体"""
    
    patient_id: str = Field(..., description="患者UUID")
    name: str = Field(..., description="姓名")
    age: int = Field(..., ge=0, le=150, description="年龄")
    gender: str = Field(..., description="性别（男/女）")
    phone: str = Field(..., description="手机号")
    id_number: Optional[str] = Field(None, description="身份证号")
    medical_history: Optional[str] = Field(None, description="既往病史")
    allergy_history: Optional[str] = Field(None, description="过敏史")
    family_history: Optional[str] = Field(None, description="家族史")
    
    @validator("gender")
    def validate_gender(cls, v):
        """验证性别"""
        if v not in ["男", "女"]:
            raise ValueError("性别必须是'男'或'女'")
        return v
    
    @validator("phone")
    def validate_phone(cls, v):
        """验证手机号"""
        if not v or len(v) != 11 or not v.isdigit():
            raise ValueError("手机号必须是11位数字")
        return v
    
    @validator("patient_id")
    def validate_patient_id(cls, v):
        """验证patient_id是UUID格式"""
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("patient_id必须是有效的UUID格式")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "张三",
                "age": 35,
                "gender": "男",
                "phone": "13800138000",
                "id_number": "110101199001011234",
                "medical_history": "无",
                "allergy_history": "无",
                "family_history": "无"
            }
        }

