"""
用户历史信息查询服务
从数据库中查询用户的基本信息、历史病例和历史预约记录
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from .db_connection import DatabaseConnection

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserHistoryService:
    """用户历史信息查询服务类"""
    
    def __init__(self):
        """初始化用户历史信息服务"""
        self.db = DatabaseConnection()
    
    def __del__(self):
        """析构时关闭数据库连接"""
        self.db.close()
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        根据用户ID查询用户基本信息（保留方法兼容性，但建议使用 get_user_by_phone）
        
        Args:
            user_id: 患者ID（Patient_ID）
            
        Returns:
            用户基本信息字典，如果未找到返回 None
        """
        try:
            query = """
                SELECT * FROM patient 
                WHERE Patient_ID = %s 
                ORDER BY Visit_Date DESC 
                LIMIT 1
            """
            result = self.db.execute_one(query, (user_id,))
            
            if result:
                logger.info(f"成功查询到用户信息: ID={user_id}, 姓名={result.get('Name')}")
            else:
                logger.warning(f"未找到用户ID: {user_id}")
            
            return result
        except Exception as e:
            logger.error(f"查询用户信息失败: {e}")
            return None
    
    def get_user_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        根据手机号查询用户基本信息（最近一次就诊记录）
        
        Args:
            phone_number: 手机号
            
        Returns:
            用户基本信息字典，如果未找到返回 None
        """
        try:
            query = """
                SELECT * FROM patient 
                WHERE Phone_Number = %s 
                ORDER BY Visit_Date DESC 
                LIMIT 1
            """
            result = self.db.execute_one(query, (phone_number,))
            
            if result:
                logger.info(f"成功查询到用户信息: 手机号={phone_number}, 姓名={result.get('Name')}")
            else:
                logger.warning(f"未找到手机号: {phone_number}")
            
            return result
        except Exception as e:
            logger.error(f"查询用户信息失败: {e}")
            return None
    
    def get_user_medical_records(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询用户的历史病例记录（通过Patient_ID）
        
        Args:
            user_id: 患者ID
            limit: 返回记录的最大数量（默认10条）
            
        Returns:
            历史病例记录列表
        """
        try:
            query = """
                SELECT 
                    Visit_Date,
                    Visit_Card_Number,
                    Chief_Complaint,
                    Diagnosis,
                    Medical_History,
                    Allergy_History,
                    Family_History,
                    Department
                FROM patient 
                WHERE Patient_ID = %s 
                ORDER BY Visit_Date DESC 
                LIMIT %s
            """
            results = self.db.execute_query(query, (user_id, limit))
            
            logger.info(f"查询到 {len(results)} 条历史病例记录 (用户ID: {user_id})")
            return results
        except Exception as e:
            logger.error(f"查询历史病例失败: {e}")
            return []
    
    def get_user_medical_records_by_phone(self, phone_number: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询用户的所有历史病例记录（通过手机号）
        
        Args:
            phone_number: 手机号
            limit: 返回记录的最大数量（默认10条）
            
        Returns:
            历史病例记录列表（该用户的所有病例）
        """
        try:
            query = """
                SELECT 
                    Visit_Date,
                    Visit_Card_Number,
                    Chief_Complaint,
                    Diagnosis,
                    Medical_History,
                    Allergy_History,
                    Family_History,
                    Department
                FROM patient 
                WHERE Phone_Number = %s 
                ORDER BY Visit_Date DESC 
                LIMIT %s
            """
            results = self.db.execute_query(query, (phone_number, limit))
            
            logger.info(f"查询到 {len(results)} 条历史病例记录 (手机号: {phone_number})")
            return results
        except Exception as e:
            logger.error(f"查询历史病例失败: {e}")
            return []
    
    def get_user_appointments(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询用户的所有预约记录（含医生信息）
        
        Args:
            user_id: 患者ID
            limit: 返回记录的最大数量（默认10条）
            
        Returns:
            所有预约记录列表
        """
        try:
            query = """
                SELECT 
                    a.Appointment_ID,
                    a.Appointment_Time,
                    a.Appointment_Category,
                    a.Severity_Level,
                    a.Description,
                    a.Appointment_Status,
                    d.Name as Doctor_Name,
                    d.Title as Doctor_Title,
                    d.Specialty as Doctor_Specialty,
                    d.Hospital_Area as Doctor_Hospital_Area
                FROM appointment a
                LEFT JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
                WHERE a.Patient_ID = %s
                ORDER BY a.Appointment_Time DESC
                LIMIT %s
            """
            results = self.db.execute_query(query, (user_id, limit))
            
            logger.info(f"查询到 {len(results)} 条预约记录 (用户ID: {user_id})")
            return results
        except Exception as e:
            logger.error(f"查询预约记录失败: {e}")
            return []
    
    def get_historical_appointments(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询用户的历史预约记录（今天之前的预约）
        
        Args:
            user_id: 患者ID
            limit: 返回记录的最大数量（默认10条）
            
        Returns:
            历史预约记录列表（今天之前的）
        """
        try:
            query = """
                SELECT 
                    a.Appointment_ID,
                    a.Appointment_Time,
                    a.Appointment_Category,
                    a.Severity_Level,
                    a.Description,
                    a.Appointment_Status,
                    d.Name as Doctor_Name,
                    d.Title as Doctor_Title,
                    d.Specialty as Doctor_Specialty,
                    d.Hospital_Area as Doctor_Hospital_Area
                FROM appointment a
                LEFT JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
                WHERE a.Patient_ID = %s AND DATE(a.Appointment_Time) < CURDATE()
                ORDER BY a.Appointment_Time DESC
                LIMIT %s
            """
            results = self.db.execute_query(query, (user_id, limit))
            
            logger.info(f"查询到 {len(results)} 条历史预约记录（今天之前） (用户ID: {user_id})")
            return results
        except Exception as e:
            logger.error(f"查询历史预约失败: {e}")
            return []
    
    def get_historical_appointments_by_phone(self, phone_number: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询用户的所有历史预约记录（通过手机号，今天之前的预约）
        
        Args:
            phone_number: 手机号
            limit: 返回记录的最大数量（默认10条）
            
        Returns:
            历史预约记录列表（今天之前的，包含该用户的所有病例的预约）
        """
        try:
            query = """
                SELECT 
                    a.Appointment_ID,
                    a.Appointment_Time,
                    a.Appointment_Category,
                    a.Severity_Level,
                    a.Description,
                    a.Appointment_Status,
                    d.Name as Doctor_Name,
                    d.Title as Doctor_Title,
                    d.Specialty as Doctor_Specialty,
                    d.Hospital_Area as Doctor_Hospital_Area
                FROM appointment a
                LEFT JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
                INNER JOIN patient p ON a.Patient_ID = p.Patient_ID
                WHERE p.Phone_Number = %s AND DATE(a.Appointment_Time) < CURDATE()
                ORDER BY a.Appointment_Time DESC
                LIMIT %s
            """
            results = self.db.execute_query(query, (phone_number, limit))
            
            logger.info(f"查询到 {len(results)} 条历史预约记录（今天之前） (手机号: {phone_number})")
            return results
        except Exception as e:
            logger.error(f"查询历史预约失败: {e}")
            return []
    
    def get_current_future_appointments(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询用户的当前和未来预约记录（今天及以后的预约）
        
        Args:
            user_id: 患者ID
            limit: 返回记录的最大数量（默认10条）
            
        Returns:
            当前和未来预约记录列表
        """
        try:
            query = """
                SELECT 
                    a.Appointment_ID,
                    a.Appointment_Time,
                    a.Appointment_Category,
                    a.Severity_Level,
                    a.Description,
                    a.Appointment_Status,
                    d.Name as Doctor_Name,
                    d.Title as Doctor_Title,
                    d.Specialty as Doctor_Specialty,
                    d.Hospital_Area as Doctor_Hospital_Area
                FROM appointment a
                LEFT JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
                WHERE a.Patient_ID = %s AND DATE(a.Appointment_Time) >= CURDATE()
                ORDER BY a.Appointment_Time ASC
                LIMIT %s
            """
            results = self.db.execute_query(query, (user_id, limit))
            
            logger.info(f"查询到 {len(results)} 条当前/未来预约记录（今天及以后） (用户ID: {user_id})")
            return results
        except Exception as e:
            logger.error(f"查询当前/未来预约失败: {e}")
            return []
    
    def get_current_future_appointments_by_phone(self, phone_number: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查询用户的所有当前和未来预约记录（通过手机号，今天及以后的预约）
        
        Args:
            phone_number: 手机号
            limit: 返回记录的最大数量（默认10条）
            
        Returns:
            当前和未来预约记录列表（包含该用户的所有病例的预约）
        """
        try:
            query = """
                SELECT 
                    a.Appointment_ID,
                    a.Appointment_Time,
                    a.Appointment_Category,
                    a.Severity_Level,
                    a.Description,
                    a.Appointment_Status,
                    d.Name as Doctor_Name,
                    d.Title as Doctor_Title,
                    d.Specialty as Doctor_Specialty,
                    d.Hospital_Area as Doctor_Hospital_Area
                FROM appointment a
                LEFT JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
                INNER JOIN patient p ON a.Patient_ID = p.Patient_ID
                WHERE p.Phone_Number = %s AND DATE(a.Appointment_Time) >= CURDATE()
                ORDER BY a.Appointment_Time ASC
                LIMIT %s
            """
            results = self.db.execute_query(query, (phone_number, limit))
            
            logger.info(f"查询到 {len(results)} 条当前/未来预约记录（今天及以后） (手机号: {phone_number})")
            return results
        except Exception as e:
            logger.error(f"查询当前/未来预约失败: {e}")
            return []
    
    def get_user_complete_info(self, user_id: int) -> Dict[str, Any]:
        """
        综合查询用户的完整历史信息（通过Patient_ID，保留兼容性）
        
        Args:
            user_id: 患者ID
            
        Returns:
            包含用户基本信息、历史病例和历史预约的完整字典
        """
        logger.info(f"开始查询用户完整历史信息: ID={user_id}")
        
        # 查询基本信息
        basic_info = self.get_user_by_id(user_id)
        
        # 查询历史病例
        medical_records = self.get_user_medical_records(user_id)
        
        # 查询历史预约（只包含今天之前的预约）
        historical_appointments = self.get_historical_appointments(user_id)
        
        # 查询当前和未来预约
        current_future_appointments = self.get_current_future_appointments(user_id)
        
        complete_info = {
            "user_id": user_id,
            "basic_info": basic_info,
            "medical_records": medical_records,
            "historical_appointments": historical_appointments,  # 历史预约（今天之前）
            "current_future_appointments": current_future_appointments,  # 当前和未来预约（今天及以后）
            "has_history": bool(basic_info or medical_records or historical_appointments)
        }
        
        logger.info(f"用户完整信息查询完成: 基本信息={'有' if basic_info else '无'}, "
                   f"历史病例={len(medical_records)}条, 历史预约={len(historical_appointments)}条, "
                   f"当前/未来预约={len(current_future_appointments)}条")
        
        return complete_info
    
    def get_user_complete_info_by_phone(self, phone_number: str) -> Dict[str, Any]:
        """
        综合查询用户的完整历史信息（通过手机号，推荐使用）
        
        【重要】通过手机号查询，可以获取该用户所有病例的历史信息
        
        Args:
            phone_number: 手机号
            
        Returns:
            包含用户基本信息、所有历史病例和所有历史预约的完整字典
        """
        logger.info(f"开始查询用户完整历史信息: 手机号={phone_number}")
        
        # 查询基本信息（最近一次就诊）
        basic_info = self.get_user_by_phone(phone_number)
        
        # 查询所有历史病例
        medical_records = self.get_user_medical_records_by_phone(phone_number)
        
        # 查询所有历史预约（只包含今天之前的预约）
        historical_appointments = self.get_historical_appointments_by_phone(phone_number)
        
        # 查询所有当前和未来预约
        current_future_appointments = self.get_current_future_appointments_by_phone(phone_number)
        
        complete_info = {
            "phone_number": phone_number,
            "basic_info": basic_info,
            "medical_records": medical_records,
            "historical_appointments": historical_appointments,  # 历史预约（今天之前）
            "current_future_appointments": current_future_appointments,  # 当前和未来预约（今天及以后）
            "has_history": bool(basic_info or medical_records or historical_appointments)
        }
        
        logger.info(f"用户完整信息查询完成: 基本信息={'有' if basic_info else '无'}, "
                   f"历史病例={len(medical_records)}条, 历史预约={len(historical_appointments)}条, "
                   f"当前/未来预约={len(current_future_appointments)}条")
        
        return complete_info
    
    def format_user_history_text(self, user_id: int) -> str:
        """
        将用户历史信息格式化为易读的文本（只包含历史数据）
        
        Args:
            user_id: 患者ID
            
        Returns:
            格式化的用户历史信息文本
        """
        complete_info = self.get_user_complete_info(user_id)
        
        if not complete_info["has_history"]:
            return "该用户为新用户，暂无历史就诊记录。"
        
        text_parts = []
        
        # 格式化基本信息
        basic_info = complete_info["basic_info"]
        if basic_info:
            text_parts.append("【用户基本信息】")
            text_parts.append(f"姓名: {basic_info.get('Name', '未知')}")
            text_parts.append(f"性别: {basic_info.get('Gender', '未知')}")
            text_parts.append(f"年龄: {basic_info.get('Age', '未知')}")
            text_parts.append(f"联系方式: {basic_info.get('Phone_Number', '未提供')}")
            text_parts.append(f"就诊卡号: {basic_info.get('Visit_Card_Number', '未知')}")
            
            # 显示既往病史、过敏史、家族史
            if basic_info.get('Medical_History'):
                text_parts.append(f"既往病史: {basic_info.get('Medical_History')}")
            if basic_info.get('Allergy_History'):
                text_parts.append(f"过敏史: {basic_info.get('Allergy_History')}")
            if basic_info.get('Family_History'):
                text_parts.append(f"家族史: {basic_info.get('Family_History')}")
            text_parts.append("")
        
        # 格式化历史病例
        medical_records = complete_info["medical_records"]
        if medical_records and len(medical_records) > 0:
            text_parts.append("【历史就诊记录】")
            for i, record in enumerate(medical_records[:5], 1):  # 最多显示5条
                visit_date = record.get('Visit_Date', '未知日期')
                if isinstance(visit_date, datetime):
                    visit_date = visit_date.strftime('%Y-%m-%d')
                text_parts.append(f"{i}. 就诊日期: {visit_date}")
                text_parts.append(f"   科室: {record.get('Department', '未知')}")
                text_parts.append(f"   主诉: {record.get('Chief_Complaint', '无')}")
                if record.get('Diagnosis'):
                    text_parts.append(f"   诊断: {record.get('Diagnosis')}")
                text_parts.append("")
        
        # 格式化历史预约（只显示今天之前的预约）
        historical_appointments = complete_info.get("historical_appointments", [])
        if historical_appointments and len(historical_appointments) > 0:
            text_parts.append("【历史预约记录】（今天之前的预约）")
            for i, appt in enumerate(historical_appointments[:5], 1):  # 最多显示5条
                appt_time = appt.get('Appointment_Time', '未知时间')
                if isinstance(appt_time, datetime):
                    appt_time = appt_time.strftime('%Y-%m-%d %H:%M')
                text_parts.append(f"{i}. 预约时间: {appt_time}")
                text_parts.append(f"   医生: {appt.get('Doctor_Name', '未知')} ({appt.get('Doctor_Title', '')})")
                text_parts.append(f"   状态: {appt.get('Appointment_Status', '未知')}")
                if appt.get('Description'):
                    text_parts.append(f"   描述: {appt.get('Description')}")
                text_parts.append("")
        
        # 如果有当前/未来预约，也显示出来（可选）
        current_future_appointments = complete_info.get("current_future_appointments", [])
        if current_future_appointments and len(current_future_appointments) > 0:
            text_parts.append("【当前/未来预约】（今天及以后的预约）")
            for i, appt in enumerate(current_future_appointments[:3], 1):  # 最多显示3条
                appt_time = appt.get('Appointment_Time', '未知时间')
                if isinstance(appt_time, datetime):
                    appt_time = appt_time.strftime('%Y-%m-%d %H:%M')
                text_parts.append(f"{i}. 预约时间: {appt_time}")
                text_parts.append(f"   医生: {appt.get('Doctor_Name', '未知')} ({appt.get('Doctor_Title', '')})")
                text_parts.append(f"   状态: {appt.get('Appointment_Status', '未知')}")
                if appt.get('Description'):
                    text_parts.append(f"   描述: {appt.get('Description')}")
                text_parts.append("")
        
        return "\n".join(text_parts)
    
    def format_user_history_text_by_phone(self, phone_number: str) -> str:
        """
        将用户历史信息格式化为易读的文本（通过手机号，推荐使用）
        
        Args:
            phone_number: 手机号
            
        Returns:
            格式化的用户历史信息文本
        """
        complete_info = self.get_user_complete_info_by_phone(phone_number)
        
        if not complete_info["has_history"]:
            return "该用户为新用户，暂无历史就诊记录。"
        
        text_parts = []
        
        # 格式化基本信息
        basic_info = complete_info["basic_info"]
        if basic_info:
            text_parts.append("【用户基本信息】")
            text_parts.append(f"姓名: {basic_info.get('Name', '未知')}")
            text_parts.append(f"性别: {basic_info.get('Gender', '未知')}")
            text_parts.append(f"年龄: {basic_info.get('Age', '未知')}")
            text_parts.append(f"联系方式: {basic_info.get('Phone_Number', '未提供')}")
            text_parts.append(f"最近就诊卡号: {basic_info.get('Visit_Card_Number', '未知')}")
            
            # 显示既往病史、过敏史、家族史
            if basic_info.get('Medical_History'):
                text_parts.append(f"既往病史: {basic_info.get('Medical_History')}")
            if basic_info.get('Allergy_History'):
                text_parts.append(f"过敏史: {basic_info.get('Allergy_History')}")
            if basic_info.get('Family_History'):
                text_parts.append(f"家族史: {basic_info.get('Family_History')}")
            text_parts.append("")
        
        # 格式化历史病例（显示所有病例）
        medical_records = complete_info["medical_records"]
        if medical_records and len(medical_records) > 0:
            text_parts.append("【历史就诊记录】")
            for i, record in enumerate(medical_records[:5], 1):  # 最多显示5条
                visit_date = record.get('Visit_Date', '未知日期')
                if isinstance(visit_date, datetime):
                    visit_date = visit_date.strftime('%Y-%m-%d')
                text_parts.append(f"{i}. 就诊日期: {visit_date}")
                text_parts.append(f"   科室: {record.get('Department', '未知')}")
                text_parts.append(f"   主诉: {record.get('Chief_Complaint', '无')}")
                if record.get('Diagnosis'):
                    text_parts.append(f"   诊断: {record.get('Diagnosis')}")
                text_parts.append("")
        
        # 格式化历史预约（只显示今天之前的预约）
        historical_appointments = complete_info.get("historical_appointments", [])
        if historical_appointments and len(historical_appointments) > 0:
            text_parts.append("【历史预约记录】（今天之前的预约）")
            for i, appt in enumerate(historical_appointments[:5], 1):  # 最多显示5条
                appt_time = appt.get('Appointment_Time', '未知时间')
                if isinstance(appt_time, datetime):
                    appt_time = appt_time.strftime('%Y-%m-%d %H:%M')
                text_parts.append(f"{i}. 预约时间: {appt_time}")
                text_parts.append(f"   医生: {appt.get('Doctor_Name', '未知')} ({appt.get('Doctor_Title', '')})")
                text_parts.append(f"   状态: {appt.get('Appointment_Status', '未知')}")
                if appt.get('Description'):
                    text_parts.append(f"   描述: {appt.get('Description')}")
                text_parts.append("")
        
        # 如果有当前/未来预约，也显示出来（可选）
        current_future_appointments = complete_info.get("current_future_appointments", [])
        if current_future_appointments and len(current_future_appointments) > 0:
            text_parts.append("【当前/未来预约】（今天及以后的预约）")
            for i, appt in enumerate(current_future_appointments[:3], 1):  # 最多显示3条
                appt_time = appt.get('Appointment_Time', '未知时间')
                if isinstance(appt_time, datetime):
                    appt_time = appt_time.strftime('%Y-%m-%d %H:%M')
                text_parts.append(f"{i}. 预约时间: {appt_time}")
                text_parts.append(f"   医生: {appt.get('Doctor_Name', '未知')} ({appt.get('Doctor_Title', '')})")
                text_parts.append(f"   状态: {appt.get('Appointment_Status', '未知')}")
                if appt.get('Description'):
                    text_parts.append(f"   描述: {appt.get('Description')}")
                text_parts.append("")
        
        return "\n".join(text_parts)
    
    def close(self):
        """关闭数据库连接"""
        self.db.close()


# ==================== 使用说明 ====================
# 
# 【重要变更】2025-11-16
# 
# 由于修改了病例创建逻辑（每次预约创建新病例），推荐使用以下方法：
# 
# 1. 通过手机号查询用户历史（推荐）：
#    service = UserHistoryService()
#    history = service.get_user_complete_info_by_phone("13800138000")
#    text = service.format_user_history_text_by_phone("13800138000")
# 
# 2. 通过Patient_ID查询（仅查询单个病例，不推荐）：
#    history = service.get_user_complete_info(patient_id)
#    text = service.format_user_history_text(patient_id)
# 
# 【架构说明】
# - patient 表：每条记录 = 一次就诊/一个病例
# - 同一个人多次就诊 = 多条 patient 记录
# - 通过 Phone_Number 关联同一个人的所有病例
# - appointment 表：通过 Patient_ID 外键关联具体的病例
#

