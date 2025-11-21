"""
时间段管理服务 (Time Slot Service)
UUID版本 - 实时时间段查询、预约、释放

功能:
1. 查询可用时间段(带剩余名额)
2. 原子性预约时间段(带并发控制)
3. 释放时间段(取消预约)
4. 批量生成时间段
5. 调整特定时间段的容量

Created: 2025-11-19
Updated: 2025-11-21 (UUID迁移)
"""

from typing import List, Dict, Optional, Union
from datetime import datetime, date, time as dt_time, timedelta
from database.db_connection import DatabaseConnection
from database.base_service import BaseServiceWithUUID


class TimeSlotService(BaseServiceWithUUID):
    """时间段管理服务 - UUID版本"""

    def __init__(self):
        super().__init__()
        self.db = DatabaseConnection()

    # ========================================
    # 1. 时间段查询
    # ========================================

    def get_available_slots(
        self,
        doctor_uuid: Optional[str] = None,
        specialty: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        only_available: bool = True
    ) -> Dict[str, any]:
        """
        查询可用时间段

        Args:
            doctor_uuid: 医生UUID(可选,如果指定则只查此医生)
            specialty: 科室(可选,如果指定则查该科室所有医生)
            start_date: 查询起始日期(默认今天)
            end_date: 查询结束日期(默认今天+3天)
            only_available: 是否只显示有剩余名额的时间段

        Returns:
            {
                "success": bool,
                "slots": List[Dict],  # 时间段列表
                "total_count": int
            }
        """
        try:
            # 默认查询范围:今天到3天后
            if not start_date:
                start_date = date.today()
            if not end_date:
                end_date = start_date + timedelta(days=3)

            # 构建查询SQL
            sql = """
                SELECT
                    ts.Slot_UUID,
                    ts.Doctor_UUID,
                    d.Name AS doctor_name,
                    d.Title AS doctor_title,
                    d.Specialty,
                    ts.Slot_Date,
                    ts.Slot_Start_Time,
                    ts.Slot_End_Time,
                    ts.Max_Capacity,
                    ts.Current_Bookings,
                    (ts.Max_Capacity - ts.Current_Bookings) AS remaining_slots,
                    ts.Is_Available,
                    ts.Slot_Type
                FROM doctor_time_slots ts
                JOIN doctor d ON ts.Doctor_UUID = d.Doctor_UUID
                WHERE ts.Slot_Date >= %s AND ts.Slot_Date <= %s
            """
            params = [start_date, end_date]

            # 医生筛选
            if doctor_uuid:
                sql += " AND ts.Doctor_UUID = %s"
                params.append(doctor_uuid)

            # 科室筛选
            if specialty:
                sql += " AND d.Specialty = %s"
                params.append(specialty)

            # 只显示可用的
            if only_available:
                sql += " AND ts.Is_Available = TRUE AND ts.Current_Bookings < ts.Max_Capacity"

            sql += " ORDER BY ts.Slot_Date, ts.Slot_Start_Time, d.Title DESC"

            rows = self.db.execute_query(sql, params)

            slots = []
            for row in rows:
                # 合成完整的预约时间
                start_time = row['Slot_Start_Time']
                if isinstance(start_time, timedelta):
                    # 如果是timedelta,转换为time
                    total_seconds = int(start_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    start_time = dt_time(hours, minutes, seconds)

                appointment_datetime = datetime.combine(
                    row['Slot_Date'],
                    start_time
                )

                slots.append({
                    "slot_uuid": row['Slot_UUID'],
                    "doctor_uuid": row['Doctor_UUID'],
                    "doctor_name": row['doctor_name'],
                    "doctor_title": row['doctor_title'],
                    "specialty": row['Specialty'],
                    "slot_date": str(row['Slot_Date']),
                    "slot_start_time": str(row['Slot_Start_Time']),
                    "slot_end_time": str(row['Slot_End_Time']),
                    "appointment_datetime": appointment_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                    "max_capacity": row['Max_Capacity'],
                    "current_bookings": row['Current_Bookings'],
                    "remaining_slots": row['remaining_slots'],
                    "is_available": bool(row['Is_Available']),
                    "slot_type": row['Slot_Type']
                })

            return {
                "success": True,
                "slots": slots,
                "total_count": len(slots)
            }

        except Exception as e:
            return {"success": False, "message": f"查询时间段失败:{str(e)}", "slots": []}

    def check_slot_availability(self, slot_uuid: str) -> Dict[str, any]:
        """
        检查时间段是否可预约

        Args:
            slot_uuid: 时间段UUID

        Returns:
            {
                "success": bool,
                "available": bool,
                "remaining_slots": int,
                "message": str
            }
        """
        try:
            sql = """
                SELECT Max_Capacity, Current_Bookings, Is_Available,
                       Slot_Date, Slot_Start_Time
                FROM doctor_time_slots
                WHERE Slot_UUID = %s
            """
            row = self.db.execute_one(sql, (slot_uuid,))

            if not row:
                return {"success": False, "available": False, "message": "时间段不存在"}

            remaining = row['Max_Capacity'] - row['Current_Bookings']
            is_available = bool(row['Is_Available']) and remaining > 0

            # 检查时间是否已过期
            start_time = row['Slot_Start_Time']
            if isinstance(start_time, timedelta):
                total_seconds = int(start_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                start_time = dt_time(hours, minutes, seconds)

            slot_datetime = datetime.combine(row['Slot_Date'], start_time)
            if slot_datetime < datetime.now():
                return {
                    "success": True,
                    "available": False,
                    "remaining_slots": 0,
                    "message": "此时间段已过期"
                }

            if not is_available:
                if remaining <= 0:
                    message = "此时间段已约满"
                else:
                    message = "此时间段不可预约"
            else:
                message = f"可预约,剩余 {remaining} 个名额"

            return {
                "success": True,
                "available": is_available,
                "remaining_slots": remaining,
                "message": message
            }

        except Exception as e:
            return {"success": False, "available": False, "message": f"查询失败:{str(e)}"}

    # ========================================
    # 2. 时间段预约(原子性操作)
    # ========================================

    def reserve_slot(
        self,
        slot_uuid: str,
        patient_uuid: str,
        check_capacity: bool = True
    ) -> Dict[str, any]:
        """
        预约时间段(原子性操作,带行锁)

        Args:
            slot_uuid: 时间段UUID
            patient_uuid: 患者UUID
            check_capacity: 是否检查容量(默认True)

        Returns:
            {
                "success": bool,
                "message": str,
                "slot_info": Dict  # 时间段信息
            }
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            # 开始事务
            conn.begin()

            # 使用 SELECT FOR UPDATE 锁定行,防止并发冲突
            sql_lock = """
                SELECT Slot_UUID, Doctor_UUID, Slot_Date, Slot_Start_Time, Slot_End_Time,
                       Max_Capacity, Current_Bookings, Is_Available
                FROM doctor_time_slots
                WHERE Slot_UUID = %s
                FOR UPDATE
            """
            cursor.execute(sql_lock, (slot_uuid,))
            slot = cursor.fetchone()

            if not slot:
                conn.rollback()
                return {"success": False, "message": "时间段不存在"}

            # 检查是否可预约
            if check_capacity:
                if not slot['Is_Available']:
                    conn.rollback()
                    return {"success": False, "message": "此时间段不可预约"}

                if slot['Current_Bookings'] >= slot['Max_Capacity']:
                    conn.rollback()
                    return {"success": False, "message": "此时间段已约满"}

            # 检查时间是否已过期
            start_time = slot['Slot_Start_Time']
            if isinstance(start_time, timedelta):
                total_seconds = int(start_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                start_time = dt_time(hours, minutes, seconds)

            slot_datetime = datetime.combine(slot['Slot_Date'], start_time)
            if slot_datetime < datetime.now():
                conn.rollback()
                return {"success": False, "message": "此时间段已过期"}

            # 增加预约计数(由触发器自动完成,这里只是为了确认)
            # 实际的 current_bookings 增加会在创建 appointment 时由触发器完成

            conn.commit()

            return {
                "success": True,
                "message": f"成功预约时间段,剩余 {slot['Max_Capacity'] - slot['Current_Bookings'] - 1} 个名额",
                "slot_info": {
                    "slot_uuid": slot['Slot_UUID'],
                    "doctor_uuid": slot['Doctor_UUID'],
                    "slot_date": str(slot['Slot_Date']),
                    "slot_start_time": str(slot['Slot_Start_Time']),
                    "slot_end_time": str(slot['Slot_End_Time']),
                    "appointment_datetime": slot_datetime.strftime("%Y-%m-%d %H:%M:%S")
                }
            }

        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"预约失败:{str(e)}"}
        finally:
            cursor.close()

    def release_slot(self, slot_uuid: str) -> Dict[str, any]:
        """
        释放时间段(取消预约时调用)
        注意:实际的 current_bookings 减少由触发器自动完成

        Args:
            slot_uuid: 时间段UUID

        Returns:
            {"success": bool, "message": str}
        """
        try:
            # 验证时间段是否存在
            sql = "SELECT Slot_UUID, Current_Bookings FROM doctor_time_slots WHERE Slot_UUID = %s"
            slot = self.db.execute_one(sql, (slot_uuid,))

            if not slot:
                return {"success": False, "message": "时间段不存在"}

            # 注意:实际的 Current_Bookings 减少由触发器完成
            # 这里只是验证操作合法性

            return {
                "success": True,
                "message": f"时间段 {slot_uuid} 已释放"
            }

        except Exception as e:
            return {"success": False, "message": f"释放失败:{str(e)}"}

    # ========================================
    # 3. 时间段管理
    # ========================================

    def update_slot_capacity(
        self,
        slot_uuid: str,
        new_capacity: int
    ) -> Dict[str, any]:
        """
        调整特定时间段的容量

        Args:
            slot_uuid: 时间段UUID
            new_capacity: 新的容量上限

        Returns:
            {"success": bool, "message": str}
        """
        try:
            if new_capacity <= 0:
                return {"success": False, "message": "容量必须大于0"}

            # 检查当前预约数
            sql_check = "SELECT Current_Bookings FROM doctor_time_slots WHERE Slot_UUID = %s"
            row = self.db.execute_one(sql_check, (slot_uuid,))

            if not row:
                return {"success": False, "message": "时间段不存在"}

            if new_capacity < row['Current_Bookings']:
                return {
                    "success": False,
                    "message": f"新容量 {new_capacity} 小于当前已预约数 {row['Current_Bookings']},无法调整"
                }

            # 更新容量
            sql_update = """
                UPDATE doctor_time_slots
                SET Max_Capacity = %s, Updated_At = CURRENT_TIMESTAMP
                WHERE Slot_UUID = %s
            """
            self.db.execute_update(sql_update, (new_capacity, slot_uuid))

            return {
                "success": True,
                "message": f"已将时间段 {slot_uuid} 的容量调整为 {new_capacity}"
            }

        except Exception as e:
            return {"success": False, "message": f"更新失败:{str(e)}"}

    def set_slot_availability(
        self,
        slot_uuid: str,
        is_available: bool
    ) -> Dict[str, any]:
        """
        设置时间段是否可预约

        Args:
            slot_uuid: 时间段UUID
            is_available: 是否可预约

        Returns:
            {"success": bool, "message": str}
        """
        try:
            sql = """
                UPDATE doctor_time_slots
                SET Is_Available = %s, Updated_At = CURRENT_TIMESTAMP
                WHERE Slot_UUID = %s
            """
            self.db.execute_update(sql, (is_available, slot_uuid))

            status = "可预约" if is_available else "不可预约"
            return {"success": True, "message": f"已将时间段 {slot_uuid} 设置为{status}"}

        except Exception as e:
            return {"success": False, "message": f"更新失败:{str(e)}"}

    def delete_slot(self, slot_uuid: str) -> Dict[str, any]:
        """
        删除时间段(仅当没有预约时)

        Args:
            slot_uuid: 时间段UUID

        Returns:
            {"success": bool, "message": str}
        """
        try:
            # 检查是否有预约
            sql_check = "SELECT Current_Bookings FROM doctor_time_slots WHERE Slot_UUID = %s"
            row = self.db.execute_one(sql_check, (slot_uuid,))

            if not row:
                return {"success": False, "message": "时间段不存在"}

            if row['Current_Bookings'] > 0:
                return {
                    "success": False,
                    "message": f"此时间段已有 {row['Current_Bookings']} 个预约,无法删除"
                }

            # 删除时间段
            sql_delete = "DELETE FROM doctor_time_slots WHERE Slot_UUID = %s"
            self.db.execute_update(sql_delete, (slot_uuid,))

            return {"success": True, "message": f"已删除时间段 {slot_uuid}"}

        except Exception as e:
            return {"success": False, "message": f"删除失败:{str(e)}"}

    # ========================================
    # 4. 批量操作
    # ========================================

    def batch_create_slots(
        self,
        slots_data: List[Dict[str, any]]
    ) -> Dict[str, any]:
        """
        批量创建时间段

        Args:
            slots_data: 时间段数据列表,格式:
                [
                    {
                        "doctor_uuid": str,
                        "slot_date": date,
                        "slot_start_time": time,
                        "slot_end_time": time,
                        "max_capacity": int,
                        "slot_type": str  # 可选
                    },
                    ...
                ]

        Returns:
            {"success": bool, "message": str, "created_count": int}
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            created_count = 0

            for slot in slots_data:
                doctor_uuid = slot.get('doctor_uuid')
                slot_date = slot.get('slot_date')
                slot_start = slot.get('slot_start_time')
                slot_end = slot.get('slot_end_time')
                max_capacity = slot.get('max_capacity', 5)
                slot_type = slot.get('slot_type', '普通')

                if not all([doctor_uuid, slot_date, slot_start, slot_end]):
                    continue

                # 生成Slot UUID
                slot_uuid = self.generate_uuid()

                # 使用 INSERT IGNORE 跳过重复记录
                sql = """
                    INSERT INTO doctor_time_slots
                    (Slot_UUID, Doctor_UUID, Slot_Date, Slot_Start_Time, Slot_End_Time,
                     Max_Capacity, Current_Bookings, Is_Available, Slot_Type)
                    VALUES (%s, %s, %s, %s, %s, %s, 0, TRUE, %s)
                    ON DUPLICATE KEY UPDATE
                        Max_Capacity = VALUES(Max_Capacity),
                        Slot_Type = VALUES(Slot_Type)
                """
                cursor.execute(sql, (
                    slot_uuid, doctor_uuid, slot_date, slot_start, slot_end,
                    max_capacity, slot_type
                ))
                created_count += cursor.rowcount

            conn.commit()

            return {
                "success": True,
                "message": f"批量创建时间段完成",
                "created_count": created_count
            }

        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"批量创建失败:{str(e)}", "created_count": 0}
        finally:
            cursor.close()

    def get_slot_info(self, slot_uuid: str) -> Optional[Dict[str, any]]:
        """
        获取时间段详细信息

        Returns:
            {
                "slot_uuid": str,
                "doctor_uuid": str,
                "doctor_name": str,
                "slot_date": str,
                "slot_start_time": str,
                "slot_end_time": str,
                "max_capacity": int,
                "current_bookings": int,
                "remaining_slots": int,
                "is_available": bool
            }
        """
        try:
            sql = """
                SELECT
                    ts.Slot_UUID, ts.Doctor_UUID, d.Name AS doctor_name,
                    ts.Slot_Date, ts.Slot_Start_Time, ts.Slot_End_Time,
                    ts.Max_Capacity, ts.Current_Bookings, ts.Is_Available, ts.Slot_Type
                FROM doctor_time_slots ts
                JOIN doctor d ON ts.Doctor_UUID = d.Doctor_UUID
                WHERE ts.Slot_UUID = %s
            """
            row = self.db.execute_one(sql, (slot_uuid,))

            if not row:
                return None

            return {
                "slot_uuid": row['Slot_UUID'],
                "doctor_uuid": row['Doctor_UUID'],
                "doctor_name": row['doctor_name'],
                "slot_date": str(row['Slot_Date']),
                "slot_start_time": str(row['Slot_Start_Time']),
                "slot_end_time": str(row['Slot_End_Time']),
                "max_capacity": row['Max_Capacity'],
                "current_bookings": row['Current_Bookings'],
                "remaining_slots": row['Max_Capacity'] - row['Current_Bookings'],
                "is_available": bool(row['Is_Available']),
                "slot_type": row['Slot_Type']
            }

        except Exception as e:
            print(f"查询时间段信息失败:{e}")
            return None

    def close(self):
        """关闭数据库连接"""
        self.db.close()
