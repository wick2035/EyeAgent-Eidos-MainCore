"""
患者仓储实现 - 通过后端API
"""
from typing import Optional, List
import logging
from application.repositories.patient_repository import IPatientRepository
from domain.models.patient import Patient
from domain.exceptions.business_exceptions import PatientNotFoundError
from infrastructure.api.backend_client import get_api_client, APIError, NetworkError

logger = logging.getLogger(__name__)


class PatientRepositoryImpl(IPatientRepository):
    """患者仓储实现（通过后端API）"""
    
    def __init__(self):
        self.api_client = get_api_client()
    
    def get_by_id(self, patient_id: str) -> Optional[Patient]:
        """
        根据ID获取患者（通过后端API）

        使用 /agent/api/get-medical-record 接口获取患者信息和病历
        从病历中提取既往史、过敏史、家族史等信息
        """
        try:
            # 调用新的get_medical_records接口
            result = self.api_client.get_medical_records(patient_id)

            if not result:
                logger.warning(f"[PatientRepository] 患者不存在: {patient_id}")
                return None

            # 处理返回格式
            # 注意：接口返回的是病历列表，而不是 {patient: {}, medicalRecords: []}
            if isinstance(result, list):
                # 如果是列表，说明返回的是病历列表
                medical_records = result
                # 需要从病历中提取患者ID，然后调用get_all_patients获取基本信息
                patient_data = self._get_patient_basic_info(patient_id)
            else:
                # 如果是字典（预期格式，但当前接口不是这样）
                patient_data = result.get("patient", {})
                medical_records = result.get("medicalRecords", [])

            # 从最新的病历中提取病史信息（如果有）
            medical_history = None
            allergy_history = None
            family_history = None

            if medical_records:
                # 取最新的病历（已按visitDate降序排序）
                latest_record = medical_records[0]
                medical_history = latest_record.get("medicalHistory")
                allergy_history = latest_record.get("allergyHistory")
                family_history = latest_record.get("familyHistory")

            # 构建Patient对象
            # 注意：后端gender字段是枚举类型（male/female），需要转换
            gender_value = patient_data.get("gender")
            if isinstance(gender_value, str):
                # 如果是字符串"male"/"female"
                gender = "男" if gender_value.lower() == "male" else "女"
            else:
                # 如果是枚举对象，可能有name属性
                gender = "男" if str(gender_value).lower() == "male" else "女"

            return Patient(
                patient_id=patient_data.get("id", patient_id),
                name=patient_data.get("patientName", ""),
                age=patient_data.get("age", 0),
                gender=gender,
                phone=patient_data.get("phone", ""),
                id_number=patient_data.get("idNumber"),
                medical_history=medical_history,
                allergy_history=allergy_history,
                family_history=family_history,
            )

        except APIError as e:
            # 后端返回错误（如患者不存在）
            logger.warning(f"[PatientRepository] API错误: {e}")
            return None

        except NetworkError as e:
            # 网络错误
            logger.error(f"[PatientRepository] 网络错误: {e}")
            return None

        except Exception as e:
            # 数据解析错误等
            logger.error(f"[PatientRepository] 未知错误: {e}", exc_info=True)
            return None

    def _get_patient_basic_info(self, patient_id: str) -> dict:
        """
        从get_all_patients接口获取患者基本信息

        Args:
            patient_id: 患者UUID

        Returns:
            患者基本信息字典
        """
        try:
            patients = self.api_client.get_all_patients()
            for patient in patients:
                if patient.get("id") == patient_id:
                    return patient
            logger.warning(f"[PatientRepository] 在患者列表中未找到: {patient_id}")
            return {}
        except Exception as e:
            logger.error(f"[PatientRepository] 获取患者基本信息失败: {e}")
            return {}

    def get_by_phone(self, phone: str) -> Optional[Patient]:
        """
        根据手机号获取患者
        
        注意：当前后端API未提供此接口
        """
        logger.warning("[PatientRepository] get_by_phone未实现（后端API不支持）")
        return None
    
    def create(self, patient: Patient) -> Patient:
        """
        创建患者
        
        注意：患者创建应该由后端API的用户注册流程处理
        """
        logger.warning("[PatientRepository] create未实现（应通过后端API注册流程）")
        return patient
    
    def update(self, patient: Patient) -> Patient:
        """
        更新患者信息
        
        注意：当前后端API未提供此接口
        """
        logger.warning("[PatientRepository] update未实现（后端API不支持）")
        return patient

