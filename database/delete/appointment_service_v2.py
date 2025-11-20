"""
预约服务核心模块 V2 - 适配新的三层架构
处理用户创建、病例创建、医生查询和预约操作

新架构：Patient(用户) → Medical_Record(病例) → Appointment(预约)
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import logging

from .db_connection import DatabaseConnection

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AppointmentServiceV2:
    """预约服务类 V2 - 适配新的三层架构"""
    
    def __init__(self):
        """初始化预约服务"""
        self.db = DatabaseConnection()
    
    def __del__(self):
        """析构时关闭数据库连接"""
        self.db.close()
    
    # ==================== 用户管理相关方法 ====================
    
    def create_or_get_patient(self, patient_info: Dict[str, Any]) -> int:
        """
        创建或获取用户（一个人只有一个Patient_ID）
        
        Args:
            patient_info: 用户基本信息 {'name': '', 'phone': '', 'gender': '', 'age': ''}
            
        Returns:
            Patient_ID (用户ID)
        """
        phone = patient_info.get('contact') or patient_info.get('phone', '')
        
        if not phone:
            raise ValueError("手机号不能为空")
        
        # 检查用户是否已存在
        query = "SELECT Patient_ID FROM patient WHERE Phone_Number = %s"
        existing_user = self.db.execute_one(query, (phone,))
        
        if existing_user:
            patient_id = existing_user['Patient_ID']
            logger.info(f"用户已存在，Patient_ID: {patient_id}")
            return patient_id
        
        # 创建新用户
        insert_query = """
            INSERT INTO patient (
                Name, Gender, Age, Phone_Number
            ) VALUES (%s, %s, %s, %s)
        """
        
        params = (
            patient_info.get('name', '未提供'),
            patient_info.get('gender', '未知'),
            patient_info.get('age', 0),
            phone
        )
        
        patient_id = self.db.execute_insert(insert_query, params)
        logger.info(f"创建新用户，Patient_ID: {patient_id}")
        
        return patient_id
    
    # ==================== 病例管理相关方法 ====================
    
    def _generate_visit_card_number(self) -> str:
        """
        生成就诊卡号
        格式: YYYY-XXXXXX (年份 + 6位序列号)
        
        Returns:
            就诊卡号字符串
        """
        year = datetime.now().year
        # 查询当年最大的序列号
        query = """
            SELECT Visit_Card_Number FROM medical_record 
            WHERE Visit_Card_Number LIKE %s 
            ORDER BY Visit_Card_Number DESC 
            LIMIT 1
        """
        result = self.db.execute_one(query, (f"{year}-%",))
        
        if result and result['Visit_Card_Number']:
            # 提取序列号并加1
            last_number = int(result['Visit_Card_Number'].split('-')[1])
            new_number = last_number + 1
        else:
            # 从1开始
            new_number = 1
        
        return f"{year}-{new_number:06d}"
    
    def create_medical_record(self, patient_id: int, patient_data: Dict[str, Any]) -> int:
        """
        创建病例记录（每次就诊创建新病例）
        
        Args:
            patient_id: 用户ID（Patient_ID）
            patient_data: 从智能体获取的患者数据字典
            
        Returns:
            Medical_Record_ID (病例ID)
        """
        # 生成就诊卡号
        visit_card_number = self._generate_visit_card_number()
        
        # 获取当前日期作为就诊日期
        visit_date = datetime.now().strftime("%Y-%m-%d")
        
        # 准备插入数据
        insert_query = """
            INSERT INTO medical_record (
                Patient_ID, Visit_Card_Number, Visit_Date, Department,
                Chief_Complaint, Present_Illness, Medical_History,
                Allergy_History, Family_History, Medication_History
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        params = (
            patient_id,
            visit_card_number,
            visit_date,
            patient_data.get('appointment', {}).get('department', '眼科'),
            patient_data.get('chief_complaint', ''),
            patient_data.get('present_illness', ''),
            patient_data.get('medical_history', ''),
            patient_data.get('allergy_history', ''),
            patient_data.get('family_history', ''),
            patient_data.get('medication_history', '')
        )
        
        medical_record_id = self.db.execute_insert(insert_query, params)
        logger.info(f"创建病例记录，Medical_Record_ID: {medical_record_id}, 就诊卡号: {visit_card_number}")
        
        return medical_record_id
    
    # ==================== 医生管理相关方法 ====================
    
    def _parse_time_expression(self, time_expr: str) -> Optional[datetime]:
        """解析自然语言时间表达式"""
        time_expr = time_expr.strip()
        today = datetime.now()
        
        # 处理"明天"、"后天"等相对时间
        if '明天' in time_expr or '明日' in time_expr:
            target_date = today + timedelta(days=1)
        elif '后天' in time_expr:
            target_date = today + timedelta(days=2)
        elif '今天' in time_expr or '今日' in time_expr:
            target_date = today
        elif '下周' in time_expr:
            target_date = today + timedelta(days=7)
        else:
            # 尝试解析具体日期
            date_pattern = r'(\d{1,2})[月/-](\d{1,2})'
            match = re.search(date_pattern, time_expr)
            if match:
                month = int(match.group(1))
                day = int(match.group(2))
                year = today.year
                if month < today.month:
                    year += 1
                try:
                    target_date = datetime(year, month, day)
                except ValueError:
                    return None
            else:
                return None
        
        # 处理时间段
        if '上午' in time_expr or '早上' in time_expr:
            target_date = target_date.replace(hour=9, minute=0)
        elif '下午' in time_expr:
            target_date = target_date.replace(hour=14, minute=0)
        elif '晚上' in time_expr:
            target_date = target_date.replace(hour=18, minute=0)
        else:
            target_date = target_date.replace(hour=9, minute=0)
        
        return target_date
    
    def _parse_available_time(self, available_time_str: str) -> Optional[Tuple[datetime, datetime]]:
        """解析医生的空闲时间字符串"""
        if not available_time_str or available_time_str.strip() == '':
            return None
        
        try:
            parts = available_time_str.split(',')
            if len(parts) < 3:
                return None
            
            date_str = parts[0].strip()
            time_range = parts[1].strip()
            is_available = parts[2].strip()
            
            if is_available not in ['是', '可', 'True', 'true', '1']:
                return None
            
            times = time_range.split('-')
            if len(times) != 2:
                return None
            
            start_time_str = f"{date_str} {times[0].strip()}"
            end_time_str = f"{date_str} {times[1].strip()}"
            
            start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
            end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M")
            
            return (start_time, end_time)
        except Exception as e:
            logger.warning(f"解析空闲时间失败: {available_time_str}, 错误: {e}")
            return None
    
    def find_available_doctors(self, department: str, preferred_time_expr: str = None,
                               doctor_preference: str = None, urgency: str = "普通") -> List[Dict]:
        """查找可用的医生"""
        query = """
            SELECT * FROM doctor
            WHERE Specialty = %s OR Hospital_Area LIKE %s
            ORDER BY Title DESC
        """
        doctors = self.db.execute_query(query, (department, f"%{department}%"))

        if not doctors:
            logger.warning(f"未找到 {department} 的医生")
            return []

        # 解析患者期望时间
        preferred_time = None
        if preferred_time_expr:
            preferred_time = self._parse_time_expression(preferred_time_expr)
            logger.info(f"解析患者期望时间: {preferred_time_expr} -> {preferred_time}")

        # 获取当前时间用于过滤过期日期
        now = datetime.now()
        logger.info(f"当前时间: {now}, 将过滤早于此时间的预约")

        # 筛选可用医生
        available_doctors = []
        filtered_count = 0  # 记录被过滤的医生数量

        for doctor in doctors:
            available_time_str = doctor.get('Available_Time', '')
            time_range = self._parse_available_time(available_time_str)

            if time_range:
                start_time, end_time = time_range

                # 过滤过期时间:跳过早于当前时间的预约
                if end_time < now:
                    filtered_count += 1
                    logger.debug(f"医生 {doctor.get('Name')} 的时间已过期: {start_time} - {end_time}")
                    continue

                # 检查时间是否匹配
                if self._is_time_match(preferred_time, start_time, end_time):
                    doctor['parsed_start_time'] = start_time
                    doctor['parsed_end_time'] = end_time
                    doctor['match_score'] = self._calculate_match_score(doctor, doctor_preference, urgency)
                    available_doctors.append(doctor)

        # 按匹配分数排序
        available_doctors.sort(key=lambda x: x['match_score'], reverse=True)

        logger.info(f"找到 {len(available_doctors)} 位可用医生 (过滤了 {filtered_count} 位时间已过期的医生)")
        return available_doctors
    
    def _is_time_match(self, preferred_time: Optional[datetime], 
                       available_start: datetime, available_end: datetime) -> bool:
        """判断期望时间是否在医生空闲时间内"""
        if preferred_time is None:
            return True
        
        if preferred_time.date() != available_start.date():
            return False
        
        return available_start <= preferred_time <= available_end
    
    def _calculate_match_score(self, doctor: Dict, doctor_preference: str, urgency: str) -> int:
        """计算医生匹配分数"""
        score = 0
        
        # 职称加分
        if doctor.get('Title'):
            if '主任' in doctor['Title']:
                score += 3
            elif '副主任' in doctor['Title']:
                score += 2
            elif '主治' in doctor['Title']:
                score += 1
        
        # 医生偏好加分
        if doctor_preference and doctor_preference in doctor.get('Title', ''):
            score += 5
        
        # 紧急程度处理
        if urgency in ['紧急', '急'] and '主任' in doctor.get('Title', ''):
            score += 2
        
        return score
    
    # ==================== 预约管理相关方法 ====================
    
    def _determine_severity_level(self, urgency: str, chief_complaint: str) -> str:
        """确定病情严重等级"""
        urgent_keywords = ['出血', '剧痛', '失明', '突然', '急性', '严重']
        
        if urgency in ['紧急', '急']:
            return '严重'
        
        if any(keyword in chief_complaint for keyword in urgent_keywords):
            return '严重'
        
        return '中等'
    
    def create_appointment(self, medical_record_id: int, patient_id: int,
                          doctor_id: int, patient_data: Dict[str, Any],
                          appointment_time: datetime) -> int:
        """
        创建预约记录
        
        Args:
            medical_record_id: 病例ID
            patient_id: 用户ID
            doctor_id: 医生ID
            patient_data: 患者数据字典
            appointment_time: 预约时间
            
        Returns:
            Appointment_ID (预约ID)
        """
        patient_info = patient_data.get('patient_info', {})
        appointment_info = patient_data.get('appointment', {})
        
        severity_level = self._determine_severity_level(
            appointment_info.get('urgency', '普通'),
            patient_data.get('chief_complaint', '')
        )
        
        insert_query = """
            INSERT INTO appointment (
                Medical_Record_ID, Patient_ID, Doctor_ID, Patient_Name,
                Appointment_Time, Appointment_Category, Severity_Level,
                Description, Appointment_Status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        params = (
            medical_record_id,
            patient_id,
            doctor_id,
            patient_info.get('name', '未提供'),
            appointment_time.strftime("%Y-%m-%d %H:%M"),
            appointment_info.get('urgency', '普通'),
            severity_level,
            patient_data.get('chief_complaint', ''),
            '已确认'
        )
        
        appointment_id = self.db.execute_insert(insert_query, params)
        logger.info(f"创建预约记录，Appointment_ID: {appointment_id}")
        
        return appointment_id
    
    # ==================== 完整流程方法 ====================
    
    def process_appointment(self, patient_json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理完整的预约流程（新架构版本）
        
        流程：
        1. 创建或获取用户（Patient）
        2. 创建病例记录（Medical_Record）
        3. 查找可用医生（Doctor）
        4. 创建预约记录（Appointment）
        
        Args:
            patient_json_data: 智能体输出的患者数据字典
            
        Returns:
            结果字典
        """
        try:
            logger.info("=" * 50)
            logger.info("开始处理预约流程（新架构）")
            logger.info("=" * 50)
            
            # 步骤1: 创建或获取用户
            logger.info("步骤1: 创建/获取用户")
            patient_info = patient_json_data.get('patient_info', {})
            patient_id = self.create_or_get_patient(patient_info)
            
            # 步骤2: 创建病例记录
            logger.info("步骤2: 创建病例记录")
            medical_record_id = self.create_medical_record(patient_id, patient_json_data)
            
            # 步骤3: 查找可用医生
            logger.info("步骤3: 查找可用医生")
            appointment_info = patient_json_data.get('appointment', {})
            department = appointment_info.get('department', '眼科')
            preferred_time = appointment_info.get('preferred_time', '')
            doctor_preference = appointment_info.get('doctor_preference', '')
            urgency = appointment_info.get('urgency', '普通')
            
            available_doctors = self.find_available_doctors(
                department=department,
                preferred_time_expr=preferred_time,
                doctor_preference=doctor_preference,
                urgency=urgency
            )

            if not available_doctors:
                # 区分不同的失败原因
                all_doctors_query = "SELECT COUNT(*) as count FROM doctor WHERE Specialty = %s OR Hospital_Area LIKE %s"
                all_doctors_count = self.db.execute_one(all_doctors_query, (department, f"%{department}%"))

                if all_doctors_count and all_doctors_count['count'] == 0:
                    message = f'抱歉,系统中没有{department}的医生'
                elif preferred_time:
                    message = f'抱歉,{preferred_time}没有可用的{department}医生,请尝试其他时间段'
                else:
                    message = f'抱歉,当前没有可用的{department}医生(所有医生的预约时间可能已过期)'

                return {
                    'success': False,
                    'patient_id': patient_id,
                    'medical_record_id': medical_record_id,
                    'message': message,
                    'department': department,
                    'preferred_time': preferred_time,
                    'available_doctors': []
                }
            
            # 步骤4: 创建预约记录
            logger.info("步骤4: 创建预约记录")
            best_doctor = available_doctors[0]
            doctor_id = best_doctor['Doctor_ID']
            appointment_time = best_doctor['parsed_start_time']
            
            appointment_id = self.create_appointment(
                medical_record_id=medical_record_id,
                patient_id=patient_id,
                doctor_id=doctor_id,
                patient_data=patient_json_data,
                appointment_time=appointment_time
            )
            
            logger.info("=" * 50)
            logger.info("预约流程完成（新架构）")
            logger.info("=" * 50)
            
            return {
                'success': True,
                'patient_id': patient_id,
                'medical_record_id': medical_record_id,
                'appointment_id': appointment_id,
                'doctor_info': {
                    'doctor_id': best_doctor['Doctor_ID'],
                    'name': best_doctor['Name'],
                    'title': best_doctor['Title'],
                    'specialty': best_doctor['Specialty']
                },
                'appointment_time': appointment_time.strftime("%Y-%m-%d %H:%M"),
                'message': f'预约成功！医生: {best_doctor["Name"]}，时间: {appointment_time.strftime("%Y-%m-%d %H:%M")}',
                'available_doctors': [
                    {
                        'name': d['Name'],
                        'title': d['Title'],
                        'available_time': f"{d['parsed_start_time'].strftime('%Y-%m-%d %H:%M')}"
                    }
                    for d in available_doctors[:3]
                ]
            }
            
        except Exception as e:
            logger.error(f"预约流程出错: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'预约过程中发生错误: {str(e)}'
            }
    
    def close(self):
        """关闭数据库连接"""
        self.db.close()

