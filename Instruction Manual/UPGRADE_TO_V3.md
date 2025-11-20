# 预约系统升级指南：V2 → V3

## 概述

本文档描述如何将医疗预约系统从 V2 升级到 V3。V3 引入了智能时间段管理系统，解决了 V2 中的以下问题：

### V2 存在的问题
- ❌ 医生可用时间存储在单个 TEXT 字段中，难以管理
- ❌ 无法限制每个时间段的预约人数
- ❌ 没有并发控制，可能导致超额预约
- ❌ 无法灵活调整医生排班
- ❌ 不支持请假、节假日管理

### V3 新特性
- ✅ 关系型时间段管理（`doctor_time_slots` 表）
- ✅ 每个时间段独立容量控制
- ✅ 数据库触发器自动管理预约计数
- ✅ 支持每周排班模板
- ✅ 支持排班例外（请假、节假日）
- ✅ 完整的管理 API
- ✅ 原子性预约操作（行锁保护）

---

## 升级前准备

### 1. 环境要求
- Python 3.8+
- MySQL 5.7+
- 已安装所有依赖（`requirements.txt`）

### 2. 备份数据库
```bash
# 方式1：使用 mysqldump
mysqldump -u root -p medical_db > backup_v2_$(date +%Y%m%d).sql

# 方式2：使用迁移脚本自动备份（推荐）
# 迁移脚本会自动创建备份
```

### 3. 检查现有数据
```sql
-- 检查医生数量
SELECT COUNT(*) FROM doctor;

-- 检查预约数量
SELECT COUNT(*) FROM appointment;

-- 检查医生的 Available_Time 格式
SELECT Doctor_ID, Name, Available_Time FROM doctor LIMIT 5;
```

---

## 升级步骤

### 方式一：自动迁移（推荐）

运行自动迁移脚本，会完成所有步骤：

```bash
cd D:\Agent\pythonProject1
python database/migrate_to_slot_system.py
```

脚本将执行：
1. 备份 V2 数据
2. 执行 V3 数据库架构
3. 为所有医生创建默认排班（周一至周五 9:00-12:00, 14:00-17:00）
4. 生成未来3天的时间段
5. 验证迁移结果

**输出示例：**
```
======================================================================
数据库迁移工具：V2 → V3（时间段管理系统）
======================================================================

[步骤 1/5] 备份 V2 数据...
✓ 备份完成：5 位医生数据已保存

[步骤 2/5] 执行 V3 数据库架构...
✓ V3 架构创建完成，执行了 48 条语句

[步骤 3/5] 创建默认排班规则...
✓ 张医生: 10 条排班规则
✓ 李医生: 10 条排班规则
...
✓ 为 5/5 位医生创建排班规则

[步骤 4/5] 生成初始时间段...
✓ 成功生成 150 个时间段

[步骤 5/5] 验证迁移结果...
验证项目：
  ✓ doctor表新字段
  ✓ doctor_working_schedule表
  ✓ doctor_time_slots表
  ✓ doctor_schedule_exceptions表
  ✓ 预约触发器
  ✓ 排班规则数据
  ✓ 时间段数据

✓ 所有验证项通过！
✓ 迁移成功完成！
```

### 方式二：手动迁移

#### 步骤1：执行 SQL 架构
```bash
mysql -u root -p medical_db < database/init_database_v3.sql
```

#### 步骤2：创建排班规则
```python
from database.doctor_schedule_service import DoctorScheduleService

service = DoctorScheduleService()

# 为医生ID=1创建排班
schedule_data = [
    {"day_of_week": 1, "shift_start_time": "09:00:00", "shift_end_time": "12:00:00", "is_active": True},
    {"day_of_week": 1, "shift_start_time": "14:00:00", "shift_end_time": "17:00:00", "is_active": True},
    # ... 重复周二至周五
]

service.create_weekly_schedule(doctor_id=1, schedule_data=schedule_data)
```

#### 步骤3：生成时间段
```bash
python -m utils.schedule_generator --days 3
```

---

## V3 数据库架构

### 新增表

#### 1. `doctor_working_schedule` - 每周排班模板
```sql
CREATE TABLE doctor_working_schedule (
    Schedule_ID INT PRIMARY KEY AUTO_INCREMENT,
    Doctor_ID INT NOT NULL,
    Day_of_Week TINYINT NOT NULL,  -- 0=周日, 1=周一, ..., 6=周六
    Shift_Start_Time TIME NOT NULL,
    Shift_End_Time TIME NOT NULL,
    Is_Active BOOLEAN DEFAULT TRUE,
    ...
);
```

**示例数据：**
| Schedule_ID | Doctor_ID | Day_of_Week | Shift_Start_Time | Shift_End_Time | Is_Active |
|-------------|-----------|-------------|------------------|----------------|-----------|
| 1           | 1         | 1 (周一)    | 09:00:00         | 12:00:00       | TRUE      |
| 2           | 1         | 1 (周一)    | 14:00:00         | 17:00:00       | TRUE      |

#### 2. `doctor_time_slots` - 具体时间段
```sql
CREATE TABLE doctor_time_slots (
    Slot_ID INT PRIMARY KEY AUTO_INCREMENT,
    Doctor_ID INT NOT NULL,
    Slot_Date DATE NOT NULL,
    Slot_Start_Time TIME NOT NULL,
    Slot_End_Time TIME NOT NULL,
    Max_Capacity INT NOT NULL DEFAULT 5,
    Current_Bookings INT NOT NULL DEFAULT 0,
    Is_Available BOOLEAN DEFAULT TRUE,
    ...
);
```

**示例数据：**
| Slot_ID | Doctor_ID | Slot_Date  | Slot_Start_Time | Max_Capacity | Current_Bookings | 剩余名额 |
|---------|-----------|------------|-----------------|--------------|------------------|----------|
| 101     | 1         | 2025-11-20 | 09:00:00        | 5            | 2                | 3        |
| 102     | 1         | 2025-11-20 | 10:00:00        | 5            | 5                | 0（已满）|

#### 3. `doctor_schedule_exceptions` - 请假/节假日
```sql
CREATE TABLE doctor_schedule_exceptions (
    Exception_ID INT PRIMARY KEY AUTO_INCREMENT,
    Doctor_ID INT NOT NULL,
    Exception_Date DATE NOT NULL,
    Exception_Type VARCHAR(20) NOT NULL,  -- 请假/节假日/临时调整
    Is_Full_Day BOOLEAN DEFAULT TRUE,
    ...
);
```

### 修改的表

#### `doctor` 表新增字段：
- `default_slot_duration_minutes` INT - 默认时间段时长（分钟）
- `default_max_patients_per_slot` INT - 默认每时段最大人数
- `booking_window_days` INT - 预约开放天数
- `is_active` BOOLEAN - 是否在职

**移除字段：**
- ~~`Available_Time` TEXT~~ ❌ 已废弃

#### `appointment` 表新增字段：
- `Time_Slot_ID` INT - 关联到 `doctor_time_slots`

**新增约束：**
- UNIQUE (Patient_ID, Appointment_Time) - 防止患者重复预约

### 数据库触发器

V3 新增3个触发器自动管理 `Current_Bookings`：

1. **`trg_appointment_insert`** - 创建预约时 +1
2. **`trg_appointment_update`** - 更新预约状态时调整
3. **`trg_appointment_delete`** - 删除预约时 -1

---

## 使用新系统

### 1. 使用 AppointmentServiceV3

```python
from database.appointment_service_v3 import AppointmentServiceV3

service = AppointmentServiceV3()

# 完整预约流程
patient_data = {
    "patient_info": {
        "name": "张三",
        "phone": "13800000001",
        "gender": "男",
        "age": 35
    },
    "chief_complaint": "眼睛干涩",
    "appointment": {
        "department": "眼科",
        "preferred_time": "明天上午",
        "urgency": "普通"
    }
}

result = service.process_appointment(patient_data)

if result['success']:
    print(f"预约成功！")
    print(f"医生：{result['appointment_details']['doctor_name']}")
    print(f"时间：{result['appointment_details']['appointment_time']}")
    print(f"剩余名额：{result['appointment_details']['remaining_slots']}")
```

### 2. 管理医生排班

```python
from database.doctor_schedule_service import DoctorScheduleService

service = DoctorScheduleService()

# 查询医生排班
schedule = service.get_weekly_schedule(doctor_id=1)
print(schedule['schedule'])

# 添加请假
service.add_schedule_exception(
    doctor_id=1,
    exception_date=date(2025, 12, 25),
    exception_type="节假日",
    is_full_day=True,
    reason="圣诞节"
)

# 调整接诊人数
service.update_doctor_capacity(doctor_id=1, max_patients_per_slot=8)
```

### 3. 生成时间段

```bash
# 为所有医生生成未来7天的时间段
python -m utils.schedule_generator --days 7

# 为特定医生生成
python -m utils.schedule_generator --doctor_id 1 --days 7 --start_date 2025-11-20
```

**建议设置定时任务：**
```bash
# Linux/Mac (crontab)
0 0 * * * cd /path/to/project && python -m utils.schedule_generator --days 3

# Windows (任务计划程序)
创建每日任务，执行上述命令
```

### 4. 管理 API 使用

在 `main.py` 中添加：

```python
from api.admin_routes import admin_router

app.include_router(admin_router, prefix="/api/admin", tags=["管理"])
```

**API 端点示例：**

```bash
# 查询可用时间段
GET /api/admin/slots?doctor_id=1&start_date=2025-11-20&end_date=2025-11-22

# 设置医生排班
POST /api/admin/doctor/1/schedule
Content-Type: application/json

[
  {
    "day_of_week": 1,
    "shift_start_time": "09:00:00",
    "shift_end_time": "12:00:00",
    "is_active": true
  }
]

# 添加请假
POST /api/admin/doctor/1/exception
{
  "doctor_id": 1,
  "exception_date": "2025-12-25",
  "exception_type": "节假日",
  "is_full_day": true,
  "reason": "圣诞节"
}

# 调整时间段容量
PUT /api/admin/slots/101/capacity
{
  "new_capacity": 10
}
```

完整 API 文档：启动服务后访问 `http://localhost:8000/docs`

---

## 升级后验证

### 1. 检查数据完整性

```sql
-- 检查排班规则
SELECT d.Name, COUNT(*) as schedule_count
FROM doctor d
LEFT JOIN doctor_working_schedule dws ON d.Doctor_ID = dws.Doctor_ID
WHERE d.is_active = TRUE
GROUP BY d.Doctor_ID;

-- 检查时间段生成
SELECT d.Name, DATE(ts.Slot_Date) as date, COUNT(*) as slot_count
FROM doctor d
LEFT JOIN doctor_time_slots ts ON d.Doctor_ID = ts.Doctor_ID
GROUP BY d.Doctor_ID, DATE(ts.Slot_Date)
ORDER BY date, d.Name;

-- 检查触发器
SHOW TRIGGERS LIKE 'appointment';
```

### 2. 测试并发预约

```python
import threading
from database.appointment_service_v3 import AppointmentServiceV3

def book_appointment(patient_num):
    service = AppointmentServiceV3()
    patient_data = {
        "patient_info": {
            "name": f"测试患者{patient_num}",
            "phone": f"138000000{patient_num:02d}",
            "gender": "男",
            "age": 30
        },
        "chief_complaint": "测试",
        "appointment": {
            "department": "眼科",
            "preferred_time": "明天上午"
        }
    }

    result = service.process_appointment(patient_data)
    print(f"患者{patient_num}: {'成功' if result['success'] else '失败'} - {result['message']}")

# 同时预约10个患者
threads = []
for i in range(10):
    t = threading.Thread(target=book_appointment, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()
```

预期结果：
- 前5个患者预约成功（假设时间段容量为5）
- 后5个患者提示"已约满"

### 3. 验证数据一致性

```sql
-- 验证 current_bookings 是否准确
SELECT
    ts.Slot_ID,
    ts.Current_Bookings as recorded_count,
    COUNT(a.Appointment_ID) as actual_count,
    ts.Current_Bookings - COUNT(a.Appointment_ID) as diff
FROM doctor_time_slots ts
LEFT JOIN appointment a ON ts.Slot_ID = a.Time_Slot_ID
    AND a.Appointment_Status IN ('已预约', '已确认')
GROUP BY ts.Slot_ID
HAVING diff != 0;
```

如果有差异，执行修复：
```sql
UPDATE doctor_time_slots ts
SET Current_Bookings = (
    SELECT COUNT(*)
    FROM appointment a
    WHERE a.Time_Slot_ID = ts.Slot_ID
      AND a.Appointment_Status IN ('已预约', '已确认')
);
```

---

## 回滚方案

如果升级后发现问题，可以回滚到 V2：

```bash
# 使用备份恢复
mysql -u root -p medical_db < backup_v2_YYYYMMDD.sql

# 或使用迁移脚本生成的备份
mysql -u root -p medical_db < database/backup/backup_v2_TIMESTAMP.sql
```

**注意：** 回滚会丢失升级后创建的所有预约数据！

---

## 常见问题

### Q1: 迁移失败怎么办？
**A:** 检查错误信息，使用备份恢复，修复问题后重新迁移。常见原因：
- 数据库版本不兼容
- 缺少必要权限
- 现有数据格式异常

### Q2: 如何调整默认排班？
**A:** 使用管理 API 或直接调用服务：
```python
service.delete_schedule(schedule_id)  # 删除旧规则
service.create_weekly_schedule(doctor_id, new_schedule)  # 创建新规则
```

### Q3: 时间段没有自动生成？
**A:** 检查：
1. 医生是否有排班规则
2. 医生是否 `is_active = TRUE`
3. 是否有例外日期冲突
4. 手动运行 `schedule_generator.py`

### Q4: 并发预约仍然冲突？
**A:** 检查：
1. 触发器是否正确创建（`SHOW TRIGGERS`）
2. 事务隔离级别（建议 REPEATABLE READ）
3. 数据库锁等待超时设置

### Q5: 如何批量导入医生排班？
**A:** 准备 CSV 或 JSON 文件，使用脚本批量导入：
```python
import json
from database.doctor_schedule_service import DoctorScheduleService

with open('schedules.json', 'r', encoding='utf-8') as f:
    schedules = json.load(f)

service = DoctorScheduleService()
for doctor_schedule in schedules:
    service.create_weekly_schedule(
        doctor_id=doctor_schedule['doctor_id'],
        schedule_data=doctor_schedule['rules']
    )
```

---

## 性能优化建议

### 1. 数据库索引
V3 已自动创建必要索引，如需进一步优化：

```sql
-- 为高频查询添加复合索引
CREATE INDEX idx_slot_doctor_date_available
ON doctor_time_slots(Doctor_ID, Slot_Date, Is_Available);

-- 为预约时间范围查询优化
CREATE INDEX idx_appointment_time_status
ON appointment(Appointment_Time, Appointment_Status);
```

### 2. 定期清理过期时间段
```sql
-- 删除超过30天的过期时间段
DELETE FROM doctor_time_slots
WHERE Slot_Date < DATE_SUB(CURDATE(), INTERVAL 30 DAY)
  AND Current_Bookings = 0;
```

### 3. 缓存热点数据
对频繁查询的时间段，可使用 Redis 缓存：

```python
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

# 缓存时间段查询结果
cache_key = f"slots:doctor_{doctor_id}:date_{date_str}"
cached_data = redis_client.get(cache_key)

if cached_data:
    slots = json.loads(cached_data)
else:
    slots = slot_service.get_available_slots(...)
    redis_client.setex(cache_key, 300, json.dumps(slots))  # 5分钟过期
```

---

## 技术支持

遇到问题？查看：

1. **日志文件** - 检查应用日志了解详细错误
2. **数据库日志** - MySQL错误日志
3. **源代码** - 查看各服务的注释和文档字符串

**联系方式：**
- GitHub Issues: [项目地址]
- 邮件支持: [邮箱地址]

---

## 附录

### A. 完整文件列表

**新增文件：**
```
database/
  ├── init_database_v3.sql           # V3 数据库架构
  ├── doctor_schedule_service.py     # 排班管理服务
  ├── time_slot_service.py           # 时间段管理服务
  ├── appointment_service_v3.py      # 预约服务 V3
  └── migrate_to_slot_system.py      # 迁移脚本

utils/
  └── schedule_generator.py          # 时间段生成工具

api/
  └── admin_routes.py                # 管理 API 路由
```

**保留文件（兼容性）：**
```
database/
  ├── init_database_v2.sql           # V2 架构（参考）
  └── appointment_service_v2.py      # V2 服务（保留）
```

### B. 数据库架构对比

| 功能 | V2 | V3 |
|------|----|----|
| 医生可用时间 | TEXT 字段 | 关系型表 |
| 容量管理 | ❌ 无 | ✅ 精确控制 |
| 并发安全 | ❌ 无保护 | ✅ 行锁+触发器 |
| 排班管理 | ❌ 手动SQL | ✅ 完整API |
| 请假管理 | ❌ 无 | ✅ 支持 |
| 时间段生成 | ❌ 手动 | ✅ 自动化 |

### C. API 端点完整列表

见 `api/admin_routes.py` 或访问 `/docs` 查看交互式文档。

---

**升级文档版本：** V1.0
**最后更新：** 2025-11-19
**适用版本：** V2 → V3
