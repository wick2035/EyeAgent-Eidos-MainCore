"""
自动时间段生成器 (Schedule Generator)
根据医生的每周排班模板自动生成未来几天的可预约时间段

功能：
1. 根据 doctor_working_schedule 生成 doctor_time_slots
2. 考虑 doctor_schedule_exceptions（请假、节假日）
3. 支持自定义时间段时长和容量
4. 可作为定时任务运行

使用方法：
    # 为所有医生生成未来3天的时间段
    python -m utils.schedule_generator

    # 为特定医生生成
    python -m utils.schedule_generator --doctor_id 1 --days 7

Created: 2025-11-19
"""

import sys
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional
import logging

# 添加项目根目录到路径
sys.path.insert(0, 'D:\\Agent\\pythonProject1')

from database.db_connection import get_db_connection
from database.doctor_schedule_service import DoctorScheduleService
from database.time_slot_service import TimeSlotService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ScheduleGenerator:
    """时间段自动生成器"""

    def __init__(self):
        self.schedule_service = DoctorScheduleService()
        self.slot_service = TimeSlotService()

    def generate_slots_for_doctor(
        self,
        doctor_id: int,
        start_date: Optional[date] = None,
        days: int = 3
    ) -> Dict[str, any]:
        """
        为特定医生生成时间段

        Args:
            doctor_id: 医生ID
            start_date: 起始日期（默认今天）
            days: 生成天数（默认3天）

        Returns:
            {
                "success": bool,
                "message": str,
                "slots_created": int,
                "doctor_name": str
            }
        """
        if start_date is None:
            start_date = date.today()

        try:
            # 1. 获取医生配置
            doctor_config = self.schedule_service.get_doctor_config(doctor_id)
            if not doctor_config:
                return {"success": False, "message": f"医生ID {doctor_id} 不存在"}

            if not doctor_config['is_active']:
                return {"success": False, "message": f"医生 {doctor_config['name']} 已停职"}

            logger.info(f"开始为医生 {doctor_config['name']} 生成时间段，从 {start_date} 起 {days} 天")

            # 2. 获取医生的每周排班
            schedule_result = self.schedule_service.get_weekly_schedule(doctor_id)
            if not schedule_result['success'] or not schedule_result['schedule']:
                return {
                    "success": False,
                    "message": f"医生 {doctor_config['name']} 没有配置排班规则"
                }

            weekly_schedule = schedule_result['schedule']

            # 3. 获取排班例外（请假、节假日）
            end_date = start_date + timedelta(days=days - 1)
            exceptions_result = self.schedule_service.get_schedule_exceptions(
                doctor_id,
                start_date,
                end_date
            )
            exceptions = exceptions_result.get('exceptions', []) if exceptions_result['success'] else []

            # 将例外日期转为集合方便查询
            exception_dates = set()
            for exc in exceptions:
                if exc['is_full_day']:
                    exception_dates.add(exc['exception_date'])

            # 4. 逐日生成时间段
            slots_to_create = []
            current_date = start_date

            for _ in range(days):
                # 跳过例外日期
                if str(current_date) in exception_dates:
                    logger.info(f"跳过 {current_date}（医生请假/节假日）")
                    current_date += timedelta(days=1)
                    continue

                # 获取当天是星期几 (0=周日, 1=周一, ..., 6=周六)
                day_of_week = (current_date.weekday() + 1) % 7

                # 查找该星期几的排班规则
                day_schedules = [s for s in weekly_schedule
                                 if s['day_of_week'] == day_of_week and s['is_active']]

                if not day_schedules:
                    logger.debug(f"{current_date} ({['周日','周一','周二','周三','周四','周五','周六'][day_of_week]}) 无排班")
                    current_date += timedelta(days=1)
                    continue

                # 为每个班次生成时间段
                for schedule in day_schedules:
                    shift_start = datetime.strptime(schedule['shift_start_time'], "%H:%M:%S").time()
                    shift_end = datetime.strptime(schedule['shift_end_time'], "%H:%M:%S").time()

                    # 生成时间段
                    shift_slots = self._generate_slots_for_shift(
                        current_date,
                        shift_start,
                        shift_end,
                        doctor_config['slot_duration'],
                        doctor_config['max_patients_per_slot']
                    )

                    for slot in shift_slots:
                        slot['doctor_id'] = doctor_id

                    slots_to_create.extend(shift_slots)

                current_date += timedelta(days=1)

            # 5. 批量创建时间段
            if not slots_to_create:
                return {
                    "success": True,
                    "message": f"医生 {doctor_config['name']} 在此期间无可生成的时间段",
                    "slots_created": 0,
                    "doctor_name": doctor_config['name']
                }

            result = self.slot_service.batch_create_slots(slots_to_create)

            return {
                "success": result['success'],
                "message": f"医生 {doctor_config['name']} 时间段生成完成",
                "slots_created": result['created_count'],
                "doctor_name": doctor_config['name']
            }

        except Exception as e:
            logger.error(f"生成时间段失败：{e}")
            return {
                "success": False,
                "message": f"生成失败：{str(e)}"
            }

    def _generate_slots_for_shift(
        self,
        slot_date: date,
        shift_start: time,
        shift_end: time,
        slot_duration_minutes: int,
        max_capacity: int
    ) -> List[Dict]:
        """
        为单个班次生成时间段

        Args:
            slot_date: 日期
            shift_start: 班次开始时间
            shift_end: 班次结束时间
            slot_duration_minutes: 时间段时长（分钟）
            max_capacity: 每时段最大人数

        Returns:
            时间段列表
        """
        slots = []

        # 转换为 datetime 以便计算
        current_time = datetime.combine(slot_date, shift_start)
        end_time = datetime.combine(slot_date, shift_end)

        while current_time < end_time:
            slot_start_time = current_time.time()
            slot_end_time = (current_time + timedelta(minutes=slot_duration_minutes)).time()

            # 确保不超过班次结束时间
            if (current_time + timedelta(minutes=slot_duration_minutes)) > end_time:
                break

            slots.append({
                "slot_date": slot_date,
                "slot_start_time": slot_start_time,
                "slot_end_time": slot_end_time,
                "max_capacity": max_capacity,
                "slot_type": "普通"
            })

            current_time += timedelta(minutes=slot_duration_minutes)

        return slots

    def generate_slots_for_all_doctors(
        self,
        start_date: Optional[date] = None,
        days: int = 3
    ) -> Dict[str, any]:
        """
        为所有活跃医生生成时间段

        Args:
            start_date: 起始日期（默认今天）
            days: 生成天数（默认3天）

        Returns:
            {
                "success": bool,
                "message": str,
                "total_slots_created": int,
                "doctors_processed": int,
                "details": List[Dict]
            }
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 获取所有活跃医生
            sql = "SELECT Doctor_ID, Name FROM doctor WHERE is_active = TRUE"
            cursor.execute(sql)
            doctors = cursor.fetchall()

            if not doctors:
                return {
                    "success": False,
                    "message": "没有找到活跃的医生"
                }

            logger.info(f"找到 {len(doctors)} 位活跃医生，开始生成时间段...")

            total_slots = 0
            details = []

            for doctor in doctors:
                doctor_id = doctor['Doctor_ID']
                doctor_name = doctor['Name']

                result = self.generate_slots_for_doctor(doctor_id, start_date, days)
                total_slots += result.get('slots_created', 0)

                details.append({
                    "doctor_id": doctor_id,
                    "doctor_name": doctor_name,
                    "slots_created": result.get('slots_created', 0),
                    "success": result['success']
                })

                if result['success']:
                    logger.info(f"✓ {doctor_name}: {result.get('slots_created', 0)} 个时间段")
                else:
                    logger.warning(f"✗ {doctor_name}: {result.get('message', '失败')}")

            return {
                "success": True,
                "message": f"批量生成完成，共创建 {total_slots} 个时间段",
                "total_slots_created": total_slots,
                "doctors_processed": len(doctors),
                "details": details
            }

        except Exception as e:
            logger.error(f"批量生成失败：{e}")
            return {
                "success": False,
                "message": f"批量生成失败：{str(e)}"
            }
        finally:
            if conn:
                conn.close()


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='医生时间段自动生成工具')
    parser.add_argument('--doctor_id', type=int, help='医生ID（不指定则为所有医生生成）')
    parser.add_argument('--days', type=int, default=3, help='生成天数（默认3天）')
    parser.add_argument('--start_date', type=str, help='起始日期 YYYY-MM-DD（默认今天）')

    args = parser.parse_args()

    # 解析起始日期
    start_date = None
    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        except ValueError:
            print(f"日期格式错误：{args.start_date}，应为 YYYY-MM-DD")
            return

    generator = ScheduleGenerator()

    print("=" * 60)
    print("医生时间段自动生成工具")
    print("=" * 60)

    if args.doctor_id:
        # 为特定医生生成
        print(f"\n为医生 ID {args.doctor_id} 生成时间段...")
        result = generator.generate_slots_for_doctor(
            doctor_id=args.doctor_id,
            start_date=start_date,
            days=args.days
        )
    else:
        # 为所有医生生成
        print(f"\n为所有医生生成时间段...")
        result = generator.generate_slots_for_all_doctors(
            start_date=start_date,
            days=args.days
        )

    print("\n" + "=" * 60)
    print("生成结果：")
    print("=" * 60)
    print(f"状态: {'成功' if result['success'] else '失败'}")
    print(f"信息: {result['message']}")

    if 'total_slots_created' in result:
        print(f"总时间段数: {result['total_slots_created']}")
        print(f"处理医生数: {result['doctors_processed']}")
    elif 'slots_created' in result:
        print(f"时间段数: {result['slots_created']}")

    print("=" * 60)


if __name__ == '__main__':
    main()
