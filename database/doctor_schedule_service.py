"""
医生排班管理服务 (Doctor Schedule Service)
V3 版本 - 支持灵活的排班管理和时间段生成

功能：
1. 创建和管理医生每周工作时间模板 (doctor_working_schedule)
2. 根据排班模板生成具体时间段 (doctor_time_slots)
3. 管理排班例外情况（请假、节假日等）
4. 调整医生接诊容量和时间段配置
5. 查询医生可用时间段

Created: 2025-11-19
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, date, time, timedelta
import pymysql
from database.db_connection import get_db_connection


class DoctorScheduleService:
    """医生排班管理服务"""

    def __init__(self):
        pass

    # ========================================
    # 1. 每周排班模板管理
    # ========================================

    def create_weekly_schedule(
        self,
        doctor_id: int,
        schedule_data: List[Dict[str, any]]
    ) -> Dict[str, any]:
        """
        创建医生的每周工作时间模板

        Args:
            doctor_id: 医生ID
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
            conn = get_db_connection()
            cursor = conn.cursor()

            # 验证医生是否存在
            cursor.execute("SELECT Name FROM doctor WHERE Doctor_ID = %s", (doctor_id,))
            doctor = cursor.fetchone()
            if not doctor:
                return {"success": False, "message": f"医生ID {doctor_id} 不存在"}

            created_count = 0

            for schedule in schedule_data:
                day_of_week = schedule.get('day_of_week')
                shift_start = schedule.get('shift_start_time')
                shift_end = schedule.get('shift_end_time')
                is_active = schedule.get('is_active', True)

                # 验证必填字段
                if day_of_week is None or not shift_start or not shift_end:
                    continue

                # 插入排班记录（使用 ON DUPLICATE KEY UPDATE 处理重复）
                sql = """
                    INSERT INTO doctor_working_schedule
                    (Doctor_ID, Day_of_Week, Shift_Start_Time, Shift_End_Time, Is_Active)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        Shift_End_Time = VALUES(Shift_End_Time),
                        Is_Active = VALUES(Is_Active),
                        Updated_At = CURRENT_TIMESTAMP
                """
                cursor.execute(sql, (doctor_id, day_of_week, shift_start, shift_end, is_active))
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

    def get_weekly_schedule(self, doctor_id: int) -> Dict[str, any]:
        """
        获取医生的每周排班模板

        Args:
            doctor_id: 医生ID

        Returns:
            {
                "success": bool,
                "schedule": List[Dict],  # 排班列表
                "doctor_name": str
            }
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 获取医生信息
            cursor.execute("SELECT Name FROM doctor WHERE Doctor_ID = %s", (doctor_id,))
            doctor = cursor.fetchone()
            if not doctor:
                return {"success": False, "message": f"医生ID {doctor_id} 不存在"}

            # 获取排班记录
            sql = """
                SELECT Schedule_ID, Day_of_Week, Shift_Start_Time, Shift_End_Time, Is_Active
                FROM doctor_working_schedule
                WHERE Doctor_ID = %s
                ORDER BY Day_of_Week, Shift_Start_Time
            """
            cursor.execute(sql, (doctor_id,))
            rows = cursor.fetchall()

            schedule_list = []
            day_names = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

            for row in rows:
                schedule_list.append({
                    "schedule_id": row['Schedule_ID'],
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
        schedule_id: int,
        is_active: bool
    ) -> Dict[str, any]:
        """
        启用或禁用某个排班规则

        Args:
            schedule_id: 排班ID
            is_active: 是否启用

        Returns:
            {"success": bool, "message": str}
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            sql = """
                UPDATE doctor_working_schedule
                SET Is_Active = %s, Updated_At = CURRENT_TIMESTAMP
                WHERE Schedule_ID = %s
            """
            cursor.execute(sql, (is_active, schedule_id))
            conn.commit()

            status = "启用" if is_active else "禁用"
            return {"success": True, "message": f"已{status}排班规则 ID {schedule_id}"}

        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"更新失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    def delete_schedule(self, schedule_id: int) -> Dict[str, any]:
        """
        删除某个排班规则

        Args:
            schedule_id: 排班ID

        Returns:
            {"success": bool, "message": str}
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            sql = "DELETE FROM doctor_working_schedule WHERE Schedule_ID = %s"
            cursor.execute(sql, (schedule_id,))
            conn.commit()

            if cursor.rowcount > 0:
                return {"success": True, "message": f"已删除排班规则 ID {schedule_id}"}
            else:
                return {"success": False, "message": f"排班规则 ID {schedule_id} 不存在"}

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
        doctor_id: int,
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
            doctor_id: 医生ID
            exception_date: 例外日期
            exception_type: 类型（"请假"/"节假日"/"临时调整"）
            is_full_day: 是否全天
            start_time: 开始时间（如果是部分时间）
            end_time: 结束时间（如果是部分时间）
            reason: 原因说明

        Returns:
            {"success": bool, "message": str, "exception_id": int}
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 验证医生是否存在
            cursor.execute("SELECT Name FROM doctor WHERE Doctor_ID = %s", (doctor_id,))
            doctor = cursor.fetchone()
            if not doctor:
                return {"success": False, "message": f"医生ID {doctor_id} 不存在"}

            sql = """
                INSERT INTO doctor_schedule_exceptions
                (Doctor_ID, Exception_Date, Exception_Type, Is_Full_Day,
                 Start_Time, End_Time, Reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                doctor_id, exception_date, exception_type, is_full_day,
                start_time, end_time, reason
            ))
            conn.commit()

            exception_id = cursor.lastrowid

            return {
                "success": True,
                "message": f"已为医生 {doctor['Name']} 添加 {exception_type}",
                "exception_id": exception_id
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
        doctor_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, any]:
        """
        查询医生的排班例外

        Args:
            doctor_id: 医生ID
            start_date: 查询起始日期（可选）
            end_date: 查询结束日期（可选）

        Returns:
            {"success": bool, "exceptions": List[Dict]}
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            sql = """
                SELECT Exception_ID, Exception_Date, Exception_Type, Is_Full_Day,
                       Start_Time, End_Time, Reason
                FROM doctor_schedule_exceptions
                WHERE Doctor_ID = %s
            """
            params = [doctor_id]

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
                    "exception_id": row['Exception_ID'],
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

    def delete_schedule_exception(self, exception_id: int) -> Dict[str, any]:
        """删除排班例外"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            sql = "DELETE FROM doctor_schedule_exceptions WHERE Exception_ID = %s"
            cursor.execute(sql, (exception_id,))
            conn.commit()

            if cursor.rowcount > 0:
                return {"success": True, "message": f"已删除例外记录 ID {exception_id}"}
            else:
                return {"success": False, "message": f"例外记录 ID {exception_id} 不存在"}

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
        doctor_id: int,
        max_patients_per_slot: int
    ) -> Dict[str, any]:
        """
        更新医生每时段接诊人数上限

        Args:
            doctor_id: 医生ID
            max_patients_per_slot: 每时段最大患者数

        Returns:
            {"success": bool, "message": str}
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            if max_patients_per_slot <= 0:
                return {"success": False, "message": "接诊人数必须大于0"}

            sql = """
                UPDATE doctor
                SET default_max_patients_per_slot = %s,
                    Updated_At = CURRENT_TIMESTAMP
                WHERE Doctor_ID = %s
            """
            cursor.execute(sql, (max_patients_per_slot, doctor_id))
            conn.commit()

            if cursor.rowcount > 0:
                return {
                    "success": True,
                    "message": f"已更新医生 ID {doctor_id} 的接诊人数为 {max_patients_per_slot} 人/时段"
                }
            else:
                return {"success": False, "message": f"医生 ID {doctor_id} 不存在"}

        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"更新失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    def update_slot_duration(
        self,
        doctor_id: int,
        duration_minutes: int
    ) -> Dict[str, any]:
        """
        更新医生的时间段时长

        Args:
            doctor_id: 医生ID
            duration_minutes: 时间段时长（分钟）

        Returns:
            {"success": bool, "message": str}
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            if duration_minutes not in [30, 60, 90, 120]:
                return {"success": False, "message": "时间段时长必须为 30/60/90/120 分钟"}

            sql = """
                UPDATE doctor
                SET default_slot_duration_minutes = %s,
                    Updated_At = CURRENT_TIMESTAMP
                WHERE Doctor_ID = %s
            """
            cursor.execute(sql, (duration_minutes, doctor_id))
            conn.commit()

            if cursor.rowcount > 0:
                return {
                    "success": True,
                    "message": f"已更新医生 ID {doctor_id} 的时间段时长为 {duration_minutes} 分钟"
                }
            else:
                return {"success": False, "message": f"医生 ID {doctor_id} 不存在"}

        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"更新失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    def update_booking_window(
        self,
        doctor_id: int,
        window_days: int
    ) -> Dict[str, any]:
        """
        更新医生的预约开放天数

        Args:
            doctor_id: 医生ID
            window_days: 预约开放天数（今天起往后几天）

        Returns:
            {"success": bool, "message": str}
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            if window_days < 1 or window_days > 30:
                return {"success": False, "message": "预约开放天数必须在 1-30 天之间"}

            sql = """
                UPDATE doctor
                SET booking_window_days = %s,
                    Updated_At = CURRENT_TIMESTAMP
                WHERE Doctor_ID = %s
            """
            cursor.execute(sql, (window_days, doctor_id))
            conn.commit()

            if cursor.rowcount > 0:
                return {
                    "success": True,
                    "message": f"已更新医生 ID {doctor_id} 的预约开放天数为 {window_days} 天"
                }
            else:
                return {"success": False, "message": f"医生 ID {doctor_id} 不存在"}

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

    def get_doctor_config(self, doctor_id: int) -> Optional[Dict[str, any]]:
        """
        获取医生的配置信息

        Returns:
            {
                "doctor_id": int,
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
            conn = get_db_connection()
            cursor = conn.cursor()

            sql = """
                SELECT Doctor_ID, Name, Specialty, Title,
                       default_slot_duration_minutes, default_max_patients_per_slot,
                       booking_window_days, is_active
                FROM doctor
                WHERE Doctor_ID = %s
            """
            cursor.execute(sql, (doctor_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                "doctor_id": row['Doctor_ID'],
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
