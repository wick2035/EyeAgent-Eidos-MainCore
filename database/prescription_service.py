"""
处方数据服务类 + UUID支持
创建日期：2025-11-17
更新日期：2025-11-20 (UUID支持)
功能：从数据库读取处方主表和详情表数据，提供格式化的数据字典
UUID支持：兼容INT和UUID格式的ID
"""

import logging
from typing import Dict, Any, Optional, List, Union
from database.db_connection import DatabaseConnection
from .base_service import BaseServiceWithUUID, normalize_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PrescriptionService(BaseServiceWithUUID):
    """处方数据服务类 (支持UUID)"""

    def __init__(self):
        """初始化处方服务"""
        super().__init__()
        self.db = DatabaseConnection()
        logger.info("处方服务初始化完成")
    
    def get_prescription_full(self, prescription_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        获取处方完整信息（包含患者、医生、病例、药物明细）

        Args:
            prescription_id: 处方ID（支持Prescription_ID或Prescription_UUID）

        Returns:
            格式化的处方数据字典，如果未找到返回 None
        """
        try:
            prescription_id_normalized = normalize_id(prescription_id)

            # 查询处方主表信息（使用UUID JOIN）
            main_query = """
                SELECT
                    p.Prescription_ID,
                    p.Prescription_UUID,
                    p.Prescription_Number,
                    p.Prescription_Date,
                    p.Prescription_Type,
                    p.Diagnosis_Description,
                    p.Usage_Instruction,
                    p.Prescription_Status,
                    p.Total_Amount,
                    p.Notes,
                    p.Prescriber_Name,
                    p.Prescriber_Signature,
                    p.Pharmacist_Name,
                    p.Dispensed_Date,
                    pat.Patient_ID,
                    pat.Patient_UUID,
                    pat.Name as Patient_Name,
                    pat.Gender as Patient_Gender,
                    pat.Age as Patient_Age,
                    pat.Phone_Number as Patient_Phone,
                    d.Doctor_ID,
                    d.Doctor_UUID,
                    d.Name as Doctor_Name,
                    d.Title as Doctor_Title,
                    mr.Medical_Record_ID,
                    mr.Medical_Record_UUID,
                    mr.Visit_Date,
                    mr.Visit_Time,
                    mr.Department,
                    mr.Chief_Complaint,
                    mr.Diagnosis as Medical_Diagnosis
                FROM prescription p
                LEFT JOIN patient pat ON p.Patient_UUID = pat.Patient_UUID
                LEFT JOIN doctor d ON p.Doctor_UUID = d.Doctor_UUID
                LEFT JOIN medical_record mr ON p.Medical_Record_UUID = mr.Medical_Record_UUID
                WHERE p.Prescription_UUID = %s OR CAST(p.Prescription_ID AS CHAR) = %s
            """

            prescription_main = self.db.execute_one(main_query, (prescription_id_normalized, prescription_id_normalized))

            if not prescription_main:
                logger.warning(f"未找到处方ID: {prescription_id}")
                return None

            # 查询处方详情（药物明细）- 使用UUID JOIN
            detail_query = """
                SELECT
                    pd.Detail_ID,
                    pd.Detail_UUID,
                    pd.Drug_ID,
                    pd.Drug_Name,
                    pd.Drug_Specification,
                    pd.Quantity,
                    pd.Unit,
                    pd.Dosage,
                    pd.Frequency,
                    pd.Duration,
                    pd.Administration_Route,
                    pd.Unit_Price,
                    pd.Subtotal,
                    pd.Special_Instructions
                FROM prescription_detail pd
                INNER JOIN prescription p ON pd.Prescription_UUID = p.Prescription_UUID
                WHERE p.Prescription_UUID = %s OR CAST(p.Prescription_ID AS CHAR) = %s
                ORDER BY pd.Detail_ID
            """

            prescription_details = self.db.execute_query(detail_query, (prescription_id_normalized, prescription_id_normalized))

            # 格式化返回数据（包含UUID字段）
            result = {
                'prescription_info': {
                    'prescription_id': prescription_main['Prescription_ID'],
                    'prescription_uuid': prescription_main['Prescription_UUID'],
                    'prescription_number': prescription_main['Prescription_Number'],
                    'prescription_date': str(prescription_main['Prescription_Date']) if prescription_main.get('Prescription_Date') else '',
                    'prescription_type': prescription_main.get('Prescription_Type', '普通'),
                    'diagnosis': prescription_main.get('Diagnosis_Description', ''),
                    'usage_instruction': prescription_main.get('Usage_Instruction', ''),
                    'status': prescription_main.get('Prescription_Status', ''),
                    'total_amount': float(prescription_main.get('Total_Amount', 0)),
                    'notes': prescription_main.get('Notes', ''),
                    'prescriber_name': prescription_main.get('Prescriber_Name', ''),
                    'prescriber_signature': prescription_main.get('Prescriber_Signature', ''),
                    'pharmacist_name': prescription_main.get('Pharmacist_Name', ''),
                    'dispensed_date': str(prescription_main['Dispensed_Date']) if prescription_main.get('Dispensed_Date') else ''
                },
                'patient_info': {
                    'patient_id': prescription_main.get('Patient_ID', ''),
                    'patient_uuid': prescription_main.get('Patient_UUID', ''),
                    'name': prescription_main.get('Patient_Name', ''),
                    'gender': prescription_main.get('Patient_Gender', ''),
                    'age': prescription_main.get('Patient_Age', ''),
                    'phone': prescription_main.get('Patient_Phone', '')
                },
                'doctor_info': {
                    'doctor_id': prescription_main.get('Doctor_ID', ''),
                    'doctor_uuid': prescription_main.get('Doctor_UUID', ''),
                    'name': prescription_main.get('Doctor_Name', ''),
                    'title': prescription_main.get('Doctor_Title', '')
                },
                'medical_record_info': {
                    'medical_record_id': prescription_main.get('Medical_Record_ID', ''),
                    'medical_record_uuid': prescription_main.get('Medical_Record_UUID', ''),
                    'visit_date': str(prescription_main['Visit_Date']) if prescription_main.get('Visit_Date') else '',
                    'visit_time': str(prescription_main['Visit_Time']) if prescription_main.get('Visit_Time') else '',
                    'department': prescription_main.get('Department', '眼科'),
                    'chief_complaint': prescription_main.get('Chief_Complaint', ''),
                    'diagnosis': prescription_main.get('Medical_Diagnosis', '')
                },
                'drug_details': []
            }
            
            # 添加药物明细（包含UUID）
            for idx, detail in enumerate(prescription_details, 1):
                drug_item = {
                    'index': idx,
                    'detail_id': detail.get('Detail_ID', ''),
                    'detail_uuid': detail.get('Detail_UUID', ''),
                    'drug_id': detail.get('Drug_ID', ''),
                    'drug_name': detail.get('Drug_Name', ''),
                    'specification': detail.get('Drug_Specification', ''),
                    'quantity': detail.get('Quantity', 0),
                    'unit': detail.get('Unit', ''),
                    'dosage': detail.get('Dosage', ''),
                    'frequency': detail.get('Frequency', ''),
                    'duration': detail.get('Duration', ''),
                    'route': detail.get('Administration_Route', ''),
                    'unit_price': float(detail.get('Unit_Price', 0)),
                    'subtotal': float(detail.get('Subtotal', 0)),
                    'special_instructions': detail.get('Special_Instructions', '')
                }
                result['drug_details'].append(drug_item)

            logger.info(f"成功获取处方完整信息: Prescription_ID={prescription_id}, 药物数量={len(prescription_details)}")
            return result

        except Exception as e:
            logger.error(f"查询处方完整信息失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_prescriptions_by_patient(self, patient_id: Union[str, int], limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取患者的所有处方列表（摘要信息）

        Args:
            patient_id: 患者ID（支持Patient_ID或Patient_UUID）
            limit: 返回记录数限制

        Returns:
            处方摘要列表
        """
        try:
            patient_id_normalized = normalize_id(patient_id)
            query = """
                SELECT
                    p.Prescription_ID,
                    p.Prescription_UUID,
                    p.Prescription_Number,
                    p.Prescription_Date,
                    p.Prescription_Type,
                    p.Diagnosis_Description,
                    p.Prescription_Status,
                    p.Total_Amount,
                    p.Prescriber_Name,
                    d.Doctor_UUID,
                    d.Name as Doctor_Name,
                    d.Title as Doctor_Title,
                    pat.Patient_UUID
                FROM prescription p
                LEFT JOIN doctor d ON p.Doctor_UUID = d.Doctor_UUID
                INNER JOIN patient pat ON p.Patient_UUID = pat.Patient_UUID
                WHERE pat.Patient_UUID = %s OR CAST(pat.Patient_ID AS CHAR) = %s
                ORDER BY p.Prescription_Date DESC
                LIMIT %s
            """

            results = self.db.execute_query(query, (patient_id_normalized, patient_id_normalized, limit))

            prescriptions = []
            for row in results:
                prescriptions.append({
                    'prescription_id': row['Prescription_ID'],
                    'prescription_uuid': row['Prescription_UUID'],
                    'prescription_number': row['Prescription_Number'],
                    'prescription_date': str(row['Prescription_Date']) if row.get('Prescription_Date') else '',
                    'prescription_type': row.get('Prescription_Type', ''),
                    'diagnosis': row.get('Diagnosis_Description', ''),
                    'status': row.get('Prescription_Status', ''),
                    'total_amount': float(row.get('Total_Amount', 0)),
                    'prescriber_name': row.get('Prescriber_Name', ''),
                    'doctor_uuid': row.get('Doctor_UUID', ''),
                    'doctor_name': row.get('Doctor_Name', ''),
                    'doctor_title': row.get('Doctor_Title', '')
                })

            logger.info(f"查询患者处方列表成功: Patient_ID={patient_id}, 数量={len(prescriptions)}")
            return prescriptions

        except Exception as e:
            logger.error(f"查询患者处方列表失败: {e}")
            return []
    
    def get_prescriptions_by_phone(self, phone_number: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        通过手机号获取患者的所有处方列表

        Args:
            phone_number: 患者手机号
            limit: 返回记录数限制

        Returns:
            处方摘要列表
        """
        try:
            # 先获取患者UUID
            patient_query = "SELECT Patient_UUID FROM patient WHERE Phone_Number = %s"
            patient_result = self.db.execute_one(patient_query, (phone_number,))

            if not patient_result:
                logger.warning(f"未找到手机号对应的患者: {phone_number}")
                return []

            patient_uuid = patient_result['Patient_UUID']
            return self.get_prescriptions_by_patient(patient_uuid, limit)

        except Exception as e:
            logger.error(f"通过手机号查询处方列表失败: {e}")
            return []
    
    def get_prescription_detail(self, prescription_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        获取单个处方的详情（仅药物明细）

        Args:
            prescription_id: 处方ID（支持Prescription_ID或Prescription_UUID）

        Returns:
            处方详情字典
        """
        try:
            prescription_id_normalized = normalize_id(prescription_id)
            query = """
                SELECT
                    pd.Detail_ID,
                    pd.Detail_UUID,
                    pd.Drug_ID,
                    pd.Drug_Name,
                    pd.Drug_Specification,
                    pd.Quantity,
                    pd.Unit,
                    pd.Dosage,
                    pd.Frequency,
                    pd.Duration,
                    pd.Administration_Route,
                    pd.Unit_Price,
                    pd.Subtotal,
                    pd.Special_Instructions,
                    p.Prescription_UUID
                FROM prescription_detail pd
                INNER JOIN prescription p ON pd.Prescription_UUID = p.Prescription_UUID
                WHERE p.Prescription_UUID = %s OR CAST(p.Prescription_ID AS CHAR) = %s
                ORDER BY pd.Detail_ID
            """

            details = self.db.execute_query(query, (prescription_id_normalized, prescription_id_normalized))

            if not details:
                logger.warning(f"未找到处方详情: Prescription_ID={prescription_id}")
                return None

            result = {
                'prescription_id': prescription_id,
                'prescription_uuid': details[0].get('Prescription_UUID', '') if details else '',
                'drug_count': len(details),
                'details': []
            }

            for detail in details:
                result['details'].append({
                    'detail_id': detail.get('Detail_ID', ''),
                    'detail_uuid': detail.get('Detail_UUID', ''),
                    'drug_id': detail.get('Drug_ID', ''),
                    'drug_name': detail.get('Drug_Name', ''),
                    'specification': detail.get('Drug_Specification', ''),
                    'quantity': detail.get('Quantity', 0),
                    'unit': detail.get('Unit', ''),
                    'dosage': detail.get('Dosage', ''),
                    'frequency': detail.get('Frequency', ''),
                    'duration': detail.get('Duration', ''),
                    'route': detail.get('Administration_Route', ''),
                    'unit_price': float(detail.get('Unit_Price', 0)),
                    'subtotal': float(detail.get('Subtotal', 0)),
                    'special_instructions': detail.get('Special_Instructions', '')
                })

            logger.info(f"查询处方详情成功: Prescription_ID={prescription_id}, 药物数量={len(details)}")
            return result

        except Exception as e:
            logger.error(f"查询处方详情失败: {e}")
            return None
    
    def close(self):
        """关闭数据库连接"""
        try:
            if hasattr(self, 'db'):
                self.db.close()
                logger.info("处方服务数据库连接已关闭")
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")


# 使用示例
if __name__ == "__main__":
    # 创建服务实例
    service = PrescriptionService()
    
    # 测试获取处方完整信息
    prescription_data = service.get_prescription_full(prescription_id=1)
    if prescription_data:
        print("\n处方完整信息:")
        print(f"处方编号: {prescription_data['prescription_info']['prescription_number']}")
        print(f"患者姓名: {prescription_data['patient_info']['name']}")
        print(f"药物数量: {len(prescription_data['drug_details'])}")
    
    # 测试获取患者处方列表
    prescriptions = service.get_prescriptions_by_patient(patient_id=1)
    print(f"\n患者处方列表: {len(prescriptions)} 条")
    
    # 关闭连接
    service.close()




