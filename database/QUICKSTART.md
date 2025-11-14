# 快速入门指南

## 5分钟快速开始

### 步骤 1: 安装依赖

```bash
pip install pymysql
```

或者安装项目所有依赖：

```bash
pip install -r requirements.txt
```

### 步骤 2: 初始化数据库

确保 MySQL 服务已启动，然后执行初始化脚本：

```bash
mysql -u root -p20041118 < database/init_database.sql
```

或者使用 MySQL 客户端：

```sql
SOURCE database/init_database.sql;
```

### 步骤 3: 验证数据库

```sql
USE medical_db;
SHOW TABLES;
SELECT * FROM doctor;
```

应该能看到 3 个表（doctor, patient, appointment）和 5 条测试医生数据。

### 步骤 4: 运行示例

```bash
cd database
python example_usage.py
```

### 步骤 5: 在代码中使用

创建一个新的 Python 文件（如 `test_appointment.py`）：

```python
from database.appointment_service import AppointmentService

# 模拟一号智能体的输出数据
patient_data = {
    "patient_info": {
        "name": "张三",
        "age": "35",
        "gender": "男",
        "contact": "13800138000",
    },
    "chief_complaint": "眼部不适，视力模糊",
    "present_illness": "近一周出现视力下降",
    "medical_history": "无",
    "allergy_history": "无",
    "appointment": {
        "department": "眼科",
        "preferred_time": "明天上午",
        "urgency": "普通"
    }
}

# 创建预约服务
service = AppointmentService()

# 处理预约
result = service.process_appointment(patient_data)

# 打印结果
if result['success']:
    print("✓ 预约成功！")
    print(f"患者ID: {result['patient_id']}")
    print(f"预约ID: {result['appointment_id']}")
    print(f"医生: {result['doctor_info']['name']}")
    print(f"时间: {result['appointment_time']}")
else:
    print(f"✗ 预约失败: {result['message']}")

# 关闭连接
service.close()
```

运行：

```bash
python test_appointment.py
```

## 与一号智能体集成

```python
from agents.agent_1 import HealthAgent
from database.appointment_service import AppointmentService

# 创建智能体
agent = HealthAgent()

# 模拟对话（实际使用时通过 UI 或命令行交互）
responses = []
responses.append(agent.chat("你好"))
responses.append(agent.chat("我最近眼睛很不舒服，看东西模糊"))
responses.append(agent.chat("是的，我想预约"))
responses.append(agent.chat("我叫张三，35岁，男，电话13800138000"))
responses.append(agent.chat("大概一周前开始的，慢慢加重"))
responses.append(agent.chat("没有其他病史，也不过敏"))
responses.append(agent.chat("明天上午可以吗"))

# 打印对话
for i, resp in enumerate(responses):
    print(f"\n智能体: {resp}")

# 检查是否完成
if agent.is_completed():
    print("\n对话完成，准备创建预约...")
    
    # 获取患者数据
    patient_data = agent.get_patient_data()
    
    # 处理预约
    service = AppointmentService()
    result = service.process_appointment(patient_data)
    
    if result['success']:
        print(f"\n✓ 预约成功！")
        print(f"预约ID: {result['appointment_id']}")
        print(f"医生: {result['doctor_info']['name']}")
        print(f"时间: {result['appointment_time']}")
    else:
        print(f"\n✗ 预约失败: {result['message']}")
    
    service.close()
```

## 常见问题

### Q1: 连接数据库失败

**错误**: `Can't connect to MySQL server`

**解决**:
1. 检查 MySQL 服务是否启动
2. 确认用户名和密码是否正确
3. 检查 `database/db_config.py` 中的配置

### Q2: 表不存在

**错误**: `Table 'medical_db.doctor' doesn't exist`

**解决**:
执行初始化脚本：
```bash
mysql -u root -p20041118 < database/init_database.sql
```

### Q3: 没有可用医生

**错误**: `未找到符合条件的可用医生`

**解决**:
1. 检查 doctor 表是否有数据
2. 确认医生的 `Available_Time` 字段格式正确
3. 尝试不指定期望时间

### Q4: 导入模块失败

**错误**: `ModuleNotFoundError: No module named 'pymysql'`

**解决**:
```bash
pip install pymysql
```

## 下一步

- 阅读 [README.md](README.md) 了解完整功能
- 查看 [example_usage.py](example_usage.py) 了解更多示例
- 根据需要修改 [db_config.py](db_config.py) 配置数据库连接

## 数据库管理

### 查看所有患者

```sql
USE medical_db;
SELECT Patient_ID, Name, Phone_Number, Chief_Complaint, Visit_Date 
FROM patient 
ORDER BY Visit_Date DESC;
```

### 查看所有预约

```sql
SELECT 
    a.Appointment_ID,
    a.Patient_Name,
    d.Name AS Doctor_Name,
    a.Appointment_Time,
    a.Appointment_Status
FROM appointment a
JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
ORDER BY a.Appointment_Time DESC;
```

### 清空测试数据

```sql
-- 删除所有预约
DELETE FROM appointment;

-- 删除所有患者（会自动删除相关预约）
DELETE FROM patient;

-- 重置自增ID
ALTER TABLE appointment AUTO_INCREMENT = 1;
ALTER TABLE patient AUTO_INCREMENT = 1;
```

## 技术支持

如有问题，请查看：
- 日志输出（INFO/WARNING/ERROR）
- 数据库连接状态
- SQL 执行结果

祝使用愉快！🎉

