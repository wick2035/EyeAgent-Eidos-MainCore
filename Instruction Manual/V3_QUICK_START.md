# V3 预约系统快速开始指南

本文档提供 V3 预约系统的快速上手步骤。

---

## 🚀 快速开始（3分钟）

### 步骤1：执行数据库迁移

```bash
cd D:\Agent\pythonProject1
python database/migrate_to_slot_system.py
```

按提示输入 `yes` 确认。脚本将自动完成所有设置。

### 步骤2：生成时间段

```bash
python -m utils.schedule_generator --days 7
```

### 步骤3：启动服务

```bash
python main.py
```

访问 http://localhost:8000/docs 查看 API 文档。

---

## 📋 核心功能清单

### ✅ 已实现功能

| 功能 | 文件 | 说明 |
|------|------|------|
| **数据库架构 V3** | `database/init_database_v3.sql` | 新增3个表+触发器 |
| **排班管理服务** | `database/doctor_schedule_service.py` | 医生排班CRUD |
| **时间段管理服务** | `database/time_slot_service.py` | 时间段查询/预约/释放 |
| **预约服务 V3** | `database/appointment_service_v3.py` | 基于时间段的预约 |
| **时间段生成器** | `utils/schedule_generator.py` | 自动生成时间段 |
| **数据迁移脚本** | `database/migrate_to_slot_system.py` | V2→V3 自动迁移 |
| **管理 API** | `api/admin_routes.py` | RESTful 管理接口 |

---

## 🔧 常用操作

### 1. 管理医生排班

**查询医生排班：**
```bash
curl http://localhost:8000/api/admin/doctor/1/schedule
```

**设置排班（周一至周五 9:00-12:00, 14:00-17:00）：**
```bash
curl -X POST http://localhost:8000/api/admin/doctor/1/schedule \
  -H "Content-Type: application/json" \
  -d '[
    {"day_of_week": 1, "shift_start_time": "09:00:00", "shift_end_time": "12:00:00", "is_active": true},
    {"day_of_week": 1, "shift_start_time": "14:00:00", "shift_end_time": "17:00:00", "is_active": true},
    {"day_of_week": 2, "shift_start_time": "09:00:00", "shift_end_time": "12:00:00", "is_active": true},
    {"day_of_week": 2, "shift_start_time": "14:00:00", "shift_end_time": "17:00:00", "is_active": true},
    {"day_of_week": 3, "shift_start_time": "09:00:00", "shift_end_time": "12:00:00", "is_active": true},
    {"day_of_week": 3, "shift_start_time": "14:00:00", "shift_end_time": "17:00:00", "is_active": true},
    {"day_of_week": 4, "shift_start_time": "09:00:00", "shift_end_time": "12:00:00", "is_active": true},
    {"day_of_week": 4, "shift_start_time": "14:00:00", "shift_end_time": "17:00:00", "is_active": true},
    {"day_of_week": 5, "shift_start_time": "09:00:00", "shift_end_time": "12:00:00", "is_active": true},
    {"day_of_week": 5, "shift_start_time": "14:00:00", "shift_end_time": "17:00:00", "is_active": true}
  ]'
```

### 2. 添加请假/节假日

```bash
curl -X POST http://localhost:8000/api/admin/doctor/1/exception \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_id": 1,
    "exception_date": "2025-12-25",
    "exception_type": "节假日",
    "is_full_day": true,
    "reason": "圣诞节休息"
  }'
```

### 3. 调整医生容量

**每时段接诊人数：**
```bash
curl -X PUT http://localhost:8000/api/admin/doctor/1/capacity \
  -H "Content-Type: application/json" \
  -d '{"max_patients_per_slot": 8}'
```

**时间段时长：**
```bash
curl -X PUT http://localhost:8000/api/admin/doctor/1/slot-duration \
  -H "Content-Type: application/json" \
  -d '{"duration_minutes": 30}'
```

### 4. 查询可用时间段

```bash
# 查询眼科所有可用时间段
curl "http://localhost:8000/api/admin/slots?specialty=眼科&start_date=2025-11-20&end_date=2025-11-22"

# 查询特定医生的时间段
curl "http://localhost:8000/api/admin/slots?doctor_id=1&start_date=2025-11-20"
```

### 5. 手动生成时间段

```bash
# 为所有医生生成未来7天时间段
curl -X POST http://localhost:8000/api/admin/slots/generate \
  -H "Content-Type: application/json" \
  -d '{"days": 7}'

# 为特定医生生成
curl -X POST http://localhost:8000/api/admin/slots/generate \
  -H "Content-Type: application/json" \
  -d '{"doctor_id": 1, "start_date": "2025-11-20", "days": 7}'
```

---

## 📊 数据库查询示例

### 查看医生排班汇总
```sql
SELECT
    d.Doctor_ID,
    d.Name AS 医生,
    CASE dws.Day_of_Week
        WHEN 0 THEN '周日'
        WHEN 1 THEN '周一'
        WHEN 2 THEN '周二'
        WHEN 3 THEN '周三'
        WHEN 4 THEN '周四'
        WHEN 5 THEN '周五'
        WHEN 6 THEN '周六'
    END AS 星期,
    dws.Shift_Start_Time AS 开始时间,
    dws.Shift_End_Time AS 结束时间,
    dws.Is_Active AS 是否启用
FROM doctor d
LEFT JOIN doctor_working_schedule dws ON d.Doctor_ID = dws.Doctor_ID
WHERE d.is_active = TRUE
ORDER BY d.Doctor_ID, dws.Day_of_Week, dws.Shift_Start_Time;
```

### 查看今日可用时间段
```sql
SELECT
    d.Name AS 医生,
    d.Title AS 职称,
    ts.Slot_Start_Time AS 开始时间,
    ts.Slot_End_Time AS 结束时间,
    ts.Max_Capacity AS 总容量,
    ts.Current_Bookings AS 已预约,
    (ts.Max_Capacity - ts.Current_Bookings) AS 剩余名额
FROM doctor_time_slots ts
JOIN doctor d ON ts.Doctor_ID = d.Doctor_ID
WHERE ts.Slot_Date = CURDATE()
  AND ts.Is_Available = TRUE
  AND ts.Current_Bookings < ts.Max_Capacity
ORDER BY ts.Slot_Start_Time, d.Title DESC;
```

### 查看医生工作负载
```sql
SELECT
    d.Name AS 医生,
    DATE(ts.Slot_Date) AS 日期,
    COUNT(DISTINCT ts.Slot_ID) AS 时间段数,
    SUM(ts.Current_Bookings) AS 总预约数,
    SUM(ts.Max_Capacity) AS 总容量,
    ROUND(SUM(ts.Current_Bookings) / SUM(ts.Max_Capacity) * 100, 1) AS 利用率
FROM doctor d
LEFT JOIN doctor_time_slots ts ON d.Doctor_ID = ts.Doctor_ID
WHERE ts.Slot_Date >= CURDATE()
  AND ts.Slot_Date < DATE_ADD(CURDATE(), INTERVAL 7 DAY)
GROUP BY d.Doctor_ID, DATE(ts.Slot_Date)
ORDER BY 日期, 利用率 DESC;
```

---

## 🔍 故障排查

### 问题1：时间段没有生成

**检查步骤：**
```sql
-- 1. 检查医生是否有排班规则
SELECT d.Name, COUNT(dws.Schedule_ID) as rule_count
FROM doctor d
LEFT JOIN doctor_working_schedule dws ON d.Doctor_ID = dws.Doctor_ID
WHERE d.is_active = TRUE
GROUP BY d.Doctor_ID;

-- 2. 检查医生是否在职
SELECT Doctor_ID, Name, is_active FROM doctor;

-- 3. 检查是否有例外日期
SELECT * FROM doctor_schedule_exceptions
WHERE Exception_Date >= CURDATE()
ORDER BY Exception_Date;
```

**解决方案：**
```bash
# 为没有排班规则的医生创建默认排班
python -c "
from database.doctor_schedule_service import DoctorScheduleService
service = DoctorScheduleService()
# ... 创建排班代码
"

# 然后重新生成时间段
python -m utils.schedule_generator --days 7
```

### 问题2：预约计数不准确

**检查数据一致性：**
```sql
SELECT
    ts.Slot_ID,
    ts.Current_Bookings AS 记录数,
    COUNT(a.Appointment_ID) AS 实际数,
    ts.Current_Bookings - COUNT(a.Appointment_ID) AS 差异
FROM doctor_time_slots ts
LEFT JOIN appointment a ON ts.Slot_ID = a.Time_Slot_ID
    AND a.Appointment_Status IN ('已预约', '已确认')
GROUP BY ts.Slot_ID
HAVING 差异 != 0;
```

**修复数据：**
```sql
UPDATE doctor_time_slots ts
SET Current_Bookings = (
    SELECT COUNT(*)
    FROM appointment a
    WHERE a.Time_Slot_ID = ts.Slot_ID
      AND a.Appointment_Status IN ('已预约', '已确认')
);
```

### 问题3：触发器未生效

**检查触发器：**
```sql
SHOW TRIGGERS LIKE 'appointment';
```

**重新创建触发器：**
```bash
mysql -u root -p medical_db < database/init_database_v3.sql
```

---

## 📖 Python 代码示例

### 示例1：完整预约流程

```python
from database.appointment_service_v3 import AppointmentServiceV3

# 初始化服务
service = AppointmentServiceV3()

# 患者数据
patient_data = {
    "patient_info": {
        "name": "王小明",
        "phone": "13900001234",
        "gender": "男",
        "age": 45
    },
    "chief_complaint": "视力模糊，看东西不清楚",
    "present_illness": "近一周出现症状，逐渐加重",
    "medical_history": "有高血压病史",
    "allergy_history": "无过敏",
    "appointment": {
        "department": "眼科",
        "preferred_time": "后天上午",
        "urgency": "普通"
    }
}

# 处理预约
result = service.process_appointment(patient_data)

if result['success']:
    details = result['appointment_details']
    print(f"✓ 预约成功！")
    print(f"  患者：{details['patient_name']}")
    print(f"  医生：{details['doctor_name']} ({details['doctor_title']})")
    print(f"  时间：{details['appointment_time']}")
    print(f"  剩余名额：{details['remaining_slots']}")
else:
    print(f"✗ 预约失败：{result['message']}")
```

### 示例2：批量设置医生排班

```python
from database.doctor_schedule_service import DoctorScheduleService

service = DoctorScheduleService()

# 医生列表
doctors = [1, 2, 3, 4, 5]

# 标准排班：周一至周五 9:00-12:00, 14:00-17:00
standard_schedule = []
for day in range(1, 6):  # 1=周一, 5=周五
    standard_schedule.append({
        "day_of_week": day,
        "shift_start_time": "09:00:00",
        "shift_end_time": "12:00:00",
        "is_active": True
    })
    standard_schedule.append({
        "day_of_week": day,
        "shift_start_time": "14:00:00",
        "shift_end_time": "17:00:00",
        "is_active": True
    })

# 批量设置
for doctor_id in doctors:
    result = service.create_weekly_schedule(doctor_id, standard_schedule)
    if result['success']:
        print(f"✓ 医生 {doctor_id}: {result['created_count']} 条规则")
    else:
        print(f"✗ 医生 {doctor_id}: {result['message']}")
```

### 示例3：查询时间段并预约

```python
from database.time_slot_service import TimeSlotService
from database.appointment_service_v3 import AppointmentServiceV3
from datetime import date, timedelta

slot_service = TimeSlotService()
appointment_service = AppointmentServiceV3()

# 查询明天眼科的可用时间段
tomorrow = date.today() + timedelta(days=1)
result = slot_service.get_available_slots(
    specialty="眼科",
    start_date=tomorrow,
    end_date=tomorrow,
    only_available=True
)

if result['success'] and result['slots']:
    print(f"找到 {result['total_count']} 个可用时间段：\n")

    for idx, slot in enumerate(result['slots'][:5], 1):
        print(f"{idx}. {slot['doctor_name']} ({slot['doctor_title']})")
        print(f"   时间：{slot['appointment_datetime']}")
        print(f"   剩余：{slot['remaining_slots']} 个名额\n")

    # 选择第一个时间段预约
    selected_slot = result['slots'][0]

    patient_data = {
        "patient_info": {"name": "测试患者", "phone": "13800000000", "gender": "男", "age": 30},
        "chief_complaint": "测试预约",
        "appointment": {"department": "眼科", "urgency": "普通"}
    }

    # 创建病例和用户
    patient_id = appointment_service.create_or_get_patient(patient_data['patient_info'])
    record_id = appointment_service.create_medical_record(patient_id, patient_data)

    # 预约
    appt_result = appointment_service.create_appointment_v3(
        medical_record_id=record_id,
        patient_id=patient_id,
        slot_id=selected_slot['slot_id'],
        patient_data=patient_data
    )

    print(f"预约结果：{appt_result['message']}")
else:
    print("没有找到可用时间段")
```

---

## 🎯 下一步

1. **集成到 main.py**
   - 引入 `admin_routes`
   - 更新现有预约接口使用 `AppointmentServiceV3`

2. **设置定时任务**
   - 每天自动生成未来时间段
   - 定期清理过期时间段

3. **添加监控**
   - 预约成功率
   - 医生工作负载
   - 时间段利用率

4. **优化性能**
   - 添加 Redis 缓存
   - 优化数据库索引
   - 实现读写分离

---

## 📚 相关文档

- **[UPGRADE_TO_V3.md](UPGRADE_TO_V3.md)** - 完整升级指南
- **[CLAUDE.md](CLAUDE.md)** - 项目总体说明
- **API 文档** - http://localhost:8000/docs

---

**版本：** V1.0
**更新日期：** 2025-11-19
