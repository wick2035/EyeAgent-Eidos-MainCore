"""
预约仓储实现 - 通过后端API
"""
from typing import Optional, List
from datetime import datetime
import logging
from application.repositories.appointment_repository import IAppointmentRepository
from domain.models.appointment import Appointment
from domain.models.medical_record import MedicalRecord
from domain.exceptions.business_exceptions import InvalidAppointmentError
from infrastructure.api.backend_client import get_api_client, APIError, NetworkError

logger = logging.getLogger(__name__)


class AppointmentRepositoryImpl(IAppointmentRepository):
    """预约仓储实现（通过后端API）"""
    
    def __init__(self):
        self.api_client = get_api_client()
    
    def get_by_id(self, appointment_id: str) -> Optional[Appointment]:
        """根据ID获取预约"""
        logger.warning("[AppointmentRepository] get_by_id未实现（后端API不支持）")
        return None
    
    def get_by_patient(self, patient_id: str, limit: int = 10) -> List[Appointment]:
        """获取患者的预约列表"""
        logger.warning("[AppointmentRepository] get_by_patient未实现（后端API不支持）")
        return []
    
    def get_doctor_free_time(self, patient_id: str, date: str, 
                            hospital_key: str) -> dict:
        """
        获取医生空闲时间
        
        Args:
            patient_id: 患者UUID
            date: 日期字符串 yyyy-MM-dd
            hospital_key: 医院关键字
        
        Returns:
            包含空闲时间段和医生信息的字典
        """
        try:
            result = self.api_client.get_doctor_free_time(
                patient_id=patient_id,
                date=date,
                hospital_key=hospital_key
            )
            logger.info(f"[AppointmentRepository] 查询空闲时间成功: {date}")
            return result
            
        except (APIError, NetworkError) as e:
            logger.error(f"[AppointmentRepository] 查询空闲时间失败: {e}")
            raise InvalidAppointmentError(f"查询医生空闲时间失败: {str(e)}")
    
    def create(self, appointment: Appointment) -> Appointment:
        """
        创建预约
        
        Args:
            appointment: Appointment对象
        
        Returns:
            创建后的Appointment对象
        """
        try:
            # 构建请求数据
            request_data = {
                "patientId": appointment.patient_id,
                "doctorId": appointment.doctor_id,
                "reserveTime": appointment.reserve_time.isoformat(),
            }
            
            # 如果有医疗记录，添加到请求中
            if appointment.medical_record:
                mr = appointment.medical_record
                request_data["medicalRecord"] = {
                    "department": mr.department,
                    "chiefComplaint": mr.chief_complaint,
                    "presentIllness": mr.present_illness,
                    "medicalHistory": mr.medical_history or "无",
                    "allergyHistory": mr.allergy_history or "无",
                    "familyHistory": mr.family_history or "无",
                    "medicationHistory": mr.medication_history or "无",
                    "physicalExamination": mr.physical_examination or "",
                    "eyeExamResults": mr.eye_exam_results or "",
                    "specialExams": mr.special_exams or "",
                    "auxiliaryExams": mr.auxiliary_exams or "",
                    "diagnosis": mr.diagnosis or "",
                    "treatmentPlan": mr.treatment_plan or "",
                }
            
            # 调用后端API
            result = self.api_client.reserve_doctor(request_data)
            
            # 解析返回结果
            appointment.appointment_id = result.get("id")
            appointment.medical_record_id = result.get("medicalRecordId")
            appointment.status = "confirmed"
            
            logger.info(f"[AppointmentRepository] 预约创建成功: {appointment.appointment_id}")
            return appointment
            
        except (APIError, NetworkError) as e:
            logger.error(f"[AppointmentRepository] 创建预约失败: {e}")
            raise InvalidAppointmentError(f"创建预约失败: {str(e)}")
    
    def cancel(self, appointment_id: str) -> bool:
        """取消预约"""
        logger.warning("[AppointmentRepository] cancel未实现（后端API不支持）")
        return False

