# Agent3 提醒管理功能使用说明

## 功能概述

Agent3（ReminderAgent）是智能医疗咨询系统的第三个智能体，专门负责管理患者的各类健康提醒，包括：
- 🏥 复诊提醒
- 📅 预约提醒
- 💊 用药提醒
- 🔬 检查提醒
- 📝 自定义提醒

## 数据库架构

### 核心表结构

1. **reminder** - 提醒记录表
   - 存储所有类型的提醒信息
   - 支持关联到病例、预约、处方
   - 包含状态、优先级、重复类型等字段

2. **reminder_history** - 提醒历史表
   - 记录提醒的所有操作历史
   - 用于审计和追溯

3. **reminder_config** - 提醒配置表
   - 每个患者的个性化提醒设置
   - 免打扰时间、通知方式等

### 初始化数据库

```bash
# 在MySQL中执行SQL脚本
mysql -u root -p medical_db < database/reminder_schema.sql
```

或直接在MySQL客户端中执行 `database/reminder_schema.sql` 文件。

## 使用方法

### 1. 通过Agent对话使用

```python
from agents.agent_3 import ReminderAgent

# 创建Agent（推荐使用手机号）
agent = ReminderAgent(
    phone_number="13900000001",
    role="patient"  # 或 "doctor"
)

# 开始对话
response, is_completed = agent.chat("你好")
print(response)

response, is_completed = agent.chat("查看我的提醒")
print(response)
```

### 2. 通过API接口使用

#### 查看提醒列表

```bash
# 通过患者ID查询
GET /api/reminder/list/1?status=pending&limit=50

# 通过手机号查询
GET /api/reminder/list/phone/13900000001?status=pending
```

响应示例：
```json
{
  "success": true,
  "patient_id": 1,
  "count": 3,
  "reminders": [
    {
      "Reminder_ID": 1,
      "Reminder_Type": "follow_up",
      "Reminder_Title": "复诊提醒",
      "Scheduled_Time": "2025-11-24 00:00:00",
      "Status": "pending",
      "Priority": "high"
    }
  ]
}
```

#### 创建提醒

```bash
POST /api/reminder/create
Content-Type: application/json

{
  "patient_id": 1,
  "reminder_type": "follow_up",
  "reminder_title": "复诊提醒",
  "reminder_content": "您的复诊日期为2025年12月1日，请准时就诊。",
  "scheduled_time": "2025-12-01T09:00:00",
  "advance_days": 3,
  "priority": "high"
}
```

#### 更新提醒状态

```bash
POST /api/reminder/update
Content-Type: application/json

{
  "reminder_id": 1,
  "status": "completed"
}
```

#### 对话接口

```bash
POST /api/chat/reminder
Content-Type: application/json

{
  "message": "查看我的提醒",
  "phone_number": "13900000001",
  "role": "patient"
}
```

### 3. 直接使用数据库服务

```python
from database.reminder_service import ReminderService
from datetime import datetime, timedelta

service = ReminderService()

# 创建复诊提醒
result = service.create_follow_up_reminder(
    patient_id=1,
    follow_up_date=datetime.now() + timedelta(days=7),
    advance_days=3,
    notes="请携带上次的检查报告"
)

# 创建用药提醒
result = service.create_medication_reminder(
    patient_id=1,
    prescription_id=1,
    medication_name="玻璃酸钠滴眼液",
    dosage="每日3次，每次1-2滴",
    duration_days=7
)

# 查询提醒
reminders = service.get_reminders_by_patient(patient_id=1, status='pending')

# 更新状态
service.update_reminder_status(reminder_id=1, status='completed')

service.close()
```

## Agent命令列表

### 查看类命令

- `查看提醒` / `我的提醒` / `提醒列表` - 查看所有提醒
- `查看待处理` / `待处理提醒` - 查看未完成的提醒
- `配置` / `设置` - 查看提醒配置

### 操作类命令

- `创建复诊提醒` - 创建复诊提醒（需要后续提供日期）
- `创建用药提醒` - 创建用药提醒（需要后续提供药物信息）
- `取消提醒 ID:X` - 取消指定提醒
- `完成提醒 ID:X` - 标记提醒为已完成

### 示例对话

```
用户: 你好
Agent: 您好！我是小Reminder，您的健康提醒助手...

用户: 查看我的提醒
Agent: 📋 您的提醒列表
      ⏰ 待处理 (2条)
      🏥 复诊提醒 - 2025-11-24 00:00:00 (ID:1)
      💊 用药提醒 - 2025-11-18 00:00:00 (ID:2)
      ...

用户: 完成提醒 ID:2
Agent: ✅ 提醒已标记为完成（ID:2）

用户: 创建复诊提醒
Agent: 好的，我来帮您创建复诊提醒。请告诉我复诊日期（例如：2025-12-01 或 下周三）
```

## 提醒类型说明

### 1. 复诊提醒 (follow_up)
用于提醒患者按时复诊
- 默认提前3天提醒
- 优先级：高

### 2. 预约提醒 (appointment)
预约就诊时间提醒
- 默认提前1天提醒
- 优先级：高

### 3. 用药提醒 (medication)
按时服药提醒
- 可设置每日重复
- 优先级：普通

### 4. 检查提醒 (checkup)
定期检查提醒
- 可自定义提醒时间
- 优先级：普通

### 5. 自定义提醒 (custom)
其他类型提醒
- 完全自定义
- 优先级：可配置

## 提醒状态

- `pending` - 待发送
- `sent` - 已发送
- `completed` - 已完成
- `cancelled` - 已取消
- `expired` - 已过期

## 优先级

- `low` - 低
- `normal` - 普通（默认）
- `high` - 高
- `urgent` - 紧急

## 重复类型

- `once` - 单次（默认）
- `daily` - 每日重复
- `weekly` - 每周重复
- `monthly` - 每月重复
- `custom` - 自定义重复

## 配置选项

每个患者可以配置个性化的提醒设置：

```python
service.update_reminder_config(
    patient_id=1,
    enable_follow_up=True,        # 启用复诊提醒
    enable_appointment=True,      # 启用预约提醒
    enable_medication=True,       # 启用用药提醒
    default_advance_days=2,       # 默认提前2天
    preferred_notification_method='sms'  # 偏好通知方式
)
```

## 自动提醒任务

系统可以实现定时任务，自动检查和发送待处理的提醒：

```python
# 获取需要发送的提醒
pending_reminders = service.get_pending_reminders()

for reminder in pending_reminders:
    # 检查免打扰时间
    # 发送通知（短信/系统通知等）
    # 更新状态为已发送
    service.update_reminder_status(
        reminder_id=reminder['Reminder_ID'],
        status='sent'
    )
```

## 集成到主系统

Agent3已完全集成到主系统中：

1. **AgentManager** - 支持创建和管理ReminderAgent
2. **IntentDetector** - 自动识别提醒相关意图
3. **Main API** - 提供完整的REST API接口
4. **自动路由** - `/api/chat` 会自动路由到ReminderAgent

### 主对话接口自动路由

```python
# 用户发送提醒相关消息时，会自动路由到Agent3
POST /api/chat
{
  "message": "查看我的提醒",
  "phone_number": "13900000001"
}

# 系统会自动识别意图并使用ReminderAgent处理
```

## 测试

运行测试脚本：

```bash
python test_agent3_reminder.py
```

测试包括：
1. 提醒服务基本功能测试
2. Agent对话测试
3. 命令功能测试
4. 配置功能测试
5. 摘要功能测试

## 注意事项

1. **数据库初始化**：使用前必须先执行 `reminder_schema.sql` 初始化数据库
2. **手机号推荐**：推荐使用手机号而非patient_id，可以获取完整的历史信息
3. **时间格式**：scheduled_time 使用 ISO 8601 格式（如：2025-12-01T09:00:00）
4. **权限控制**：患者和医生都可以查看和管理提醒
5. **定时任务**：需要单独实现定时任务机制来自动发送提醒

## 扩展功能建议

1. **短信通知集成** - 集成短信服务商API
2. **微信通知** - 集成微信公众号/小程序推送
3. **邮件通知** - 发送邮件提醒
4. **智能推荐** - 根据病史自动推荐复诊时间
5. **家属通知** - 支持通知紧急联系人

## 开发者信息

- 创建日期：2025-11-17
- Agent类：`agents/agent_3.py`
- 数据库服务：`database/reminder_service.py`
- API路由：`/api/reminder/*` 和 `/api/chat/reminder`
- 测试脚本：`test_agent3_reminder.py`
