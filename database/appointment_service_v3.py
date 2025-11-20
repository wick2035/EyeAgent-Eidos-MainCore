"""
预约服务核心模块 V3 - 整合时间段管理系统 + UUID支持
处理用户创建、病例创建、医生查询和预约操作

新架构：Patient(用户) → Medical_Record(病例) → Appointment(预约)
V3 新增：基于 doctor_time_slots 的智能预约系统
UUID支持：兼容INT和UUID格式的ID

Created: 2025-11-19
Updated: 2025-11-20 (UUID support)
"""

import re
import uuid
from datetime import datetime, timedelta, date, time as dt_time
from typing import Dict, Any, List, Optional, Tuple, Union
import logging

from .db_connection import DatabaseConnection
from .time_slot_service import TimeSlotService
from .doctor_schedule_service import DoctorScheduleService
from .base_service import BaseServiceWithUUID, normalize_id

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AppointmentServiceV3(BaseServiceWithUUID):
    """预约服务类 V3 - 基于时间段管理系统 (支持UUID)"""

    def __init__(self):
        """初始化预约服务"""
        super().__init__()
        self.db = DatabaseConnection()
        self.slot_service = TimeSlotService()
        self.schedule_service = DoctorScheduleService()

    def __del__(self):
        """析构时关闭数据库连接"""
        self.db.close()

    # ==================== 用户管理相关方法（UUID支持）====================

    def create_or_get_patient(self, patient_info: Dict[str, Any], created_by_uuid: str = 'system') -> str:
        """
        创建或获取用户（一个人只有一个Patient记录）

        Args:
            patient_info: 用户基本信息 {'name': '', 'phone': '', 'gender': '', 'age': ''}
            created_by_uuid: 创建人UUID（默认'system'）

        Returns:
            Patient_UUID (用户UUID) - 现在返回UUID而非INT
        """
        phone = patient_info.get('contact') or patient_info.get('phone', '')

        if not phone:
            raise ValueError("手机号不能为空")

        # 检查用户是否已存在 (仅查询未删除的记录)
        query = "SELECT Patient_ID, Patient_UUID FROM patient WHERE Phone_Number = %s AND Deleted = 0"
        existing_user = self.db.execute_one(query, (phone,))

        if existing_user:
            patient_uuid = existing_user['Patient_UUID']
            patient_id = existing_user['Patient_ID']
            logger.info(f"用户已存在，Patient_ID: {patient_id}, Patient_UUID: {patient_uuid}")
            return patient_uuid  # 返回UUID

        # 创建新用户 (触发器会自动生成UUID)
        insert_query = """
            INSERT INTO patient (
                Name, Gender, Age, Phone_Number,
                Create_By, Version, Deleted
            ) VALUES (%s, %s, %s, %s, %s, 0, 0)
        """

        params = (
            patient_info.get('name', '未提供'),
            patient_info.get('gender', '未知'),
            patient_info.get('age', 0),
            phone,
            created_by_uuid
        )

        patient_id = self.db.execute_insert(insert_query, params)

        # 查询生成的UUID
        query_uuid = "SELECT Patient_UUID FROM patient WHERE Patient_ID = %s"
        result = self.db.execute_one(query_uuid, (patient_id,))
        patient_uuid = result['Patient_UUID'] if result else None

        logger.info(f"创建新用户，Patient_ID: {patient_id}, Patient_UUID: {patient_uuid}, Created_By: {created_by_uuid}")

        return patient_uuid  # 返回UUID

    # ==================== 病例管理相关方法（保持不变）====================

    def _generate_visit_card_number(self) -> str:
        """
        生成就诊卡号
        格式: YYYY-XXXXXX (年份 + 6位序列号)
        """
        year = datetime.now().year
        query = """
            SELECT Visit_Card_Number FROM medical_record
            WHERE Visit_Card_Number LIKE %s AND Deleted = 0
            ORDER BY Visit_Card_Number DESC
            LIMIT 1
        """
        result = self.db.execute_one(query, (f"{year}-%",))

        if result and result['Visit_Card_Number']:
            last_number = int(result['Visit_Card_Number'].split('-')[1])
            new_number = last_number + 1
        else:
            new_number = 1

        return f"{year}-{new_number:06d}"

    def create_medical_record(self, patient_id: Union[str, int], patient_data: Dict[str, Any], created_by_uuid: str = 'system') -> str:
        """
        创建病例记录（每次就诊创建新病例）

        Args:
            patient_id: 患者ID（支持Patient_ID或Patient_UUID）
            patient_data: 病例数据
            created_by_uuid: 创建人UUID（默认'system'）

        Returns:
            Medical_Record_UUID (病例UUID)
        """
        visit_card_number = self._generate_visit_card_number()
        visit_date = datetime.now().strftime("%Y-%m-%d")

        # 规范化patient_id
        patient_id_normalized = normalize_id(patient_id)

        # 查询Patient_UUID (如果传入的是INT ID)
        if patient_id_normalized.isdigit():
            query_patient = "SELECT Patient_UUID FROM patient WHERE Patient_ID = %s"
            patient_result = self.db.execute_one(query_patient, (patient_id_normalized,))
            patient_uuid = patient_result['Patient_UUID'] if patient_result else patient_id_normalized
        else:
            patient_uuid = patient_id_normalized

        # 使用Patient_UUID插入 (触发器会自动填充Patient_ID和生成Medical_Record_UUID)
        insert_query = """
            INSERT INTO medical_record (
                Patient_UUID, Visit_Card_Number, Visit_Date, Department,
                Chief_Complaint, Present_Illness, Medical_History,
                Allergy_History, Family_History, Medication_History,
                Create_By, Version, Deleted
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0
            )
        """

        params = (
            patient_uuid,
            visit_card_number,
            visit_date,
            patient_data.get('appointment', {}).get('department', '眼科'),
            patient_data.get('chief_complaint', ''),
            patient_data.get('present_illness', ''),
            patient_data.get('medical_history', ''),
            patient_data.get('allergy_history', ''),
            patient_data.get('family_history', ''),
            patient_data.get('medication_history', ''),
            created_by_uuid
        )

        medical_record_id = self.db.execute_insert(insert_query, params)

        # 查询生成的UUID
        query_uuid = "SELECT Medical_Record_UUID FROM medical_record WHERE Medical_Record_ID = %s"
        result = self.db.execute_one(query_uuid, (medical_record_id,))
        medical_record_uuid = result['Medical_Record_UUID'] if result else None

        logger.info(f"创建病例记录，Medical_Record_ID: {medical_record_id}, Medical_Record_UUID: {medical_record_uuid}, Created_By: {created_by_uuid}")

        return medical_record_uuid  # 返回UUID

    # ==================== V3 新增：基于时间段的医生查询 ====================

    def _parse_time_expression(self, time_expr: str) -> Optional[datetime]:
        """解析自然语言时间表达式（保持兼容性）"""
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

    def find_available_doctors(
        self,
        department: str,
        preferred_time_expr: str = None,
        doctor_preference: str = None,
        urgency: str = "普通"
    ) -> List[Dict]:
        """
        V3 版本：基于 doctor_time_slots 查找可用医生和时间段

        Args:
            department: 科室名称
            preferred_time_expr: 期望时间表达式（如"明天上午"）
            doctor_preference: 医生偏好（如"主任医师"）
            urgency: 紧急程度（"普通"/"紧急"）

        Returns:
            可用医生及时间段列表，每个元素包含：
            {
                "doctor_id": int,
                "doctor_name": str,
                "doctor_title": str,
                "available_slots": [
                    {
                        "slot_id": int,
                        "slot_date": str,
                        "slot_start_time": str,
                        "slot_end_time": str,
                        "remaining_slots": int,
                        "appointment_datetime": str
                    },
                    ...
                ],
                "match_score": int
            }
        """
        # 解析期望时间
        preferred_time = None
        if preferred_time_expr:
            preferred_time = self._parse_time_expression(preferred_time_expr)
            logger.info(f"解析患者期望时间: {preferred_time_expr} -> {preferred_time}")

        # 确定查询日期范围
        if preferred_time:
            start_date = preferred_time.date()
            end_date = start_date
        else:
            start_date = date.today()
            end_date = start_date + timedelta(days=3)

        # 查询可用时间段
        slots_result = self.slot_service.get_available_slots(
            specialty=department,
            start_date=start_date,
            end_date=end_date,
            only_available=True
        )

        if not slots_result['success'] or not slots_result['slots']:
            logger.warning(f"未找到 {department} 的可用时间段")
            return []

        # 按医生分组时间段
        doctor_slots_map = {}
        for slot in slots_result['slots']:
            doctor_id = slot['doctor_id']

            # 如果指定了期望时间，筛选匹配的时间段
            if preferred_time:
                slot_datetime = datetime.strptime(slot['appointment_datetime'], "%Y-%m-%d %H:%M:%S")
                # 允许±2小时的误差
                time_diff = abs((slot_datetime - preferred_time).total_seconds() / 3600)
                if time_diff > 2:
                    continue

            if doctor_id not in doctor_slots_map:
                doctor_slots_map[doctor_id] = {
                    "doctor_id": doctor_id,
                    "doctor_name": slot['doctor_name'],
                    "doctor_title": slot['doctor_title'],
                    "specialty": slot['specialty'],
                    "available_slots": []
                }

            doctor_slots_map[doctor_id]['available_slots'].append({
                "slot_id": slot['slot_id'],
                "slot_date": slot['slot_date'],
                "slot_start_time": slot['slot_start_time'],
                "slot_end_time": slot['slot_end_time'],
                "remaining_slots": slot['remaining_slots'],
                "appointment_datetime": slot['appointment_datetime']
            })

        # 计算匹配分数并排序
        available_doctors = []
        for doctor_data in doctor_slots_map.values():
            doctor_data['match_score'] = self._calculate_match_score_v3(
                doctor_data,
                doctor_preference,
                urgency
            )
            available_doctors.append(doctor_data)

        # 按匹配分数排序
        available_doctors.sort(key=lambda x: x['match_score'], reverse=True)

        logger.info(f"找到 {len(available_doctors)} 位可用医生，共 {len(slots_result['slots'])} 个时间段")
        return available_doctors

    def _calculate_match_score_v3(
        self,
        doctor_data: Dict,
        doctor_preference: str,
        urgency: str
    ) -> int:
        """计算医生匹配分数（V3版本）"""
        score = 0

        # 职称加分
        title = doctor_data.get('doctor_title', '')
        if '主任' in title:
            score += 3
        elif '副主任' in title:
            score += 2
        elif '主治' in title:
            score += 1

        # 医生偏好加分
        if doctor_preference and doctor_preference in title:
            score += 5

        # 紧急程度处理
        if urgency in ['紧急', '急'] and '主任' in title:
            score += 2

        # 可用时间段数量加分（每个时间段+0.1分）
        score += len(doctor_data.get('available_slots', [])) * 0.1

        return score

    # ==================== V3 新增：基于时间段的预约创建 ====================

    def _determine_severity_level(self, urgency: str, chief_complaint: str) -> str:
        """确定病情严重等级"""
        urgent_keywords = ['出血', '剧痛', '失明', '突然', '急性', '严重']

        if urgency in ['紧急', '急']:
            return '严重'

        if any(keyword in chief_complaint for keyword in urgent_keywords):
            return '严重'

        return '中等'

    def create_appointment_v3(
        self,
        medical_record_id: int,
        patient_id: int,
        slot_id: int,
        patient_data: Dict[str, Any],
        created_by_uuid: str = 'system'
    ) -> Dict[str, Any]:
        """
        V3 版本：基于时间段创建预约（带并发控制）

        Args:
            medical_record_id: 病例ID
            patient_id: 用户ID
            slot_id: 时间段ID
            patient_data: 患者数据字典
            created_by_uuid: 创建人UUID（默认'system'）

        Returns:
            {
                "success": bool,
                "message": str,
                "appointment_id": int,
                "appointment_time": str
            }
        """
        try:
            # 1. 检查时间段可用性（原子性检查+预留）
            reserve_result = self.slot_service.reserve_slot(slot_id, patient_id)

            if not reserve_result['success']:
                return {
                    "success": False,
                    "message": reserve_result['message']
                }

            slot_info = reserve_result['slot_info']
            doctor_id = slot_info['doctor_id']
            appointment_datetime = datetime.strptime(
                slot_info['appointment_datetime'],
                "%Y-%m-%d %H:%M:%S"
            )

            # 2. 获取患者和预约信息
            patient_info = patient_data.get('patient_info', {})
            appointment_info = patient_data.get('appointment', {})

            category = appointment_info.get('urgency', '普通')
            if category in ['紧急', '急']:
                category = '紧急'
            else:
                category = '普通'

            severity_level = self._determine_severity_level(
                category,
                patient_data.get('chief_complaint', '')
            )

            description = patient_data.get('chief_complaint', '')
            if patient_data.get('present_illness'):
                description += f" | {patient_data.get('present_illness')}"

            # 3. 创建预约记录 (使用UUID主键)
            insert_query = """
                INSERT INTO appointment (
                    Appointment_UUID, Medical_Record_UUID, Patient_UUID, Doctor_UUID, Time_Slot_UUID,
                    Patient_Name, Appointment_Time, Appointment_Category,
                    Severity_Level, Description, Appointment_Status,
                    Create_By, Version, Deleted
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0
                )
            """

            # 生成Appointment UUID
            appointment_uuid = str(uuid.uuid4())

            params = (
                appointment_uuid,  # Appointment_UUID
                medical_record_id,  # Medical_Record_UUID (应该已经是UUID)
                patient_id,         # Patient_UUID (应该已经是UUID)
                doctor_id,          # Doctor_UUID (应该已经是UUID)
                slot_id,            # Time_Slot_UUID (应该已经是UUID)
                patient_info.get('name', ''),
                appointment_datetime,
                category,
                severity_level,
                description,
                '已预约',
                created_by_uuid
            )

            self.db.execute_insert(insert_query, params)

            # 4. 触发器会自动增加 current_bookings

            logger.info(f"创建预约成功，Appointment_UUID: {appointment_uuid}, Created_By: {created_by_uuid}")

            return {
                "success": True,
                "message": f"预约成功！预约时间：{appointment_datetime.strftime('%Y-%m-%d %H:%M')}",
                "appointment_id": appointment_uuid,  # 现在返回UUID而非INT
                "appointment_uuid": appointment_uuid,  # 同时提供明确的UUID字段
                "appointment_time": appointment_datetime.strftime('%Y-%m-%d %H:%M'),
                "slot_id": slot_id
            }

        except Exception as e:
            logger.error(f"创建预约失败：{e}")
            return {
                "success": False,
                "message": f"预约失败：{str(e)}"
            }

    def cancel_appointment(self, appointment_id: int, updated_by_uuid: str = 'system') -> Dict[str, Any]:
        """
        取消预约（触发器会自动减少 current_bookings）

        Args:
            appointment_id: 预约ID
            updated_by_uuid: 更新人UUID（默认'system'）

        Returns:
            {"success": bool, "message": str}
        """
        try:
            # 更新预约状态为已取消 (使用乐观锁)
            update_query = """
                UPDATE appointment
                SET Appointment_Status = '已取消',
                    Update_By = %s,
                    Version = Version + 1,
                    Updated_At = CURRENT_TIMESTAMP
                WHERE Appointment_ID = %s
                  AND Appointment_Status IN ('已预约', '已确认')
                  AND Deleted = 0
            """

            rows_affected = self.db.execute_update(update_query, (updated_by_uuid, appointment_id))

            if rows_affected > 0:
                logger.info(f"取消预约成功，Appointment_ID: {appointment_id}")
                return {
                    "success": True,
                    "message": "预约已取消"
                }
            else:
                return {
                    "success": False,
                    "message": "预约不存在或已取消"
                }

        except Exception as e:
            logger.error(f"取消预约失败：{e}")
            return {
                "success": False,
                "message": f"取消预约失败：{str(e)}"
            }

    # ==================== 完整预约流程（V3版本）====================

    def process_appointment(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理完整的预约流程（V3版本）

        流程：
        1. 创建或获取用户 (patient)
        2. 创建病例记录 (medical_record)
        3. 查找可用医生和时间段
        4. 选择最佳时间段
        5. 创建预约 (appointment)

        Args:
            patient_data: 包含患者信息和预约需求的字典

        Returns:
            {
                "success": bool,
                "message": str,
                "appointment_id": int,
                "appointment_details": Dict
            }
        """
        try:
            # 步骤1：创建或获取用户
            patient_info = patient_data.get('patient_info', {})
            patient_id = self.create_or_get_patient(patient_info)

            # 步骤2：创建病例记录
            medical_record_id = self.create_medical_record(patient_id, patient_data)

            # 步骤3：查找可用医生
            appointment_info = patient_data.get('appointment', {})
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
                    "success": False,
                    "message": f"抱歉，{department}暂时没有可用的医生时间段，请稍后再试或选择其他时间"
                }

            # 步骤4：选择最佳医生和时间段（得分最高的医生的第一个时间段）
            best_doctor = available_doctors[0]
            best_slot = best_doctor['available_slots'][0]

            # 步骤5：创建预约
            appointment_result = self.create_appointment_v3(
                medical_record_id=medical_record_id,
                patient_id=patient_id,
                slot_id=best_slot['slot_id'],
                patient_data=patient_data
            )

            if not appointment_result['success']:
                return appointment_result

            # 构建详细信息
            return {
                "success": True,
                "message": appointment_result['message'],
                "appointment_id": appointment_result['appointment_id'],
                "appointment_details": {
                    "patient_id": patient_id,
                    "patient_name": patient_info.get('name', ''),
                    "medical_record_id": medical_record_id,
                    "doctor_id": best_doctor['doctor_id'],
                    "doctor_name": best_doctor['doctor_name'],
                    "doctor_title": best_doctor['doctor_title'],
                    "appointment_time": appointment_result['appointment_time'],
                    "department": department,
                    "slot_id": best_slot['slot_id'],
                    "remaining_slots": best_slot['remaining_slots'] - 1  # 减去刚预约的
                }
            }

        except Exception as e:
            logger.error(f"预约流程失败：{e}")
            return {
                "success": False,
                "message": f"预约失败：{str(e)}"
            }
