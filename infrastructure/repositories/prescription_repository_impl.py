"""
处方仓储实现 - 通过后端API
"""
from typing import Optional, List
from datetime import datetime
import logging
from application.repositories.prescription_repository import IPrescriptionRepository
from domain.models.prescription import Prescription, PrescriptionDetail
from domain.exceptions.business_exceptions import PrescriptionNotFoundError
from infrastructure.api.backend_client import get_api_client, APIError, NetworkError

logger = logging.getLogger(__name__)


class PrescriptionRepositoryImpl(IPrescriptionRepository):
    """处方仓储实现（通过后端API）"""
    
    def __init__(self):
        self.api_client = get_api_client()
    
    def get_by_id(self, prescription_id: str) -> Optional[Prescription]:
        """根据ID获取处方"""
        logger.warning("[PrescriptionRepository] get_by_id未实现（后端API不支持）")
        return None
    
    def get_by_patient(self, patient_id: str, limit: int = 10) -> List[Prescription]:
        """
        获取患者的处方列表（摘要）
        
        Args:
            patient_id: 患者UUID
            limit: 限制数量
        
        Returns:
            Prescription对象列表
        """
        try:
            result = self.api_client.get_patient_prescription_limit(
                patient_id=patient_id,
                limit=limit
            )
            
            prescriptions = []
            if result and "prescriptions" in result:
                for p_data in result["prescriptions"]:
                    prescriptions.append(Prescription(
                        prescription_id=p_data.get("prescriptionId", ""),
                        patient_id=patient_id,
                        doctor_id=p_data.get("doctorId"),
                        medical_record_id=p_data.get("medicalRecordId"),
                        prescription_number=p_data.get("prescriptionNumber"),
                        prescription_date=self._parse_datetime(p_data.get("prescriptionDate")),
                        notes=p_data.get("notes"),
                    ))
            
            logger.info(f"[PrescriptionRepository] 获取处方列表成功: {len(prescriptions)}条")
            return prescriptions
            
        except (APIError, NetworkError) as e:
            logger.error(f"[PrescriptionRepository] 获取处方列表失败: {e}")
            return []
    
    def get_by_patient_with_details(self, patient_id: str, 
                                    limit: int = 10) -> List[Prescription]:
        """
        获取患者的处方列表（包含详细药品信息）
        
        Args:
            patient_id: 患者UUID
            limit: 限制数量
        
        Returns:
            包含详细信息的Prescription对象列表
        """
        try:
            result = self.api_client.get_patient_prescription_detail(
                patient_id=patient_id,
                limit=limit
            )
            
            prescriptions = []
            if result and "prescriptions" in result:
                for p_data in result["prescriptions"]:
                    # 解析处方明细
                    details = []
                    if "details" in p_data:
                        for detail_data in p_data["details"]:
                            details.append(PrescriptionDetail(
                                drug_name=detail_data.get("drugName", ""),
                                dosage=detail_data.get("dosage", ""),
                                frequency=detail_data.get("frequency", ""),
                                duration=detail_data.get("duration", ""),
                                usage=detail_data.get("usage"),
                                notes=detail_data.get("notes"),
                            ))
                    
                    prescriptions.append(Prescription(
                        prescription_id=p_data.get("prescriptionId", ""),
                        patient_id=patient_id,
                        doctor_id=p_data.get("doctorId"),
                        medical_record_id=p_data.get("medicalRecordId"),
                        prescription_number=p_data.get("prescriptionNumber"),
                        prescription_date=self._parse_datetime(p_data.get("prescriptionDate")),
                        details=details,
                        notes=p_data.get("notes"),
                    ))
            
            logger.info(f"[PrescriptionRepository] 获取详细处方列表成功: {len(prescriptions)}条")
            return prescriptions
            
        except (APIError, NetworkError) as e:
            logger.error(f"[PrescriptionRepository] 获取详细处方列表失败: {e}")
            return []
    
    def create(self, prescription: Prescription) -> Prescription:
        """创建处方"""
        logger.warning("[PrescriptionRepository] create未实现（应由医生端创建）")
        return prescription
    
    def _parse_datetime(self, date_str: str) -> Optional[datetime]:
        """解析日期时间字符串"""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None

