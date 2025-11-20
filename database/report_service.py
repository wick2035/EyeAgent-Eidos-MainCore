"""
病例报告数据服务 + UUID支持
创建日期：2025-11-17
更新日期：2025-11-20 (UUID支持)
功能：提供报告数据查询和更新功能
UUID支持：兼容INT和UUID格式的ID
"""

import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

from .db_connection import DatabaseConnection
from .base_service import BaseServiceWithUUID, normalize_id

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReportService(BaseServiceWithUUID):
    """病例报告数据服务类 (支持UUID)"""

    def __init__(self):
        """初始化报告服务"""
        super().__init__()
        self.db = DatabaseConnection()
    
    def __del__(self):
        """析构时关闭数据库连接"""
        self.db.close()
    
    # ==================== 报告ID生成 ====================
    
    def _generate_report_id(self) -> str:
        """
        生成唯一的报告编号
        格式：FILE-{year}-{sequence}
        
        Returns:
            报告编号字符串
        """
        year = datetime.now().year
        
        # 查询当年最大的报告编号 (仅查询未删除的记录)
        query = """
            SELECT Report_ID
            FROM medical_record
            WHERE Report_ID LIKE %s AND Deleted = 0
            ORDER BY Report_ID DESC
            LIMIT 1
        """
        result = self.db.execute_one(query, (f"FILE-{year}-%",))
        
        if result and result['Report_ID']:
            # 提取序号并加1
            last_id = result['Report_ID']
            try:
                last_number = int(last_id.split('-')[-1])
                new_number = last_number + 1
            except (ValueError, IndexError):
                new_number = 1
        else:
            new_number = 1
        
        return f"FILE-{year}-{new_number:05d}"
    
    # ==================== 病例完整信息查询 ====================
    
    def get_medical_record_full(self, medical_record_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        获取病例的完整信息（包含所有字段）

        Args:
            medical_record_id: 病例ID（支持Medical_Record_ID或Medical_Record_UUID）

        Returns:
            完整病例信息字典，如果未找到返回 None
        """
        try:
            medical_record_id_normalized = normalize_id(medical_record_id)
            query = """
                SELECT
                    mr.*,
                    p.Patient_UUID,
                    p.Name as Patient_Name,
                    p.Gender as Patient_Gender,
                    p.Age as Patient_Age,
                    p.Phone_Number as Patient_Phone
                FROM medical_record mr
                LEFT JOIN patient p ON mr.Patient_UUID = p.Patient_UUID AND p.Deleted = 0
                WHERE (mr.Medical_Record_UUID = %s OR CAST(mr.Medical_Record_ID AS CHAR) = %s)
                  AND mr.Deleted = 0
            """
            result = self.db.execute_one(query, (medical_record_id_normalized, medical_record_id_normalized))

            if result:
                logger.info(f"成功查询到病例完整信息: Medical_Record_ID={medical_record_id}")
            else:
                logger.warning(f"未找到病例ID: {medical_record_id}")

            return result
        except Exception as e:
            logger.error(f"查询病例完整信息失败: {e}")
            return None
    
    # ==================== 报告列表查询 ====================
    
    def get_all_reports_by_patient(self, patient_id: Union[str, int], limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取用户的所有病例报告列表

        Args:
            patient_id: 用户ID（支持Patient_ID或Patient_UUID）
            limit: 返回记录的最大数量（默认50条）

        Returns:
            病例报告列表
        """
        try:
            patient_id_normalized = normalize_id(patient_id)
            query = """
                SELECT
                    mr.Medical_Record_ID,
                    mr.Medical_Record_UUID,
                    mr.Visit_Card_Number,
                    mr.Report_ID,
                    mr.Visit_Date,
                    mr.Visit_Time,
                    mr.Department,
                    mr.Chief_Complaint,
                    mr.Diagnosis,
                    mr.AI_Diagnosis,
                    mr.Physician_Name,
                    mr.Doctor_Signature,
                    mr.Print_Time,
                    mr.Created_At,
                    p.Patient_UUID
                FROM medical_record mr
                INNER JOIN patient p ON mr.Patient_UUID = p.Patient_UUID AND p.Deleted = 0
                WHERE (p.Patient_UUID = %s OR CAST(p.Patient_ID AS CHAR) = %s)
                  AND mr.Deleted = 0
                ORDER BY mr.Visit_Date DESC, mr.Visit_Time DESC
                LIMIT %s
            """
            results = self.db.execute_query(query, (patient_id_normalized, patient_id_normalized, limit))

            logger.info(f"查询到 {len(results)} 条病例报告 (Patient_ID: {patient_id})")
            return results
        except Exception as e:
            logger.error(f"查询病例报告列表失败: {e}")
            return []
    
    def get_all_reports_by_phone(self, phone_number: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取用户的所有病例报告列表（通过手机号）

        Args:
            phone_number: 手机号
            limit: 返回记录的最大数量（默认50条）

        Returns:
            病例报告列表
        """
        try:
            query = """
                SELECT
                    mr.Medical_Record_ID,
                    mr.Medical_Record_UUID,
                    mr.Visit_Card_Number,
                    mr.Report_ID,
                    mr.Visit_Date,
                    mr.Visit_Time,
                    mr.Department,
                    mr.Chief_Complaint,
                    mr.Diagnosis,
                    mr.AI_Diagnosis,
                    mr.Physician_Name,
                    mr.Doctor_Signature,
                    mr.Print_Time,
                    mr.Created_At,
                    p.Patient_ID,
                    p.Patient_UUID
                FROM medical_record mr
                INNER JOIN patient p ON mr.Patient_UUID = p.Patient_UUID AND p.Deleted = 0
                WHERE p.Phone_Number = %s
                  AND mr.Deleted = 0
                ORDER BY mr.Visit_Date DESC, mr.Visit_Time DESC
                LIMIT %s
            """
            results = self.db.execute_query(query, (phone_number, limit))

            logger.info(f"查询到 {len(results)} 条病例报告 (手机号: {phone_number})")
            return results
        except Exception as e:
            logger.error(f"查询病例报告列表失败: {e}")
            return []
    
    # ==================== 用于模板填充的数据获取 ====================
    
    def get_report_data_for_template(self, medical_record_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        获取用于填充报告模板的数据（格式化为JSON Schema格式）

        Args:
            medical_record_id: 病例ID（支持Medical_Record_ID或Medical_Record_UUID）

        Returns:
            符合报告模板要求的数据字典
        """
        try:
            record = self.get_medical_record_full(medical_record_id)

            if not record:
                return None

            # 格式化为模板所需的JSON结构
            template_data = {
                "patient_info": {
                    "name": record.get('Patient_Name', ''),
                    "gender": record.get('Patient_Gender', ''),
                    "age": record.get('Patient_Age', ''),
                    "patient_id": str(record.get('Patient_ID', '')),
                    "patient_uuid": record.get('Patient_UUID', ''),
                    "report_id": record.get('Report_ID', ''),
                    "medical_record_uuid": record.get('Medical_Record_UUID', ''),
                    "visit_time": self._format_datetime(record.get('Visit_Time') or record.get('Visit_Date')),
                    "department": record.get('Department', '眼科')
                },
                "medical_history": {
                    "chief_complaint": record.get('Chief_Complaint', ''),
                    "present_illness_history": record.get('Present_Illness', ''),
                    "past_history": record.get('Medical_History', '无'),
                    "allergy_history": record.get('Allergy_History', '无'),
                    "family_history": record.get('Family_History', '无')
                },
                "examinations": {
                    "special_exams": record.get('Special_Exams', ''),
                    "auxiliary_exams": record.get('Auxiliary_Exams', '')
                },
                "diagnosis": {
                    "ai_diagnosis": record.get('AI_Diagnosis', ''),
                    "initial_diagnosis": record.get('Diagnosis', '')
                },
                "treatment": {
                    "treatment_plan": record.get('Treatment_Plan', '')
                },
                "meta": {
                    "doctor_signature": record.get('Doctor_Signature', ''),
                    "print_time": self._format_datetime(record.get('Print_Time'))
                }
            }
            
            logger.info(f"成功获取病例报告模板数据: Medical_Record_ID={medical_record_id}")
            return template_data
            
        except Exception as e:
            logger.error(f"获取报告模板数据失败: {e}")
            return None
    
    def _format_datetime(self, dt) -> str:
        """格式化日期时间"""
        if not dt:
            return ''
        if isinstance(dt, datetime):
            return dt.strftime('%Y-%m-%d %H:%M')
        if isinstance(dt, str):
            return dt
        return str(dt)
    
    # ==================== 报告字段更新 ====================
    
    def update_report_fields(self, medical_record_id: Union[str, int], data: Dict[str, Any]) -> bool:
        """
        更新病例的报告相关字段

        Args:
            medical_record_id: 病例ID（支持Medical_Record_ID或Medical_Record_UUID）
            data: 要更新的数据字典，支持的键：
                  - report_id: 报告编号
                  - visit_time: 就诊时间
                  - special_exams: 专项检查
                  - auxiliary_exams: 辅助检查
                  - ai_diagnosis: AI诊断
                  - doctor_signature: 医生签名
                  - print_time: 打印时间

        Returns:
            是否更新成功
        """
        try:
            medical_record_id_normalized = normalize_id(medical_record_id)

            # 构建更新语句
            update_fields = []
            params = []

            field_mapping = {
                'report_id': 'Report_ID',
                'visit_time': 'Visit_Time',
                'special_exams': 'Special_Exams',
                'auxiliary_exams': 'Auxiliary_Exams',
                'ai_diagnosis': 'AI_Diagnosis',
                'doctor_signature': 'Doctor_Signature',
                'print_time': 'Print_Time'
            }

            for key, db_field in field_mapping.items():
                if key in data:
                    update_fields.append(f"{db_field} = %s")
                    params.append(data[key])

            if not update_fields:
                logger.warning("没有需要更新的字段")
                return False

            # 添加Version字段用于乐观锁
            update_fields.append("Version = Version + 1")
            params.extend([medical_record_id_normalized, medical_record_id_normalized])

            query = f"""
                UPDATE medical_record
                SET {', '.join(update_fields)}
                WHERE (Medical_Record_UUID = %s OR CAST(Medical_Record_ID AS CHAR) = %s)
                  AND Deleted = 0
            """

            affected_rows = self.db.execute_update(query, tuple(params))

            if affected_rows > 0:
                logger.info(f"成功更新病例报告字段: Medical_Record_ID={medical_record_id}, 字段={list(data.keys())}")
                return True
            else:
                logger.warning(f"未找到要更新的病例: Medical_Record_ID={medical_record_id}")
                return False

        except Exception as e:
            logger.error(f"更新报告字段失败: {e}")
            return False
    
    def assign_report_id(self, medical_record_id: Union[str, int]) -> Optional[str]:
        """
        为病例分配报告编号

        Args:
            medical_record_id: 病例ID（支持Medical_Record_ID或Medical_Record_UUID）

        Returns:
            生成的报告编号，失败返回 None
        """
        try:
            # 检查是否已有报告编号
            record = self.get_medical_record_full(medical_record_id)
            if not record:
                logger.error(f"病例不存在: Medical_Record_ID={medical_record_id}")
                return None

            if record.get('Report_ID'):
                logger.info(f"病例已有报告编号: {record['Report_ID']}")
                return record['Report_ID']

            # 生成新的报告编号
            report_id = self._generate_report_id()

            # 更新到数据库
            success = self.update_report_fields(medical_record_id, {'report_id': report_id})

            if success:
                logger.info(f"成功分配报告编号: Medical_Record_ID={medical_record_id}, Report_ID={report_id}")
                return report_id
            else:
                return None

        except Exception as e:
            logger.error(f"分配报告编号失败: {e}")
            return None

    def mark_report_printed(self, medical_record_id: Union[str, int]) -> bool:
        """
        标记报告已打印（设置打印时间）

        Args:
            medical_record_id: 病例ID（支持Medical_Record_ID或Medical_Record_UUID）

        Returns:
            是否标记成功
        """
        try:
            print_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return self.update_report_fields(medical_record_id, {'print_time': print_time})
        except Exception as e:
            logger.error(f"标记报告打印失败: {e}")
            return False
    
    # ==================== 历史分析辅助方法 ====================
    
    def get_records_for_analysis(self, patient_id: Union[str, int], limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取用于历史分析的病例记录（包含详细信息）

        Args:
            patient_id: 用户ID（支持Patient_ID或Patient_UUID）
            limit: 返回记录的最大数量

        Returns:
            病例记录列表
        """
        try:
            patient_id_normalized = normalize_id(patient_id)
            query = """
                SELECT
                    mr.Medical_Record_ID,
                    mr.Medical_Record_UUID,
                    mr.Visit_Date,
                    mr.Visit_Time,
                    mr.Department,
                    mr.Chief_Complaint,
                    mr.Present_Illness,
                    mr.Medical_History,
                    mr.Allergy_History,
                    mr.Family_History,
                    mr.Eye_Exam_Results,
                    mr.Special_Exams,
                    mr.Diagnosis,
                    mr.AI_Diagnosis,
                    mr.Treatment_Plan,
                    mr.Medication,
                    mr.Created_At,
                    p.Patient_UUID
                FROM medical_record mr
                INNER JOIN patient p ON mr.Patient_UUID = p.Patient_UUID AND p.Deleted = 0
                WHERE (p.Patient_UUID = %s OR CAST(p.Patient_ID AS CHAR) = %s)
                  AND mr.Deleted = 0
                ORDER BY mr.Visit_Date DESC, mr.Visit_Time DESC
                LIMIT %s
            """
            results = self.db.execute_query(query, (patient_id_normalized, patient_id_normalized, limit))

            logger.info(f"查询到 {len(results)} 条病例用于分析 (Patient_ID: {patient_id})")
            return results
        except Exception as e:
            logger.error(f"查询分析数据失败: {e}")
            return []

    def compare_records(self, record_ids: List[Union[str, int]]) -> List[Dict[str, Any]]:
        """
        获取多条病例记录用于对比

        Args:
            record_ids: 病例ID列表（支持Medical_Record_ID或Medical_Record_UUID）

        Returns:
            病例记录列表
        """
        try:
            if not record_ids:
                return []

            # Normalize all IDs
            normalized_ids = [normalize_id(rid) for rid in record_ids]

            # Build query with UUID support (仅查询未删除的记录)
            placeholders = ', '.join(['%s'] * len(normalized_ids) * 2)
            query = f"""
                SELECT
                    Medical_Record_ID,
                    Medical_Record_UUID,
                    Visit_Date,
                    Visit_Time,
                    Chief_Complaint,
                    Present_Illness,
                    Diagnosis,
                    AI_Diagnosis,
                    Treatment_Plan,
                    Eye_Exam_Results,
                    Special_Exams
                FROM medical_record
                WHERE (Medical_Record_UUID IN ({', '.join(['%s'] * len(normalized_ids))})
                   OR CAST(Medical_Record_ID AS CHAR) IN ({', '.join(['%s'] * len(normalized_ids))}))
                  AND Deleted = 0
                ORDER BY Visit_Date DESC, Visit_Time DESC
            """
            params = normalized_ids + normalized_ids
            results = self.db.execute_query(query, tuple(params))

            logger.info(f"查询到 {len(results)} 条病例用于对比")
            return results
        except Exception as e:
            logger.error(f"查询对比数据失败: {e}")
            return []
    
    def close(self):
        """关闭数据库连接"""
        self.db.close()


# ==================== 使用说明 ====================
# 
# 【创建服务实例】
# service = ReportService()
# 
# 【获取完整病例信息】
# record = service.get_medical_record_full(medical_record_id=1)
# 
# 【获取用户所有报告】
# reports = service.get_all_reports_by_patient(patient_id=1)
# 
# 【获取用于模板的数据】
# template_data = service.get_report_data_for_template(medical_record_id=1)
# 
# 【分配报告编号】
# report_id = service.assign_report_id(medical_record_id=1)
# 
# 【更新报告字段】
# service.update_report_fields(medical_record_id=1, {
#     'ai_diagnosis': '双眼近视',
#     'doctor_signature': '张医生'
# })
# 
# 【标记报告已打印】
# service.mark_report_printed(medical_record_id=1)
#

