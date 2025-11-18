"""
用户历史信息查询服务 V2 - 适配新的三层架构
从数据库中查询用户的基本信息、历史病例和历史预约记录

新架构：Patient(用户) → Medical_Record(病例) → Appointment(预约)
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from .db_connection import DatabaseConnection

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserHistoryServiceV2:
    """用户历史信息查询服务类 V2"""
    
    def __init__(self):
        """初始化用户历史信息服务"""
        self.db = DatabaseConnection()
    
    def __del__(self):
        """析构时关闭数据库连接"""
        self.db.close()
    
    # ==================== 用户基本信息查询 ====================
    
    def get_user_by_id(self, patient_id: int) -> Optional[Dict[str, Any]]:
        """
        根据Patient_ID查询用户基本信息
        
        Args:
            patient_id: 用户ID（Patient_ID）
            
        Returns:
            用户基本信息字典，如果未找到返回 None
        """
        try:
            query = "SELECT * FROM patient WHERE Patient_ID = %s"
            result = self.db.execute_one(query, (patient_id,))
            
            if result:
                logger.info(f"成功查询到用户信息: ID={patient_id}, 姓名={result.get('Name')}")
            else:
                logger.warning(f"未找到用户ID: {patient_id}")
            
            return result
        except Exception as e:
            logger.error(f"查询用户信息失败: {e}")
            return None
    
    def get_user_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        根据手机号查询用户基本信息
        
        Args:
            phone_number: 手机号
            
        Returns:
            用户基本信息字典，如果未找到返回 None
        """
        try:
            query = "SELECT * FROM patient WHERE Phone_Number = %s"
            result = self.db.execute_one(query, (phone_number,))
            
            if result:
                logger.info(f"成功查询到用户信息: 手机号={phone_number}, 姓名={result.get('Name')}")
            else:
                logger.warning(f"未找到手机号: {phone_number}")
            
            return result
        except Exception as e:
            logger.error(f"查询用户信息失败: {e}")
            return None
    
    # ==================== 病例记录查询 ====================
    
    def get_medical_records_by_patient_id(self, patient_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询用户的所有病例记录
        
        Args:
            patient_id: 用户ID（Patient_ID）
            limit: 返回记录的最大数量（默认10条）
            
        Returns:
            病例记录列表
        """
        try:
            query = """
                SELECT 
                    Medical_Record_ID,
                    Visit_Card_Number,
                    Visit_Date,
                    Department,
                    Chief_Complaint,
                    Diagnosis,
                    Medical_History,
                    Allergy_History,
                    Family_History,
                    Treatment_Plan
                FROM medical_record 
                WHERE Patient_ID = %s 
                ORDER BY Visit_Date DESC 
                LIMIT %s
            """
            results = self.db.execute_query(query, (patient_id, limit))
            
            logger.info(f"查询到 {len(results)} 条病例记录 (Patient_ID: {patient_id})")
            return results
        except Exception as e:
            logger.error(f"查询病例记录失败: {e}")
            return []
    
    def get_medical_records_by_phone(self, phone_number: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询用户的所有病例记录（通过手机号）
        
        Args:
            phone_number: 手机号
            limit: 返回记录的最大数量（默认10条）
            
        Returns:
            病例记录列表
        """
        try:
            query = """
                SELECT 
                    mr.Medical_Record_ID,
                    mr.Visit_Card_Number,
                    mr.Visit_Date,
                    mr.Department,
                    mr.Chief_Complaint,
                    mr.Diagnosis,
                    mr.Medical_History,
                    mr.Allergy_History,
                    mr.Family_History,
                    mr.Treatment_Plan
                FROM medical_record mr
                INNER JOIN patient p ON mr.Patient_ID = p.Patient_ID
                WHERE p.Phone_Number = %s 
                ORDER BY mr.Visit_Date DESC 
                LIMIT %s
            """
            results = self.db.execute_query(query, (phone_number, limit))
            
            logger.info(f"查询到 {len(results)} 条病例记录 (手机号: {phone_number})")
            return results
        except Exception as e:
            logger.error(f"查询病例记录失败: {e}")
            return []
    
    # ==================== 预约记录查询 ====================
    
    def get_appointments_by_patient_id(self, patient_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询用户的所有预约记录
        
        Args:
            patient_id: 用户ID（Patient_ID）
            limit: 返回记录的最大数量（默认10条）
            
        Returns:
            预约记录列表
        """
        try:
            query = """
                SELECT 
                    a.Appointment_ID,
                    a.Medical_Record_ID,
                    a.Appointment_Time,
                    a.Appointment_Category,
                    a.Severity_Level,
                    a.Description,
                    a.Appointment_Status,
                    d.Name as Doctor_Name,
                    d.Title as Doctor_Title,
                    d.Specialty as Doctor_Specialty,
                    mr.Chief_Complaint as Medical_Record_Chief_Complaint,
                    mr.Visit_Date as Medical_Record_Visit_Date
                FROM appointment a
                LEFT JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
                LEFT JOIN medical_record mr ON a.Medical_Record_ID = mr.Medical_Record_ID
                WHERE a.Patient_ID = %s
                ORDER BY a.Appointment_Time DESC
                LIMIT %s
            """
            results = self.db.execute_query(query, (patient_id, limit))
            
            logger.info(f"查询到 {len(results)} 条预约记录 (Patient_ID: {patient_id})")
            return results
        except Exception as e:
            logger.error(f"查询预约记录失败: {e}")
            return []
    
    def get_historical_appointments(self, patient_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询用户的历史预约记录（今天之前的预约）
        
        Args:
            patient_id: 用户ID
            limit: 返回记录的最大数量（默认10条）
            
        Returns:
            历史预约记录列表
        """
        try:
            query = """
                SELECT 
                    a.Appointment_ID,
                    a.Medical_Record_ID,
                    a.Appointment_Time,
                    a.Appointment_Category,
                    a.Severity_Level,
                    a.Description,
                    a.Appointment_Status,
                    d.Name as Doctor_Name,
                    d.Title as Doctor_Title,
                    d.Specialty as Doctor_Specialty,
                    mr.Chief_Complaint as Medical_Record_Chief_Complaint
                FROM appointment a
                LEFT JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
                LEFT JOIN medical_record mr ON a.Medical_Record_ID = mr.Medical_Record_ID
                WHERE a.Patient_ID = %s AND DATE(a.Appointment_Time) < CURDATE()
                ORDER BY a.Appointment_Time DESC
                LIMIT %s
            """
            results = self.db.execute_query(query, (patient_id, limit))
            
            logger.info(f"查询到 {len(results)} 条历史预约记录（今天之前） (Patient_ID: {patient_id})")
            return results
        except Exception as e:
            logger.error(f"查询历史预约失败: {e}")
            return []
    
    def get_current_future_appointments(self, patient_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询用户的当前和未来预约记录（今天及以后的预约）
        
        Args:
            patient_id: 用户ID
            limit: 返回记录的最大数量（默认10条）
            
        Returns:
            当前和未来预约记录列表
        """
        try:
            query = """
                SELECT 
                    a.Appointment_ID,
                    a.Medical_Record_ID,
                    a.Appointment_Time,
                    a.Appointment_Category,
                    a.Severity_Level,
                    a.Description,
                    a.Appointment_Status,
                    d.Name as Doctor_Name,
                    d.Title as Doctor_Title,
                    d.Specialty as Doctor_Specialty,
                    mr.Chief_Complaint as Medical_Record_Chief_Complaint
                FROM appointment a
                LEFT JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
                LEFT JOIN medical_record mr ON a.Medical_Record_ID = mr.Medical_Record_ID
                WHERE a.Patient_ID = %s AND DATE(a.Appointment_Time) >= CURDATE()
                ORDER BY a.Appointment_Time ASC
                LIMIT %s
            """
            results = self.db.execute_query(query, (patient_id, limit))
            
            logger.info(f"查询到 {len(results)} 条当前/未来预约记录（今天及以后） (Patient_ID: {patient_id})")
            return results
        except Exception as e:
            logger.error(f"查询当前/未来预约失败: {e}")
            return []
    
    # ==================== 综合查询方法 ====================
    
    def get_user_complete_info(self, patient_id: int) -> Dict[str, Any]:
        """
        综合查询用户的完整历史信息
        
        Args:
            patient_id: 用户ID（Patient_ID）
            
        Returns:
            包含用户基本信息、病例记录和预约记录的完整字典
        """
        logger.info(f"开始查询用户完整历史信息: Patient_ID={patient_id}")
        
        # 查询基本信息
        basic_info = self.get_user_by_id(patient_id)
        
        # 查询病例记录
        medical_records = self.get_medical_records_by_patient_id(patient_id)
        
        # 查询历史预约
        historical_appointments = self.get_historical_appointments(patient_id)
        
        # 查询当前和未来预约
        current_future_appointments = self.get_current_future_appointments(patient_id)
        
        complete_info = {
            "patient_id": patient_id,
            "basic_info": basic_info,
            "medical_records": medical_records,
            "historical_appointments": historical_appointments,
            "current_future_appointments": current_future_appointments,
            "has_history": bool(basic_info or medical_records or historical_appointments)
        }
        
        logger.info(f"用户完整信息查询完成: 基本信息={'有' if basic_info else '无'}, "
                   f"病例={len(medical_records)}条, 历史预约={len(historical_appointments)}条, "
                   f"当前/未来预约={len(current_future_appointments)}条")
        
        return complete_info
    
    def get_user_complete_info_by_phone(self, phone_number: str) -> Dict[str, Any]:
        """
        综合查询用户的完整历史信息（通过手机号）
        
        Args:
            phone_number: 手机号
            
        Returns:
            包含用户基本信息、病例记录和预约记录的完整字典
        """
        logger.info(f"开始查询用户完整历史信息: 手机号={phone_number}")
        
        # 先查询用户基本信息，获取Patient_ID
        basic_info = self.get_user_by_phone(phone_number)
        
        if not basic_info:
            return {
                "phone_number": phone_number,
                "basic_info": None,
                "medical_records": [],
                "historical_appointments": [],
                "current_future_appointments": [],
                "has_history": False
            }
        
        patient_id = basic_info['Patient_ID']
        
        # 查询病例记录
        medical_records = self.get_medical_records_by_patient_id(patient_id)
        
        # 查询历史预约
        historical_appointments = self.get_historical_appointments(patient_id)
        
        # 查询当前和未来预约
        current_future_appointments = self.get_current_future_appointments(patient_id)
        
        complete_info = {
            "phone_number": phone_number,
            "patient_id": patient_id,
            "basic_info": basic_info,
            "medical_records": medical_records,
            "historical_appointments": historical_appointments,
            "current_future_appointments": current_future_appointments,
            "has_history": bool(basic_info)  # 修复：基于patient表是否有记录判断，而非就诊记录
        }
        
        logger.info(f"用户完整信息查询完成: Patient_ID={patient_id}, "
                   f"病例={len(medical_records)}条, 历史预约={len(historical_appointments)}条, "
                   f"当前/未来预约={len(current_future_appointments)}条")
        
        return complete_info
    
    # ==================== 格式化输出方法 ====================
    
    def format_user_history_text(self, patient_id: int) -> str:
        """
        将用户历史信息格式化为易读的文本
        
        Args:
            patient_id: 用户ID
            
        Returns:
            格式化的用户历史信息文本
        """
        complete_info = self.get_user_complete_info(patient_id)
        
        if not complete_info["has_history"]:
            return "该用户为新用户，暂无历史就诊记录。"
        
        text_parts = []
        
        # 格式化基本信息
        basic_info = complete_info["basic_info"]
        if basic_info:
            text_parts.append("【用户基本信息】")
            text_parts.append(f"用户ID: {basic_info.get('Patient_ID')}")
            text_parts.append(f"姓名: {basic_info.get('Name', '未知')}")
            text_parts.append(f"性别: {basic_info.get('Gender', '未知')}")
            text_parts.append(f"年龄: {basic_info.get('Age', '未知')}")
            text_parts.append(f"联系方式: {basic_info.get('Phone_Number', '未提供')}")
            text_parts.append("")
        
        # 格式化病例记录
        medical_records = complete_info["medical_records"]
        if medical_records and len(medical_records) > 0:
            text_parts.append("【历史就诊记录】")
            for i, record in enumerate(medical_records[:5], 1):
                visit_date = record.get('Visit_Date', '未知日期')
                if isinstance(visit_date, datetime):
                    visit_date = visit_date.strftime('%Y-%m-%d')
                text_parts.append(f"{i}. 就诊日期: {visit_date}")
                text_parts.append(f"   就诊卡号: {record.get('Visit_Card_Number', '未知')}")
                text_parts.append(f"   科室: {record.get('Department', '未知')}")
                text_parts.append(f"   主诉: {record.get('Chief_Complaint', '无')}")
                if record.get('Diagnosis'):
                    text_parts.append(f"   诊断: {record.get('Diagnosis')}")
                text_parts.append("")
        
        # 格式化历史预约
        historical_appointments = complete_info.get("historical_appointments", [])
        if historical_appointments and len(historical_appointments) > 0:
            text_parts.append("【历史预约记录】（今天之前的预约）")
            for i, appt in enumerate(historical_appointments[:5], 1):
                appt_time = appt.get('Appointment_Time', '未知时间')
                if isinstance(appt_time, datetime):
                    appt_time = appt_time.strftime('%Y-%m-%d %H:%M')
                text_parts.append(f"{i}. 预约时间: {appt_time}")
                text_parts.append(f"   医生: {appt.get('Doctor_Name', '未知')} ({appt.get('Doctor_Title', '')})")
                text_parts.append(f"   状态: {appt.get('Appointment_Status', '未知')}")
                if appt.get('Medical_Record_Chief_Complaint'):
                    text_parts.append(f"   病情: {appt.get('Medical_Record_Chief_Complaint')}")
                text_parts.append("")
        
        # 格式化当前/未来预约
        current_future_appointments = complete_info.get("current_future_appointments", [])
        if current_future_appointments and len(current_future_appointments) > 0:
            text_parts.append("【当前/未来预约】（今天及以后的预约）")
            for i, appt in enumerate(current_future_appointments[:3], 1):
                appt_time = appt.get('Appointment_Time', '未知时间')
                if isinstance(appt_time, datetime):
                    appt_time = appt_time.strftime('%Y-%m-%d %H:%M')
                text_parts.append(f"{i}. 预约时间: {appt_time}")
                text_parts.append(f"   医生: {appt.get('Doctor_Name', '未知')} ({appt.get('Doctor_Title', '')})")
                text_parts.append(f"   状态: {appt.get('Appointment_Status', '未知')}")
                if appt.get('Medical_Record_Chief_Complaint'):
                    text_parts.append(f"   病情: {appt.get('Medical_Record_Chief_Complaint')}")
                text_parts.append("")
        
        return "\n".join(text_parts)
    
    def format_user_history_text_by_phone(self, phone_number: str) -> str:
        """
        将用户历史信息格式化为易读的文本（通过手机号）
        
        Args:
            phone_number: 手机号
            
        Returns:
            格式化的用户历史信息文本
        """
        complete_info = self.get_user_complete_info_by_phone(phone_number)

        # 修复：区分"无patient记录"vs"无就诊记录"
        if not complete_info["has_history"]:
            return "该用户为新用户，数据库中无patient记录。"

        # 使用Patient_ID调用标准格式化方法（会显示基础信息，即使无就诊记录）
        return self.format_user_history_text(complete_info["patient_id"])
    
    def close(self):
        """关闭数据库连接"""
        self.db.close()


# ==================== 使用说明 ====================
# 
# 【新架构】2025-11-16
# 
# 1. 通过Patient_ID查询：
#    service = UserHistoryServiceV2()
#    history = service.get_user_complete_info(patient_id)
#    text = service.format_user_history_text(patient_id)
# 
# 2. 通过手机号查询：
#    history = service.get_user_complete_info_by_phone("13900000001")
#    text = service.format_user_history_text_by_phone("13900000001")
# 
# 【架构说明】
# - patient 表：一条记录 = 一个人（用户基本信息）
# - medical_record 表：一条记录 = 一次就诊（病例信息）
# - appointment 表：一条记录 = 一次预约（预约信息）
# 
# 关系：Patient(1) → Medical_Record(N) → Appointment(N)
#

