"""
预约服务核心模块
处理患者病例创建、医生空闲时间检查和预约操作
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import logging

from .db_connection import DatabaseConnection

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AppointmentService:
    """预约服务类 - 处理完整的预约流程"""
    
    def __init__(self):
        """初始化预约服务"""
        self.db = DatabaseConnection()
    
    def __del__(self):
        """析构时关闭数据库连接"""
        self.db.close()
    
    # ==================== 患者管理相关方法 ====================
    
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
            SELECT Visit_Card_Number FROM patient 
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
    
    def _check_patient_exists(self, contact: str, name: str = None) -> Optional[Dict]:
        """
        检查患者是否已存在
        
        Args:
            contact: 患者联系方式（手机号）
            name: 患者姓名（可选）
            
        Returns:
            如果存在返回患者信息字典，否则返回 None
        """
        if not contact:
            return None
        
        # 优先通过手机号查询
        query = "SELECT * FROM patient WHERE Phone_Number = %s"
        patient = self.db.execute_one(query, (contact,))
        
        if patient:
            logger.info(f"找到已存在患者: {patient['Name']} (ID: {patient['Patient_ID']})")
            return patient
        
        # 如果提供了姓名，尝试通过姓名查询
        if name:
            query = "SELECT * FROM patient WHERE Name = %s"
            patient = self.db.execute_one(query, (name,))
            if patient:
                logger.info(f"通过姓名找到已存在患者: {patient['Name']} (ID: {patient['Patient_ID']})")
                return patient
        
        return None
    
    def _calculate_age_from_birthdate(self, birthdate_str: str) -> Optional[int]:
        """
        从出生日期计算年龄
        
        Args:
            birthdate_str: 出生日期字符串
            
        Returns:
            年龄（整数），如果无法计算返回 None
        """
        try:
            birthdate = datetime.strptime(birthdate_str, "%Y-%m-%d")
            today = datetime.now()
            age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
            return age
        except:
            return None
    
    def create_patient(self, patient_data: Dict[str, Any]) -> int:
        """
        创建新患者病例
        
        Args:
            patient_data: 从一号智能体获取的患者数据字典
            
        Returns:
            新创建的患者ID
            
        Raises:
            Exception: 数据库操作失败时抛出异常
        """
        # 提取患者基本信息
        patient_info = patient_data.get('patient_info', {})
        name = patient_info.get('name', '')
        age = patient_info.get('age', '')
        gender = patient_info.get('gender', '')
        contact = patient_info.get('contact', '')
        
        # 检查患者是否已存在
        existing_patient = self._check_patient_exists(contact, name)
        if existing_patient:
            logger.info(f"患者已存在，使用现有ID: {existing_patient['Patient_ID']}")
            return existing_patient['Patient_ID']
        
        # 生成就诊卡号
        visit_card_number = self._generate_visit_card_number()
        
        # 准备插入数据
        insert_query = """
            INSERT INTO patient (
                Visit_Card_Number, Name, Gender, Age, Phone_Number,
                Chief_Complaint, Diagnosis, Medical_History,
                Allergy_History, Family_History, Department, Visit_Date
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        # 获取当前日期作为就诊日期
        visit_date = datetime.now().strftime("%Y-%m-%d")
        
        params = (
            visit_card_number,
            name or '未提供',
            gender or '未知',
            age or '0',
            contact or '',
            patient_data.get('chief_complaint', ''),
            '',  # 诊断暂时为空，由医生填写
            patient_data.get('medical_history', ''),
            patient_data.get('allergy_history', ''),
            patient_data.get('family_history', ''),
            patient_data.get('appointment', {}).get('department', '眼科'),
            visit_date
        )
        
        # 执行插入
        patient_id = self.db.execute_insert(insert_query, params)
        logger.info(f"成功创建患者病例，ID: {patient_id}, 就诊卡号: {visit_card_number}")
        
        return patient_id
    
    # ==================== 医生管理相关方法 ====================
    
    def _parse_time_expression(self, time_expr: str) -> Optional[datetime]:
        """
        解析自然语言时间表达式
        
        Args:
            time_expr: 时间表达式，如 "明天下午"、"后天上午"、"11月15日"
            
        Returns:
            datetime 对象，如果无法解析返回 None
        """
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
            # 匹配 "11月15日" 或 "2025-11-15"
            date_pattern = r'(\d{1,2})[月/-](\d{1,2})'
            match = re.search(date_pattern, time_expr)
            if match:
                month = int(match.group(1))
                day = int(match.group(2))
                year = today.year
                # 如果月份小于当前月份，可能是明年
                if month < today.month:
                    year += 1
                try:
                    target_date = datetime(year, month, day)
                except ValueError:
                    return None
            else:
                return None
        
        # 处理时间段（上午、下午、晚上）
        if '上午' in time_expr or '早上' in time_expr:
            target_date = target_date.replace(hour=9, minute=0)
        elif '下午' in time_expr:
            target_date = target_date.replace(hour=14, minute=0)
        elif '晚上' in time_expr:
            target_date = target_date.replace(hour=18, minute=0)
        else:
            # 默认上午9点
            target_date = target_date.replace(hour=9, minute=0)
        
        return target_date
    
    def _parse_available_time(self, available_time_str: str) -> Optional[Tuple[datetime, datetime]]:
        """
        解析医生的空闲时间字符串
        
        Args:
            available_time_str: 空闲时间字符串，格式如 "2025-11-14, 14:00-16:00, 是"
            
        Returns:
            (开始时间, 结束时间) 元组，如果无法解析返回 None
        """
        if not available_time_str or available_time_str.strip() == '':
            return None
        
        try:
            parts = available_time_str.split(',')
            if len(parts) < 3:
                return None
            
            date_str = parts[0].strip()
            time_range = parts[1].strip()
            is_available = parts[2].strip()
            
            # 检查是否可预约
            if is_available not in ['是', '可', 'True', 'true', '1']:
                return None
            
            # 解析日期和时间范围
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
    
    def _is_time_match(self, preferred_time: Optional[datetime], 
                       available_start: datetime, available_end: datetime) -> bool:
        """
        判断期望时间是否在医生空闲时间内
        
        Args:
            preferred_time: 患者期望时间
            available_start: 医生空闲开始时间
            available_end: 医生空闲结束时间
            
        Returns:
            是否匹配
        """
        if preferred_time is None:
            # 如果没有指定期望时间，认为任何时间都可以
            return True
        
        # 检查日期是否匹配（同一天）
        if preferred_time.date() != available_start.date():
            return False
        
        # 检查时间是否在空闲时间段内
        return available_start <= preferred_time <= available_end
    
    def find_available_doctors(self, department: str, preferred_time_expr: str = None,
                               doctor_preference: str = None, urgency: str = "普通") -> List[Dict]:
        """
        查找可用的医生
        
        Args:
            department: 就诊科室（如"眼科"）
            preferred_time_expr: 期望就诊时间表达式
            doctor_preference: 医生偏好（如"专家"、"主任"）
            urgency: 紧急程度（如"紧急"、"普通"）
            
        Returns:
            可用医生列表，按匹配度排序
        """
        # 查询该科室的所有医生
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
        
        # 筛选可用医生
        available_doctors = []
        for doctor in doctors:
            available_time_str = doctor.get('Available_Time', '')
            time_range = self._parse_available_time(available_time_str)
            
            if time_range:
                start_time, end_time = time_range
                # 检查时间是否匹配
                if self._is_time_match(preferred_time, start_time, end_time):
                    doctor['parsed_start_time'] = start_time
                    doctor['parsed_end_time'] = end_time
                    doctor['match_score'] = 0
                    
                    # 计算匹配分数
                    # 职称加分
                    if doctor.get('Title'):
                        if '主任' in doctor['Title']:
                            doctor['match_score'] += 3
                        elif '副主任' in doctor['Title']:
                            doctor['match_score'] += 2
                        elif '主治' in doctor['Title']:
                            doctor['match_score'] += 1
                    
                    # 医生偏好加分
                    if doctor_preference:
                        if doctor_preference in doctor.get('Title', ''):
                            doctor['match_score'] += 5
                    
                    # 紧急程度处理：紧急情况优先推荐高级医生
                    if urgency in ['紧急', '急']:
                        if '主任' in doctor.get('Title', ''):
                            doctor['match_score'] += 2
                    
                    available_doctors.append(doctor)
        
        # 按匹配分数排序
        available_doctors.sort(key=lambda x: x['match_score'], reverse=True)
        
        logger.info(f"找到 {len(available_doctors)} 位可用医生")
        return available_doctors
    
    # ==================== 预约管理相关方法 ====================
    
    def _determine_severity_level(self, urgency: str, chief_complaint: str) -> str:
        """
        确定病情严重等级
        
        Args:
            urgency: 紧急程度
            chief_complaint: 主诉症状
            
        Returns:
            严重等级字符串
        """
        # 紧急关键词
        urgent_keywords = ['出血', '剧痛', '失明', '突然', '急性', '严重']
        
        if urgency in ['紧急', '急']:
            return '严重'
        
        # 检查主诉中是否包含紧急关键词
        if any(keyword in chief_complaint for keyword in urgent_keywords):
            return '严重'
        
        return '中等'
    
    def create_appointment(self, patient_id: int, doctor_id: int, 
                          patient_data: Dict[str, Any], 
                          appointment_time: datetime) -> int:
        """
        创建预约记录
        
        Args:
            patient_id: 患者ID
            doctor_id: 医生ID
            patient_data: 患者数据字典
            appointment_time: 预约时间
            
        Returns:
            预约ID
            
        Raises:
            Exception: 数据库操作失败时抛出异常
        """
        patient_info = patient_data.get('patient_info', {})
        appointment_info = patient_data.get('appointment', {})
        
        # 确定严重等级
        severity_level = self._determine_severity_level(
            appointment_info.get('urgency', '普通'),
            patient_data.get('chief_complaint', '')
        )
        
        # 插入预约记录
        insert_query = """
            INSERT INTO appointment (
                Patient_ID, Doctor_ID, Patient_Name, Appointment_Time,
                Appointment_Category, Severity_Level, Description,
                Appointment_Status, Appointment_Time_Change_Record
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        params = (
            patient_id,
            doctor_id,
            patient_info.get('name', '未提供'),
            appointment_time.strftime("%Y-%m-%d %H:%M"),
            appointment_info.get('urgency', '普通'),
            severity_level,
            patient_data.get('chief_complaint', ''),
            '已确认',
            '无'
        )
        
        appointment_id = self.db.execute_insert(insert_query, params)
        logger.info(f"成功创建预约，ID: {appointment_id}")
        
        return appointment_id
    
    def _update_doctor_availability(self, doctor_id: int, appointment_time: datetime):
        """
        更新医生的空闲时间（标记已预约）
        
        Args:
            doctor_id: 医生ID
            appointment_time: 预约时间
        """
        # 这里简化处理，实际应该更新医生的 Available_Time 字段
        # 可以记录已预约时间或标记为不可用
        logger.info(f"更新医生 {doctor_id} 在 {appointment_time} 的空闲状态")
        # 实际实现中可能需要更复杂的时间管理逻辑
        pass
    
    # ==================== 完整流程方法 ====================
    
    def process_appointment(self, patient_json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理完整的预约流程
        
        这是主要的对外接口，接收一号智能体的输出数据，完成：
        1. 创建或更新患者病例
        2. 查找可用医生
        3. 创建预约记录
        4. 更新医生空闲时间
        
        Args:
            patient_json_data: 一号智能体输出的患者数据字典
            
        Returns:
            结果字典，包含以下字段：
            - success: bool - 是否成功
            - patient_id: int - 患者ID
            - appointment_id: int - 预约ID（如果成功）
            - doctor_info: dict - 医生信息（如果成功）
            - message: str - 结果消息
            - available_doctors: list - 可用医生列表（如果有多个选择）
        """
        try:
            logger.info("=" * 50)
            logger.info("开始处理预约流程")
            logger.info("=" * 50)
            
            # 1. 验证必填字段（放宽要求，至少有姓名或联系方式之一）
            patient_info = patient_json_data.get('patient_info', {})
            has_name = patient_info.get('name') and patient_info.get('name').strip()
            has_contact = patient_info.get('contact') and patient_info.get('contact').strip()
            
            if not has_name and not has_contact:
                return {
                    'success': False,
                    'message': '患者姓名和联系方式都缺失，无法创建预约。请至少提供姓名或联系方式。'
                }
            
            # 如果缺少姓名，使用联系方式作为临时姓名
            if not has_name:
                patient_info['name'] = f"患者_{patient_info.get('contact', '未知')[:4]}"
                logger.warning(f"患者姓名缺失，使用临时姓名: {patient_info['name']}")
            
            # 如果缺少联系方式，使用空字符串
            if not has_contact:
                patient_info['contact'] = ''
                logger.warning("患者联系方式缺失")
            
            # 2. 创建或获取患者ID
            logger.info("步骤1: 创建/获取患者病例")
            patient_id = self.create_patient(patient_json_data)
            
            # 3. 查找可用医生
            logger.info("步骤2: 查找可用医生")
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
                return {
                    'success': False,
                    'patient_id': patient_id,
                    'message': f'未找到符合条件的可用医生（科室: {department}，期望时间: {preferred_time}）',
                    'available_doctors': []
                }
            
            # 4. 选择最匹配的医生（排序后的第一个）
            logger.info("步骤3: 选择最佳医生")
            best_doctor = available_doctors[0]
            doctor_id = best_doctor['Doctor_ID']
            
            # 使用医生的空闲时间作为预约时间
            appointment_time = best_doctor['parsed_start_time']
            
            # 5. 使用事务创建预约
            logger.info("步骤4: 创建预约记录")
            with self.db.transaction() as cursor:
                # 创建预约
                insert_query = """
                    INSERT INTO appointment (
                        Patient_ID, Doctor_ID, Patient_Name, Appointment_Time,
                        Appointment_Category, Severity_Level, Description,
                        Appointment_Status, Appointment_Time_Change_Record
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """
                
                severity_level = self._determine_severity_level(
                    urgency, patient_json_data.get('chief_complaint', '')
                )
                
                params = (
                    patient_id,
                    doctor_id,
                    patient_info.get('name', '未提供'),
                    appointment_time.strftime("%Y-%m-%d %H:%M"),
                    urgency,
                    severity_level,
                    patient_json_data.get('chief_complaint', ''),
                    '已确认',
                    '无'
                )
                
                cursor.execute(insert_query, params)
                appointment_id = cursor.lastrowid
                
                logger.info(f"预约创建成功，预约ID: {appointment_id}")
            
            # 6. 更新医生空闲状态
            self._update_doctor_availability(doctor_id, appointment_time)
            
            # 7. 返回成功结果
            logger.info("=" * 50)
            logger.info("预约流程完成")
            logger.info("=" * 50)
            
            return {
                'success': True,
                'patient_id': patient_id,
                'appointment_id': appointment_id,
                'doctor_info': {
                    'doctor_id': best_doctor['Doctor_ID'],
                    'name': best_doctor['Name'],
                    'title': best_doctor['Title'],
                    'specialty': best_doctor['Specialty'],
                    'hospital_area': best_doctor['Hospital_Area'],
                    'phone': best_doctor['Phone_Number']
                },
                'appointment_time': appointment_time.strftime("%Y-%m-%d %H:%M"),
                'message': f'预约成功！医生: {best_doctor["Name"]}（{best_doctor["Title"]}），时间: {appointment_time.strftime("%Y-%m-%d %H:%M")}',
                'available_doctors': [
                    {
                        'name': d['Name'],
                        'title': d['Title'],
                        'available_time': f"{d['parsed_start_time'].strftime('%Y-%m-%d %H:%M')} - {d['parsed_end_time'].strftime('%H:%M')}"
                    }
                    for d in available_doctors[:3]  # 返回前3个可选医生
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

