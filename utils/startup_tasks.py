"""
启动任务模块
处理应用启动时需要执行的任务：
1. 自动生成未来3天的医生时间段（已有则不生成）
2. 定时任务：每天0点自动生成时间段

Created: 2025-11-19
"""

import schedule
import time
import threading
from datetime import date
from utils.schedule_generator import ScheduleGenerator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_time_slots_for_next_days(days=3, check_existing=True):
    """
    生成未来几天的时间段
    
    Args:
        days: 生成天数（默认3天）
        check_existing: 是否检查已存在的时间段（默认True，已有则不重复生成）
    
    Returns:
        Dict with success status and message
    """
    try:
        logger.info(f"[启动任务] 开始生成未来 {days} 天的时间段...")
        
        generator = ScheduleGenerator()
        
        # 如果需要检查已存在的时间段
        if check_existing:
            from database.time_slot_service import TimeSlotService
            slot_service = TimeSlotService()
            
            # 检查今天是否已有时间段
            today = date.today()
            check_result = slot_service.get_available_slots(
                start_date=today,
                end_date=today,
                only_available=False
            )
            
            if check_result['success'] and check_result['total_count'] > 0:
                logger.info(f"[启动任务] 检测到已有时间段数据，跳过生成")
                return {
                    "success": True,
                    "message": "时间段已存在，无需生成",
                    "slots_created": 0
                }
        
        # 生成时间段
        result = generator.generate_slots_for_all_doctors(
            start_date=date.today(),
            days=days
        )
        
        if result['success']:
            logger.info(f"[启动任务] 成功生成 {result['total_slots_created']} 个时间段")
            return {
                "success": True,
                "message": f"成功生成 {result['total_slots_created']} 个时间段",
                "slots_created": result['total_slots_created']
            }
        else:
            logger.error(f"[启动任务] 生成时间段失败: {result.get('message')}")
            return result
            
    except Exception as e:
        logger.error(f"[启动任务] 生成时间段异常: {e}")
        return {
            "success": False,
            "message": f"生成失败: {str(e)}"
        }


def daily_generate_time_slots():
    """
    定时任务：每天生成时间段
    这个函数会被调度器调用
    """
    logger.info("[定时任务] 执行每日时间段生成...")
    result = generate_time_slots_for_next_days(days=3, check_existing=False)
    if result['success']:
        logger.info(f"[定时任务] 完成: {result['message']}")
    else:
        logger.error(f"[定时任务] 失败: {result['message']}")


def run_scheduler():
    """
    运行定时任务调度器
    在后台线程中运行
    """
    # 设置每天00:00执行
    schedule.every().day.at("00:00").do(daily_generate_time_slots)
    
    logger.info("[调度器] 定时任务已启动，每天00:00自动生成时间段")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次


def start_scheduler_in_background():
    """
    在后台线程中启动调度器
    """
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("[调度器] 后台线程已启动")


def on_startup():
    """
    应用启动时执行的任务
    1. 生成未来3天时间段（已有则跳过）
    2. 启动定时任务调度器
    """
    logger.info("=" * 60)
    logger.info("[启动任务] 执行应用启动初始化...")
    logger.info("=" * 60)
    
    # 任务1：生成时间段
    generate_time_slots_for_next_days(days=3, check_existing=True)
    
    # 任务2：启动定时调度器
    start_scheduler_in_background()
    
    logger.info("=" * 60)
    logger.info("[启动任务] 初始化完成")
    logger.info("=" * 60)


if __name__ == '__main__':
    # 测试启动任务
    on_startup()
    
    # 保持运行以测试定时任务
    print("启动任务测试运行中，按Ctrl+C退出...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n测试结束")

