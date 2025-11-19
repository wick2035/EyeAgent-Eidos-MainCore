"""
管理员API路由 - V3 时间段管理系统

提供医生排班管理、时间段管理、容量调整等管理功能

使用方法：
    在 main.py 中引入：
    from api.admin_routes import admin_router
    app.include_router(admin_router, prefix="/api/admin")

Created: 2025-11-19
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, time

from database.doctor_schedule_service import DoctorScheduleService
from database.time_slot_service import TimeSlotService
from utils.schedule_generator import ScheduleGenerator


# 创建路由器
admin_router = APIRouter(tags=["管理员功能"])

# 初始化服务
schedule_service = DoctorScheduleService()
slot_service = TimeSlotService()
generator = ScheduleGenerator()


# ========================================
# Pydantic 模型定义
# ========================================

class ScheduleRule(BaseModel):
    """排班规则"""
    day_of_week: int = Field(..., ge=0, le=6, description="星期几（0=周日，1=周一，...，6=周六）")
    shift_start_time: str = Field(..., description="班次开始时间（HH:MM:SS）")
    shift_end_time: str = Field(..., description="班次结束时间（HH:MM:SS）")
    is_active: bool = Field(True, description="是否启用")


class WeeklyScheduleRequest(BaseModel):
    """每周排班请求"""
    doctor_id: int = Field(..., description="医生ID")
    schedules: List[ScheduleRule] = Field(..., description="排班规则列表")


class ScheduleException(BaseModel):
    """排班例外"""
    doctor_id: int = Field(..., description="医生ID")
    exception_date: str = Field(..., description="例外日期（YYYY-MM-DD）")
    exception_type: str = Field(..., description="例外类型（请假/节假日/临时调整）")
    is_full_day: bool = Field(True, description="是否全天")
    start_time: Optional[str] = Field(None, description="开始时间（HH:MM:SS）")
    end_time: Optional[str] = Field(None, description="结束时间（HH:MM:SS）")
    reason: Optional[str] = Field(None, description="原因说明")


class DoctorCapacityUpdate(BaseModel):
    """医生容量更新"""
    max_patients_per_slot: int = Field(..., gt=0, description="每时段最大患者数")


class SlotDurationUpdate(BaseModel):
    """时间段时长更新"""
    duration_minutes: int = Field(..., description="时间段时长（分钟）")


class BookingWindowUpdate(BaseModel):
    """预约窗口更新"""
    window_days: int = Field(..., ge=1, le=30, description="预约开放天数")


class SlotCapacityUpdate(BaseModel):
    """时间段容量更新"""
    new_capacity: int = Field(..., gt=0, description="新容量")


class SlotAvailabilityUpdate(BaseModel):
    """时间段可用性更新"""
    is_available: bool = Field(..., description="是否可预约")


class GenerateSlotsRequest(BaseModel):
    """生成时间段请求"""
    doctor_id: Optional[int] = Field(None, description="医生ID（不指定则为所有医生）")
    start_date: Optional[str] = Field(None, description="起始日期（YYYY-MM-DD）")
    days: int = Field(3, ge=1, le=30, description="生成天数")


# ========================================
# 医生排班管理
# ========================================

@admin_router.post("/doctor/{doctor_id}/schedule", summary="设置医生每周排班")
async def create_weekly_schedule(
    doctor_id: int,
    request: List[ScheduleRule]
):
    """
    为医生设置每周工作时间模板

    示例：
    ```json
    [
        {
            "day_of_week": 1,
            "shift_start_time": "09:00:00",
            "shift_end_time": "12:00:00",
            "is_active": true
        },
        {
            "day_of_week": 1,
            "shift_start_time": "14:00:00",
            "shift_end_time": "17:00:00",
            "is_active": true
        }
    ]
    ```
    """
    schedule_data = [rule.dict() for rule in request]
    result = schedule_service.create_weekly_schedule(doctor_id, schedule_data)

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@admin_router.get("/doctor/{doctor_id}/schedule", summary="查询医生排班")
async def get_weekly_schedule(doctor_id: int):
    """查询医生的每周排班模板"""
    result = schedule_service.get_weekly_schedule(doctor_id)

    if not result['success']:
        raise HTTPException(status_code=404, detail=result['message'])

    return result


@admin_router.delete("/schedule/{schedule_id}", summary="删除排班规则")
async def delete_schedule(schedule_id: int):
    """删除某个排班规则"""
    result = schedule_service.delete_schedule(schedule_id)

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@admin_router.put("/schedule/{schedule_id}/status", summary="启用/禁用排班规则")
async def update_schedule_status(
    schedule_id: int,
    is_active: bool = Query(..., description="是否启用")
):
    """启用或禁用某个排班规则"""
    result = schedule_service.update_schedule_status(schedule_id, is_active)

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


# ========================================
# 排班例外管理
# ========================================

@admin_router.post("/doctor/{doctor_id}/exception", summary="添加排班例外")
async def add_schedule_exception(
    doctor_id: int,
    request: ScheduleException
):
    """
    添加排班例外（请假、节假日、临时调整）

    示例：
    ```json
    {
        "doctor_id": 1,
        "exception_date": "2025-12-25",
        "exception_type": "节假日",
        "is_full_day": true,
        "reason": "圣诞节休息"
    }
    ```
    """
    from datetime import datetime

    try:
        exception_date = datetime.strptime(request.exception_date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

    start_time = None
    end_time = None
    if not request.is_full_day:
        if request.start_time and request.end_time:
            try:
                start_time = datetime.strptime(request.start_time, '%H:%M:%S').time()
                end_time = datetime.strptime(request.end_time, '%H:%M:%S').time()
            except ValueError:
                raise HTTPException(status_code=400, detail="时间格式错误，应为 HH:MM:SS")

    result = schedule_service.add_schedule_exception(
        doctor_id=doctor_id,
        exception_date=exception_date,
        exception_type=request.exception_type,
        is_full_day=request.is_full_day,
        start_time=start_time,
        end_time=end_time,
        reason=request.reason
    )

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@admin_router.get("/doctor/{doctor_id}/exceptions", summary="查询排班例外")
async def get_schedule_exceptions(
    doctor_id: int,
    start_date: Optional[str] = Query(None, description="起始日期（YYYY-MM-DD）"),
    end_date: Optional[str] = Query(None, description="结束日期（YYYY-MM-DD）")
):
    """查询医生的排班例外"""
    from datetime import datetime

    parsed_start = None
    parsed_end = None

    if start_date:
        try:
            parsed_start = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="起始日期格式错误")

    if end_date:
        try:
            parsed_end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="结束日期格式错误")

    result = schedule_service.get_schedule_exceptions(doctor_id, parsed_start, parsed_end)

    if not result['success']:
        raise HTTPException(status_code=404, detail=result['message'])

    return result


@admin_router.delete("/exception/{exception_id}", summary="删除排班例外")
async def delete_schedule_exception(exception_id: int):
    """删除排班例外"""
    result = schedule_service.delete_schedule_exception(exception_id)

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


# ========================================
# 医生配置管理
# ========================================

@admin_router.put("/doctor/{doctor_id}/capacity", summary="更新医生接诊容量")
async def update_doctor_capacity(
    doctor_id: int,
    request: DoctorCapacityUpdate
):
    """更新医生每时段接诊人数上限"""
    result = schedule_service.update_doctor_capacity(
        doctor_id,
        request.max_patients_per_slot
    )

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@admin_router.put("/doctor/{doctor_id}/slot-duration", summary="更新时间段时长")
async def update_slot_duration(
    doctor_id: int,
    request: SlotDurationUpdate
):
    """更新医生的时间段时长"""
    result = schedule_service.update_slot_duration(
        doctor_id,
        request.duration_minutes
    )

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@admin_router.put("/doctor/{doctor_id}/booking-window", summary="更新预约窗口")
async def update_booking_window(
    doctor_id: int,
    request: BookingWindowUpdate
):
    """更新医生的预约开放天数"""
    result = schedule_service.update_booking_window(
        doctor_id,
        request.window_days
    )

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@admin_router.get("/doctor/{doctor_id}/config", summary="查询医生配置")
async def get_doctor_config(doctor_id: int):
    """获取医生的配置信息"""
    config = schedule_service.get_doctor_config(doctor_id)

    if not config:
        raise HTTPException(status_code=404, detail="医生不存在")

    return config


# ========================================
# 时间段管理
# ========================================

@admin_router.get("/slots", summary="查询时间段")
async def get_available_slots(
    doctor_id: Optional[int] = Query(None, description="医生ID"),
    specialty: Optional[str] = Query(None, description="科室"),
    start_date: Optional[str] = Query(None, description="起始日期（YYYY-MM-DD）"),
    end_date: Optional[str] = Query(None, description="结束日期（YYYY-MM-DD）"),
    only_available: bool = Query(True, description="仅显示可用时间段")
):
    """查询时间段（支持多种筛选条件）"""
    from datetime import datetime

    parsed_start = None
    parsed_end = None

    if start_date:
        try:
            parsed_start = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="起始日期格式错误")

    if end_date:
        try:
            parsed_end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="结束日期格式错误")

    result = slot_service.get_available_slots(
        doctor_id=doctor_id,
        specialty=specialty,
        start_date=parsed_start,
        end_date=parsed_end,
        only_available=only_available
    )

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@admin_router.put("/slots/{slot_id}/capacity", summary="调整时间段容量")
async def update_slot_capacity(
    slot_id: int,
    request: SlotCapacityUpdate
):
    """调整特定时间段的容量上限"""
    result = slot_service.update_slot_capacity(slot_id, request.new_capacity)

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@admin_router.put("/slots/{slot_id}/availability", summary="设置时间段可用性")
async def set_slot_availability(
    slot_id: int,
    request: SlotAvailabilityUpdate
):
    """设置时间段是否可预约"""
    result = slot_service.set_slot_availability(slot_id, request.is_available)

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@admin_router.delete("/slots/{slot_id}", summary="删除时间段")
async def delete_slot(slot_id: int):
    """删除时间段（仅当没有预约时）"""
    result = slot_service.delete_slot(slot_id)

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@admin_router.get("/slots/{slot_id}", summary="查询时间段详情")
async def get_slot_info(slot_id: int):
    """获取时间段详细信息"""
    info = slot_service.get_slot_info(slot_id)

    if not info:
        raise HTTPException(status_code=404, detail="时间段不存在")

    return info


# ========================================
# 时间段生成
# ========================================

@admin_router.post("/slots/generate", summary="生成时间段")
async def generate_time_slots(request: GenerateSlotsRequest):
    """
    手动触发时间段生成

    示例：
    ```json
    {
        "doctor_id": 1,
        "start_date": "2025-11-20",
        "days": 7
    }
    ```
    """
    from datetime import datetime

    parsed_start = None
    if request.start_date:
        try:
            parsed_start = datetime.strptime(request.start_date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误")

    if request.doctor_id:
        # 为特定医生生成
        result = generator.generate_slots_for_doctor(
            doctor_id=request.doctor_id,
            start_date=parsed_start,
            days=request.days
        )
    else:
        # 为所有医生生成
        result = generator.generate_slots_for_all_doctors(
            start_date=parsed_start,
            days=request.days
        )

    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


# ========================================
# 健康检查
# ========================================

@admin_router.get("/health", summary="健康检查")
async def health_check():
    """检查管理API服务状态"""
    return {
        "status": "healthy",
        "service": "Admin API V3",
        "timestamp": str(datetime.now())
    }
