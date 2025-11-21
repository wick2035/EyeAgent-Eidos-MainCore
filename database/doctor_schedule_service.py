"""
医生排班管理服务 (Doctor Schedule Service)
V4 版本 - UUID适配版本,支持灵活的排班管理和时间段生成

功能：
1. 创建和管理医生每周工作时间模板 (doctor_working_schedule)
2. 根据排班模板生成具体时间段 (doctor_time_slots)
3. 管理排班例外情况（请假、节假日等）
4. 调整医生接诊容量和时间段配置
5. 查询医生可用时间段

Migration: 已适配UUID主键格式
Created: 2025-11-19
Updated: 2025-11-21 (UUID Migration)
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, date, time, timedelta
import pymysql
from database.db_connection import DatabaseConnection
from database.base_service import BaseServiceWithUUID


class DoctorScheduleService(BaseServiceWithUUID):
    """医生排班管理服务 - UUID版本"""

    def __init__(self):
        super().__init__()
        self.db = DatabaseConnection()

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'db'):
            self.db.close()

    # ========================================
    # 1. 每周排班模板管理
    # ========================================

    def create_weekly_schedule(
        self,
        doctor_uuid: str,
        schedule_data: List[Dict[str, any]]
    ) -> Dict[str, any]:
        """
        创建医生的每周工作时间模板

        Args:
            doctor_uuid: 医生UUID
            schedule_data: 排班数据列表，格式：
                [
                    {
                        "day_of_week": 1,  # 0=周日，1=周一，...，6=周六
                        "shift_start_time": "09:00:00",
                        "shift_end_time": "12:00:00",
                        "is_active": True
                    },
                    ...
                ]

        Returns:
            {"success": bool, "message": str, "created_count": int}
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # 验证医生是否存在
            cursor.execute("SELECT Name FROM doctor WHERE Doctor_UUID = %s", (doctor_uuid,))
            doctor = cursor.fetchone()
            if not doctor:
                return {"success": False, "message": f"医生UUID {doctor_uuid} 不存在"}

            created_count = 0

            for schedule in schedule_data:
                day_of_week = schedule.get('day_of_week')
                shift_start = schedule.get('shift_start_time')
                shift_end = schedule.get('shift_end_time')
                is_active = schedule.get('is_active', True)

                # 验证必填字段
                if day_of_week is None or not shift_start or not shift_end:
                    continue

                # 生成Schedule_UUID
                schedule_uuid = self.generate_uuid()

                # 插入排班记录（使用 ON DUPLICATE KEY UPDATE 处理重复）
                sql = """
                    INSERT INTO doctor_working_schedule
                    (Schedule_UUID, Doctor_UUID, Day_of_Week, Shift_Start_Time, Shift_End_Time, Is_Active)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        Shift_End_Time = VALUES(Shift_End_Time),
                        Is_Active = VALUES(Is_Active),
                        Updated_At = CURRENT_TIMESTAMP
                """
                cursor.execute(sql, (schedule_uuid, doctor_uuid, day_of_week, shift_start, shift_end, is_active))
                created_count += 1

            conn.commit()

            return {
                "success": True,
                "message": f"成功为医生 {doctor['Name']} 创建 {created_count} 条排班规则",
                "created_count": created_count
            }

        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"创建排班失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    def get_weekly_schedule(self, doctor_uuid: str) -> Dict[str, any]:
        """
        获取医生的每周排班模板

        Args:
            doctor_uuid: 医生UUID

        Returns:
            {
                "success": bool,
                "schedule": List[Dict],  # 排班列表
                "doctor_name": str
            }
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # 获取医生信息
            cursor.execute("SELECT Name FROM doctor WHERE Doctor_UUID = %s", (doctor_uuid,))
            doctor = cursor.fetchone()
            if not doctor:
                return {"success": False, "message": f"医生UUID {doctor_uuid} 不存在"}

            # 获取排班记录
            sql = """
                SELECT Schedule_UUID, Day_of_Week, Shift_Start_Time, Shift_End_Time, Is_Active
                FROM doctor_working_schedule
                WHERE Doctor_UUID = %s
                ORDER BY Day_of_Week, Shift_Start_Time
            """
            cursor.execute(sql, (doctor_uuid,))
            rows = cursor.fetchall()

            schedule_list = []
            day_names = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

            for row in rows:
                schedule_list.append({
                    "schedule_uuid": row['Schedule_UUID'],
                    "day_of_week": row['Day_of_Week'],
                    "day_name": day_names[row['Day_of_Week']],
                    "shift_start_time": str(row['Shift_Start_Time']),
                    "shift_end_time": str(row['Shift_End_Time']),
                    "is_active": bool(row['Is_Active'])
                })

            return {
                "success": True,
                "doctor_name": doctor['Name'],
                "schedule": schedule_list
            }

        except Exception as e:
            return {"success": False, "message": f"查询排班失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    def update_schedule_status(
        self,
        schedule_uuid: str,
        is_active: bool
    ) -> Dict[str, any]:
        """
        启用或禁用某个排班规则

        Args:
            schedule_uuid: 排班UUID
            is_active: 是否启用

        Returns:
            {"success": bool, "message": str}
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            sql = """
                UPDATE doctor_working_schedule
                SET Is_Active = %s, Updated_At = CURRENT_TIMESTAMP
                WHERE Schedule_UUID = %s
            """
            cursor.execute(sql, (is_active, schedule_uuid))
            conn.commit()

            status = "启用" if is_active else "禁用"
            return {"success": True, "message": f"已{status}排班规则 UUID {schedule_uuid}"}

        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"更新失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    def delete_schedule(self, schedule_uuid: str) -> Dict[str, any]:
        """
        删除某个排班规则

        Args:
            schedule_uuid: 排班UUID

        Returns:
            {"success": bool, "message": str}
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            sql = "DELETE FROM doctor_working_schedule WHERE Schedule_UUID = %s"
            cursor.execute(sql, (schedule_uuid,))
            conn.commit()

            if cursor.rowcount > 0:
                return {"success": True, "message": f"已删除排班规则 UUID {schedule_uuid}"}
            else:
                return {"success": False, "message": f"排班规则 UUID {schedule_uuid} 不存在"}

        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"删除失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    # ========================================
    # 2. 排班例外管理（请假、节假日）
    # ========================================

    def add_schedule_exception(
        self,
        doctor_uuid: str,
        exception_date: date,
        exception_type: str,
        is_full_day: bool = True,
        start_time: Optional[time] = None,
        end_time: Optional[time] = None,
        reason: Optional[str] = None
    ) -> Dict[str, any]:
        """
        添加排班例外（请假、节假日、临时调整）

        Args:
            doctor_uuid: 医生UUID
            exception_date: 例外日期
            exception_type: 类型（"请假"/"节假日"/"临时调整"）
            is_full_day: 是否全天
            start_time: 开始时间（如果是部分时间）
            end_time: 结束时间（如果是部分时间）
            reason: 原因说明

        Returns:
            {"success": bool, "message": str, "exception_uuid": str}
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # 验证医生是否存在
            cursor.execute("SELECT Name FROM doctor WHERE Doctor_UUID = %s", (doctor_uuid,))
            doctor = cursor.fetchone()
            if not doctor:
                return {"success": False, "message": f"医生UUID {doctor_uuid} 不存在"}

            # 生成Exception_UUID
            exception_uuid = self.generate_uuid()

            sql = """
                INSERT INTO doctor_schedule_exceptions
                (Exception_UUID, Doctor_UUID, Exception_Date, Exception_Type, Is_Full_Day,
                 Start_Time, End_Time, Reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                exception_uuid, doctor_uuid, exception_date, exception_type, is_full_day,
                start_time, end_time, reason
            ))
            conn.commit()

            return {
                "success": True,
                "message": f"已为医生 {doctor['Name']} 添加 {exception_type}",
                "exception_uuid": exception_uuid
            }

        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"添加例外失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    def get_schedule_exceptions(
        self,
        doctor_uuid: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, any]:
        """
        查询医生的排班例外

        Args:
            doctor_uuid: 医生UUID
            start_date: 查询起始日期（可选）
            end_date: 查询结束日期（可选）

        Returns:
            {"success": bool, "exceptions": List[Dict]}
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            sql = """
                SELECT Exception_UUID, Exception_Date, Exception_Type, Is_Full_Day,
                       Start_Time, End_Time, Reason
                FROM doctor_schedule_exceptions
                WHERE Doctor_UUID = %s
            """
            params = [doctor_uuid]

            if start_date:
                sql += " AND Exception_Date >= %s"
                params.append(start_date)

            if end_date:
                sql += " AND Exception_Date <= %s"
                params.append(end_date)

            sql += " ORDER BY Exception_Date"

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            exceptions = []
            for row in rows:
                exceptions.append({
                    "exception_uuid": row['Exception_UUID'],
                    "exception_date": str(row['Exception_Date']),
                    "exception_type": row['Exception_Type'],
                    "is_full_day": bool(row['Is_Full_Day']),
                    "start_time": str(row['Start_Time']) if row['Start_Time'] else None,
                    "end_time": str(row['End_Time']) if row['End_Time'] else None,
                    "reason": row['Reason']
                })

            return {"success": True, "exceptions": exceptions}

        except Exception as e:
            return {"success": False, "message": f"查询失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    def delete_schedule_exception(self, exception_uuid: str) -> Dict[str, any]:
        """删除排班例外"""
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            sql = "DELETE FROM doctor_schedule_exceptions WHERE Exception_UUID = %s"
            cursor.execute(sql, (exception_uuid,))
            conn.commit()

            if cursor.rowcount > 0:
                return {"success": True, "message": f"已删除例外记录 UUID {exception_uuid}"}
            else:
                return {"success": False, "message": f"例外记录 UUID {exception_uuid} 不存在"}

        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"删除失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    # ========================================
    # 3. 医生配置管理
    # ========================================

    def update_doctor_capacity(
        self,
        doctor_uuid: str,
        max_patients_per_slot: int
    ) -> Dict[str, any]:
        """
        更新医生每时段接诊人数上限

        Args:
            doctor_uuid: 医生UUID
            max_patients_per_slot: 每时段最大患者数

        Returns:
            {"success": bool, "message": str}
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            if max_patients_per_slot <= 0:
                return {"success": False, "message": "接诊人数必须大于0"}

            sql = """
                UPDATE doctor
                SET default_max_patients_per_slot = %s,
                    Updated_At = CURRENT_TIMESTAMP
                WHERE Doctor_UUID = %s
            """
            cursor.execute(sql, (max_patients_per_slot, doctor_uuid))
            conn.commit()

            if cursor.rowcount > 0:
                return {
                    "success": True,
                    "message": f"已更新医生 UUID {doctor_uuid} 的接诊人数为 {max_patients_per_slot} 人/时段"
                }
            else:
                return {"success": False, "message": f"医生 UUID {doctor_uuid} 不存在"}

        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"更新失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    def update_slot_duration(
        self,
        doctor_uuid: str,
        duration_minutes: int
    ) -> Dict[str, any]:
        """
        更新医生的时间段时长

        Args:
            doctor_uuid: 医生UUID
            duration_minutes: 时间段时长（分钟）

        Returns:
            {"success": bool, "message": str}
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            if duration_minutes not in [30, 60, 90, 120]:
                return {"success": False, "message": "时间段时长必须为 30/60/90/120 分钟"}

            sql = """
                UPDATE doctor
                SET default_slot_duration_minutes = %s,
                    Updated_At = CURRENT_TIMESTAMP
                WHERE Doctor_UUID = %s
            """
            cursor.execute(sql, (duration_minutes, doctor_uuid))
            conn.commit()

            if cursor.rowcount > 0:
                return {
                    "success": True,
                    "message": f"已更新医生 UUID {doctor_uuid} 的时间段时长为 {duration_minutes} 分钟"
                }
            else:
                return {"success": False, "message": f"医生 UUID {doctor_uuid} 不存在"}

        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"更新失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    def update_booking_window(
        self,
        doctor_uuid: str,
        window_days: int
    ) -> Dict[str, any]:
        """
        更新医生的预约开放天数

        Args:
            doctor_uuid: 医生UUID
            window_days: 预约开放天数（今天起往后几天）

        Returns:
            {"success": bool, "message": str}
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            if window_days < 1 or window_days > 30:
                return {"success": False, "message": "预约开放天数必须在 1-30 天之间"}

            sql = """
                UPDATE doctor
                SET booking_window_days = %s,
                    Updated_At = CURRENT_TIMESTAMP
                WHERE Doctor_UUID = %s
            """
            cursor.execute(sql, (window_days, doctor_uuid))
            conn.commit()

            if cursor.rowcount > 0:
                return {
                    "success": True,
                    "message": f"已更新医生 UUID {doctor_uuid} 的预约开放天数为 {window_days} 天"
                }
            else:
                return {"success": False, "message": f"医生 UUID {doctor_uuid} 不存在"}

        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"更新失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    # ========================================
    # 4. 辅助方法
    # ========================================

    def get_doctor_config(self, doctor_uuid: str) -> Optional[Dict[str, any]]:
        """
        获取医生的配置信息

        Returns:
            {
                "doctor_uuid": str,
                "name": str,
                "specialty": str,
                "slot_duration": int,  # 分钟
                "max_patients_per_slot": int,
                "booking_window_days": int,
                "is_active": bool
            }
        """
        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            sql = """
                SELECT Doctor_UUID, Name, Specialty, Title,
                       default_slot_duration_minutes, default_max_patients_per_slot,
                       booking_window_days, is_active
                FROM doctor
                WHERE Doctor_UUID = %s
            """
            cursor.execute(sql, (doctor_uuid,))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                "doctor_uuid": row['Doctor_UUID'],
                "name": row['Name'],
                "specialty": row['Specialty'],
                "title": row['Title'],
                "slot_duration": row['default_slot_duration_minutes'],
                "max_patients_per_slot": row['default_max_patients_per_slot'],
                "booking_window_days": row['booking_window_days'],
                "is_active": bool(row['is_active'])
            }

        except Exception as e:
            print(f"查询医生配置失败：{e}")
            return None
        finally:
            if conn:
                conn.close()
