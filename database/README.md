# 数据库操作模块

这是一个独立的数据库操作模块，用于处理一号智能体的预约 JSON 输出，自动完成患者病例创建、医生空闲时间检查和预约操作。

## 功能特性

- ✅ 自动创建/更新患者病例
- ✅ 智能检查医生空闲时间
- ✅ 自动匹配最佳医生
- ✅ 事务管理确保数据一致性
- ✅ 完整的错误处理机制
- ✅ 支持自然语言时间表达式解析

## 目录结构

```
database/
├── __init__.py              # 模块初始化
├── db_config.py             # 数据库配置
├── db_connection.py         # 数据库连接管理
├── appointment_service.py   # 预约服务核心逻辑
├── example_usage.py         # 使用示例
└── README.md                # 本文档
```

## 环境要求

- Python 3.7+
- MySQL 5.7+ 或 MariaDB 10.2+
- pymysql 库

## 安装依赖

```bash
pip install pymysql
```

## 数据库配置

### 1. 创建数据库

```sql
CREATE DATABASE medical_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 创建数据表

根据 `example/DB.md` 中的设计创建三个表：
- `doctor` - 医生信息表
- `patient` - 患者信息表
- `appointment` - 预约信息表

### 3. 配置连接信息

在 `db_config.py` 中修改数据库连接信息（默认配置）：

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '20041118',
    'database': 'medical_db',
    'charset': 'utf8mb4',
    'autocommit': False,
}
```

## 使用方法

### 基本使用

```python
from database.appointment_service import AppointmentService

# 创建预约服务实例
service = AppointmentService()

# 从一号智能体获取患者数据
# patient_data = agent.get_patient_data()

# 或者使用字典格式的数据
patient_data = {
    "patient_info": {
        "name": "张三",
        "age": "35",
        "gender": "男",
        "contact": "13800138000",
    },
    "chief_complaint": "眼部不适，视力模糊",
    "appointment": {
        "department": "眼科",
        "preferred_time": "明天下午",
        "urgency": "普通"
    }
}

# 处理预约
result = service.process_appointment(patient_data)

# 检查结果
if result['success']:
    print(f"预约成功！预约ID: {result['appointment_id']}")
    print(f"医生: {result['doctor_info']['name']}")
    print(f"时间: {result['appointment_time']}")
else:
    print(f"预约失败: {result['message']}")

# 关闭连接
service.close()
```

### 与一号智能体集成

```python
from agents.agent_1 import HealthAgent
from database.appointment_service import AppointmentService

# 创建智能体
agent = HealthAgent()

# 进行对话收集信息
# ... 对话流程 ...

# 获取患者数据
patient_data = agent.get_patient_data()

# 处理预约
service = AppointmentService()
result = service.process_appointment(patient_data)

# 处理结果
if result['success']:
    # 通知用户预约成功
    message = result['message']
    # 可以将结果反馈给智能体或用户
else:
    # 处理预约失败情况
    error_message = result['message']

service.close()
```

### 仅查询可用医生

```python
from database.appointment_service import AppointmentService

service = AppointmentService()

# 查询可用医生
doctors = service.find_available_doctors(
    department="眼科",
    preferred_time_expr="明天上午",
    doctor_preference="主任",
    urgency="普通"
)

for doctor in doctors:
    print(f"{doctor['Name']} - {doctor['Title']}")
    print(f"可预约时间: {doctor['parsed_start_time']}")

service.close()
```

## 运行示例

运行完整的使用示例：

```bash
cd database
python example_usage.py
```

示例包含：
1. 基本使用
2. 与一号智能体集成
3. 错误处理
4. 查询可用医生

## 核心类和方法

### AppointmentService

主要的预约服务类，提供以下方法：

#### `process_appointment(patient_json_data: Dict) -> Dict`

处理完整的预约流程（主要接口）

**参数:**
- `patient_json_data`: 一号智能体输出的患者数据字典

**返回:**
```python
{
    'success': bool,           # 是否成功
    'patient_id': int,         # 患者ID
    'appointment_id': int,     # 预约ID
    'doctor_info': dict,       # 医生信息
    'appointment_time': str,   # 预约时间
    'message': str,            # 结果消息
    'available_doctors': list  # 可用医生列表
}
```

#### `create_patient(patient_data: Dict) -> int`

创建或获取患者病例

**返回:** 患者ID

#### `find_available_doctors(department: str, ...) -> List[Dict]`

查找可用医生

**参数:**
- `department`: 科室名称
- `preferred_time_expr`: 期望时间（自然语言）
- `doctor_preference`: 医生偏好
- `urgency`: 紧急程度

**返回:** 医生列表（按匹配度排序）

## 数据映射

### 一号智能体 JSON → 数据库字段

| JSON 字段 | 数据库表 | 数据库字段 |
|----------|---------|----------|
| patient_info.name | patient | Name |
| patient_info.age | patient | Age |
| patient_info.gender | patient | Gender |
| patient_info.contact | patient | Phone_Number |
| chief_complaint | patient | Chief_Complaint |
| medical_history | patient | Medical_History |
| allergy_history | patient | Allergy_History |
| appointment.preferred_time | appointment | Appointment_Time |
| appointment.urgency | appointment | Appointment_Category |

## 时间表达式支持

支持以下自然语言时间表达式：

- **相对时间**: "明天"、"后天"、"今天"、"下周"
- **时间段**: "上午"、"下午"、"晚上"
- **具体日期**: "11月15日"、"2025-11-15"
- **组合**: "明天下午"、"后天上午"

## 错误处理

模块会自动处理以下情况：

1. **缺少必填字段**: 返回错误信息
2. **数据库连接失败**: 抛出异常并记录日志
3. **无可用医生**: 返回失败结果和原因
4. **事务失败**: 自动回滚

## 日志

模块使用 Python 标准 logging 模块记录关键操作：

- INFO: 成功的操作
- WARNING: 可恢复的问题
- ERROR: 错误和异常

## 注意事项

1. **数据库连接**: 使用完毕后记得调用 `service.close()` 关闭连接
2. **事务处理**: 患者创建和预约创建在同一事务中，确保数据一致性
3. **时间匹配**: 如果患者没有指定期望时间，系统会选择最匹配的医生
4. **医生空闲时间**: 当前版本简化了医生空闲时间的更新逻辑

## 扩展开发

如需扩展功能，可以：

1. 在 `AppointmentService` 类中添加新方法
2. 修改 `db_config.py` 适配不同的数据库环境
3. 扩展时间解析逻辑支持更多表达式

## 许可证

本项目为内部使用模块，请遵守相关规定。

