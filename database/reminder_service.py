"""
提醒服务 - 管理复诊提醒、预约提醒、用药提醒等功能
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from database.db_connection import DatabaseConnection


class ReminderService:
    """提醒服务类"""

    def __init__(self):
        self.db = DatabaseConnection()

    def create_reminder(
        self,
        patient_id: int,
        reminder_type: str,
        reminder_title: str,
        reminder_content: str,
        scheduled_time: datetime,
        advance_days: int = 1,
        priority: str = 'normal',
        medical_record_id: Optional[int] = None,
        appointment_id: Optional[int] = None,
        prescription_id: Optional[int] = None,
        repeat_type: str = 'once',
        max_repeat_count: int = 1,
        created_by: str = 'system',
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建新提醒

        Args:
            patient_id: 患者ID
            reminder_type: 提醒类型 (follow_up/appointment/medication/checkup/custom)
            reminder_title: 提醒标题
            reminder_content: 提醒内容
            scheduled_time: 计划提醒时间
            advance_days: 提前提醒天数
            priority: 优先级 (low/normal/high/urgent)
            medical_record_id: 关联病例ID（可选）
            appointment_id: 关联预约ID（可选）
            prescription_id: 关联处方ID（可选）
            repeat_type: 重复类型 (once/daily/weekly/monthly/custom)
            max_repeat_count: 最大重复次数
            created_by: 创建者
            notes: 备注

        Returns:
            包含成功状态和提醒ID的字典
        """
        try:
            query = """
                INSERT INTO reminder (
                    Patient_ID, Medical_Record_ID, Appointment_ID, Prescription_ID,
                    Reminder_Type, Reminder_Title, Reminder_Content,
                    Scheduled_Time, Advance_Days, Priority,
                    Repeat_Type, Max_Repeat_Count, Created_By, Notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            reminder_id = self.db.execute_insert(
                query,
                (patient_id, medical_record_id, appointment_id, prescription_id,
                 reminder_type, reminder_title, reminder_content,
                 scheduled_time, advance_days, priority,
                 repeat_type, max_repeat_count, created_by, notes)
            )

            # 记录历史
            self._add_history(reminder_id, 'created', created_by, f'创建提醒: {reminder_title}')

            return {
                'success': True,
                'reminder_id': reminder_id,
                'message': '提醒创建成功'
            }

        except Exception as e:
            print(f"[ReminderService] 创建提醒失败: {e}")
            return {
                'success': False,
                'message': f'创建提醒失败: {str(e)}'
            }

    def get_reminders_by_patient(
        self,
        patient_id: int,
        status: Optional[str] = None,
        reminder_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取患者的提醒列表

        Args:
            patient_id: 患者ID
            status: 状态过滤 (pending/sent/completed/cancelled/expired)
            reminder_type: 类型过滤 (follow_up/appointment/medication/checkup/custom)
            limit: 返回数量限制

        Returns:
            提醒列表
        """
        try:
            query = """
                SELECT
                    r.*,
                    p.Name as Patient_Name,
                    p.Phone_Number,
                    mr.Visit_Date,
                    a.Appointment_Time,
                    pr.Prescription_Number
                FROM reminder r
                LEFT JOIN patient p ON r.Patient_ID = p.Patient_ID
                LEFT JOIN medical_record mr ON r.Medical_Record_ID = mr.Medical_Record_ID
                LEFT JOIN appointment a ON r.Appointment_ID = a.Appointment_ID
                LEFT JOIN prescription pr ON r.Prescription_ID = pr.Prescription_ID
                WHERE r.Patient_ID = %s
            """

            params = [patient_id]

            if status:
                query += " AND r.Status = %s"
                params.append(status)

            if reminder_type:
                query += " AND r.Reminder_Type = %s"
                params.append(reminder_type)

            query += " ORDER BY r.Scheduled_Time DESC LIMIT %s"
            params.append(limit)

            return self.db.execute_query(query, tuple(params))

        except Exception as e:
            print(f"[ReminderService] 查询患者提醒失败: {e}")
            return []

    def get_reminders_by_phone(
        self,
        phone_number: str,
        status: Optional[str] = None,
        reminder_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        通过手机号获取患者的提醒列表

        Args:
            phone_number: 患者手机号
            status: 状态过滤
            reminder_type: 类型过滤
            limit: 返回数量限制

        Returns:
            提醒列表
        """
        try:
            # 先获取患者ID
            patient = self.db.execute_one(
                "SELECT Patient_ID FROM patient WHERE Phone_Number = %s",
                (phone_number,)
            )

            if not patient:
                return []

            return self.get_reminders_by_patient(
                patient['Patient_ID'],
                status=status,
                reminder_type=reminder_type,
                limit=limit
            )

        except Exception as e:
            print(f"[ReminderService] 通过手机号查询提醒失败: {e}")
            return []

    def get_pending_reminders(
        self,
        check_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取待发送的提醒（用于定时任务）

        Args:
            check_time: 检查时间（默认为当前时间）
            limit: 返回数量限制

        Returns:
            待发送的提醒列表
        """
        try:
            if check_time is None:
                check_time = datetime.now()

            query = """
                SELECT
                    r.*,
                    p.Name as Patient_Name,
                    p.Phone_Number,
                    rc.Preferred_Notification_Method,
                    rc.Quiet_Hours_Start,
                    rc.Quiet_Hours_End
                FROM reminder r
                LEFT JOIN patient p ON r.Patient_ID = p.Patient_ID
                LEFT JOIN reminder_config rc ON r.Patient_ID = rc.Patient_ID
                WHERE r.Status = 'pending'
                AND DATE_SUB(r.Scheduled_Time, INTERVAL r.Advance_Days DAY) <= %s
                ORDER BY r.Priority DESC, r.Scheduled_Time ASC
                LIMIT %s
            """

            return self.db.execute_query(query, (check_time, limit))

        except Exception as e:
            print(f"[ReminderService] 查询待发送提醒失败: {e}")
            return []

    def update_reminder_status(
        self,
        reminder_id: int,
        status: str,
        action_by: str = 'system',
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        更新提醒状态

        Args:
            reminder_id: 提醒ID
            status: 新状态 (sent/completed/cancelled/expired)
            action_by: 操作者
            notes: 备注

        Returns:
            更新结果
        """
        try:
            # 更新状态和对应时间字段
            time_field_map = {
                'sent': 'Sent_Time',
                'completed': 'Completed_Time',
                'cancelled': 'Cancelled_Time'
            }

            time_field = time_field_map.get(status)

            if time_field:
                query = f"""
                    UPDATE reminder
                    SET Status = %s, {time_field} = %s, Notes = COALESCE(%s, Notes)
                    WHERE Reminder_ID = %s
                """
                self.db.execute_update(query, (status, datetime.now(), notes, reminder_id))
            else:
                query = "UPDATE reminder SET Status = %s WHERE Reminder_ID = %s"
                self.db.execute_update(query, (status, reminder_id))

            # 记录历史
            action_details = notes if notes else f'状态更新为: {status}'
            self._add_history(reminder_id, status, action_by, action_details)

            return {
                'success': True,
                'message': f'提醒状态已更新为: {status}'
            }

        except Exception as e:
            print(f"[ReminderService] 更新提醒状态失败: {e}")
            return {
                'success': False,
                'message': f'更新失败: {str(e)}'
            }

    def reschedule_reminder(
        self,
        reminder_id: int,
        new_scheduled_time: datetime,
        action_by: str = 'patient',
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        重新安排提醒时间

        Args:
            reminder_id: 提醒ID
            new_scheduled_time: 新的计划时间
            action_by: 操作者
            reason: 原因

        Returns:
            更新结果
        """
        try:
            query = """
                UPDATE reminder
                SET Scheduled_Time = %s, Status = 'pending', Notes = CONCAT(COALESCE(Notes, ''), '\n重新安排: ', %s)
                WHERE Reminder_ID = %s
            """

            note = reason if reason else f'改期至 {new_scheduled_time}'
            self.db.execute_update(query, (new_scheduled_time, note, reminder_id))

            # 记录历史
            self._add_history(reminder_id, 'rescheduled', action_by, f'改期至: {new_scheduled_time}')

            return {
                'success': True,
                'message': '提醒时间已重新安排'
            }

        except Exception as e:
            print(f"[ReminderService] 重新安排提醒失败: {e}")
            return {
                'success': False,
                'message': f'重新安排失败: {str(e)}'
            }

    def create_follow_up_reminder(
        self,
        patient_id: int,
        follow_up_date: datetime,
        medical_record_id: Optional[int] = None,
        advance_days: int = 3,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        便捷方法：创建复诊提醒

        Args:
            patient_id: 患者ID
            follow_up_date: 复诊日期
            medical_record_id: 关联病例ID
            advance_days: 提前天数
            notes: 备注

        Returns:
            创建结果
        """
        content = f"您的复诊日期为 {follow_up_date.strftime('%Y年%m月%d日')}，请准时就诊。"
        if notes:
            content += f"\n医生建议：{notes}"

        return self.create_reminder(
            patient_id=patient_id,
            reminder_type='follow_up',
            reminder_title='复诊提醒',
            reminder_content=content,
            scheduled_time=follow_up_date,
            advance_days=advance_days,
            priority='high',
            medical_record_id=medical_record_id,
            created_by='system',
            notes=notes
        )

    def create_appointment_reminder(
        self,
        patient_id: int,
        appointment_id: int,
        appointment_time: datetime,
        advance_days: int = 1
    ) -> Dict[str, Any]:
        """
        便捷方法：创建预约提醒

        Args:
            patient_id: 患者ID
            appointment_id: 预约ID
            appointment_time: 预约时间
            advance_days: 提前天数

        Returns:
            创建结果
        """
        content = f"您预约的就诊时间为 {appointment_time.strftime('%Y年%m月%d日 %H:%M')}，请携带就诊卡和医保卡准时就诊。"

        return self.create_reminder(
            patient_id=patient_id,
            reminder_type='appointment',
            reminder_title='预约就诊提醒',
            reminder_content=content,
            scheduled_time=appointment_time,
            advance_days=advance_days,
            priority='high',
            appointment_id=appointment_id,
            created_by='system'
        )

    def create_medication_reminder(
        self,
        patient_id: int,
        prescription_id: int,
        medication_name: str,
        dosage: str,
        duration_days: int = 7
    ) -> Dict[str, Any]:
        """
        便捷方法：创建用药提醒

        Args:
            patient_id: 患者ID
            prescription_id: 处方ID
            medication_name: 药物名称
            dosage: 用法用量
            duration_days: 疗程天数

        Returns:
            创建结果
        """
        content = f"请按时服用 {medication_name}。\n用法用量：{dosage}"

        return self.create_reminder(
            patient_id=patient_id,
            reminder_type='medication',
            reminder_title='用药提醒',
            reminder_content=content,
            scheduled_time=datetime.now() + timedelta(days=1),
            advance_days=0,
            priority='normal',
            prescription_id=prescription_id,
            repeat_type='daily',
            max_repeat_count=duration_days,
            created_by='doctor'
        )

    def get_reminder_config(self, patient_id: int) -> Optional[Dict[str, Any]]:
        """
        获取患者的提醒配置

        Args:
            patient_id: 患者ID

        Returns:
            配置信息
        """
        try:
            return self.db.execute_one(
                "SELECT * FROM reminder_config WHERE Patient_ID = %s",
                (patient_id,)
            )
        except Exception as e:
            print(f"[ReminderService] 获取提醒配置失败: {e}")
            return None

    def update_reminder_config(
        self,
        patient_id: int,
        enable_follow_up: Optional[bool] = None,
        enable_appointment: Optional[bool] = None,
        enable_medication: Optional[bool] = None,
        default_advance_days: Optional[int] = None,
        preferred_notification_method: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        更新患者的提醒配置

        Args:
            patient_id: 患者ID
            enable_follow_up: 启用复诊提醒
            enable_appointment: 启用预约提醒
            enable_medication: 启用用药提醒
            default_advance_days: 默认提前天数
            preferred_notification_method: 偏好通知方式

        Returns:
            更新结果
        """
        try:
            # 构建动态更新语句
            updates = []
            params = []

            if enable_follow_up is not None:
                updates.append("Enable_Follow_Up = %s")
                params.append(enable_follow_up)

            if enable_appointment is not None:
                updates.append("Enable_Appointment = %s")
                params.append(enable_appointment)

            if enable_medication is not None:
                updates.append("Enable_Medication = %s")
                params.append(enable_medication)

            if default_advance_days is not None:
                updates.append("Default_Advance_Days = %s")
                params.append(default_advance_days)

            if preferred_notification_method is not None:
                updates.append("Preferred_Notification_Method = %s")
                params.append(preferred_notification_method)

            if not updates:
                return {'success': True, 'message': '无需更新'}

            params.append(patient_id)
            query = f"UPDATE reminder_config SET {', '.join(updates)} WHERE Patient_ID = %s"

            self.db.execute_update(query, tuple(params))

            return {
                'success': True,
                'message': '提醒配置已更新'
            }

        except Exception as e:
            print(f"[ReminderService] 更新提醒配置失败: {e}")
            return {
                'success': False,
                'message': f'更新失败: {str(e)}'
            }

    def _add_history(
        self,
        reminder_id: int,
        action_type: str,
        action_by: str,
        action_details: Optional[str] = None
    ):
        """
        添加提醒历史记录（内部方法）

        Args:
            reminder_id: 提醒ID
            action_type: 操作类型
            action_by: 操作者
            action_details: 操作详情
        """
        try:
            query = """
                INSERT INTO reminder_history (Reminder_ID, Action_Type, Action_By, Action_Details)
                VALUES (%s, %s, %s, %s)
            """
            self.db.execute_insert(query, (reminder_id, action_type, action_by, action_details))
        except Exception as e:
            print(f"[ReminderService] 添加历史记录失败: {e}")

    def get_reminder_history(self, reminder_id: int) -> List[Dict[str, Any]]:
        """
        获取提醒的历史记录

        Args:
            reminder_id: 提醒ID

        Returns:
            历史记录列表
        """
        try:
            query = """
                SELECT * FROM reminder_history
                WHERE Reminder_ID = %s
                ORDER BY Action_Time DESC
            """
            return self.db.execute_query(query, (reminder_id,))
        except Exception as e:
            print(f"[ReminderService] 获取历史记录失败: {e}")
            return []

    def close(self):
        """关闭数据库连接"""
        self.db.close()
