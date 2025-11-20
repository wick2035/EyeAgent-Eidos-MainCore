# 对话历史记录表使用文档

本文档说明如何使用对话历史记录功能，包括表结构、服务类API和使用示例。

## 目录

- [表结构设计](#表结构设计)
- [安装和初始化](#安装和初始化)
- [服务类API](#服务类api)
- [使用示例](#使用示例)
- [常用查询](#常用查询)
- [集成到现有系统](#集成到现有系统)

---

## 表结构设计

### 1. `chat_conversation` - 对话会话主表

存储每个独立的对话会话信息，**支持患者(patient)和医生(doctor)两种用户类型**。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `Chat_ID` | INT (主键) | 对话唯一标识 |
| `User_Type` | ENUM('patient', 'doctor') | 用户类型 |
| `Patient_ID` | INT (外键, 可空) | 患者ID（当User_Type='patient'时必填） |
| `Doctor_ID` | INT (外键, 可空) | 医生ID（当User_Type='doctor'时必填） |
| `Title` | VARCHAR(255) | 对话标题（可为空） |
| `Conversation_Type` | VARCHAR(50) | 对话类型（general/consultation/appointment/report等） |
| `AI_Agent` | VARCHAR(100) | 处理此对话的AI智能体（agent_1/agent_2/agent_3等） |
| `Summary` | TEXT | 对话摘要（可选，用于快速查阅） |
| `Total_Messages` | INT | 消息总数 |
| `Status` | ENUM | 对话状态（active/archived/closed） |
| `Created_At` | TIMESTAMP | 创建时间 |
| `Updated_At` | TIMESTAMP | 最后更新时间 |

**约束:**
- 当 `User_Type='patient'` 时，`Patient_ID` 不为空，`Doctor_ID` 为空
- 当 `User_Type='doctor'` 时，`Doctor_ID` 不为空，`Patient_ID` 为空

### 2. `chat_message` - 消息详情表

存储对话中的每一条消息（用户消息和AI消息）。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `Message_ID` | INT (主键) | 消息唯一标识 |
| `Chat_ID` | INT (外键) | 关联到对话会话 |
| `Message_Order` | INT | 消息序号（会话内的顺序号，从1开始） |
| `Message_Content` | LONGTEXT | 消息内容 |
| `Message_Type` | ENUM('user', 'ai') | 消息类型 |
| `Sender_Info` | VARCHAR(255) | 发送者信息（用户名/AI代理名称） |
| `Context` | TEXT | 消息上下文（可存储JSON格式） |
| `Tokens_Used` | INT | 此消息消耗的token数（可选） |
| `Created_At` | TIMESTAMP | 消息创建时间 |
| `Updated_At` | TIMESTAMP | 消息修改时间 |

**约束:**
- `(Chat_ID, Message_Order)` 为唯一约束，确保消息顺序不重复

---

## 安装和初始化

### 步骤 1: 执行SQL脚本创建表

```bash
# 方法1: 使用Python脚本自动执行
cd database
python execute_chat_init.py

# 方法2: 手动执行SQL
mysql -u root -p medical_db < chat_history_table.sql
```

### 步骤 2: 验证表创建成功

```bash
# 进入MySQL
mysql -u root -p medical_db

# 查看表
mysql> SHOW TABLES LIKE 'chat%';
mysql> DESCRIBE chat_conversation;
mysql> DESCRIBE chat_message;
```

---

## 服务类API

### ChatService 类

位置: `database/chat_service.py`

#### 对话会话管理

##### 1. 创建对话

```python
from database.chat_service import ChatService

service = ChatService()

# 为患者创建对话
chat_id = service.create_chat_for_patient(
    patient_id=1,
    title="眼部不适咨询",
    conversation_type='consultation',
    ai_agent='agent_1'
)

# 为医生创建对话
chat_id = service.create_chat_for_doctor(
    doctor_id=5,
    title="患者诊断记录",
    conversation_type='report',
    ai_agent='agent_2'
)
```

##### 2. 查询用户的所有对话

```python
# 查询患者的对话
chats = service.get_user_chats(
    user_type='patient',
    user_id=1,
    status='active',  # 可选: 'active'/'archived'/'closed'/None(所有)
    limit=20
)

# 查询医生的对话
chats = service.get_user_chats(
    user_type='doctor',
    user_id=5,
    status=None,  # 查询所有状态
    limit=50
)
```

##### 3. 查询单个对话

```python
chat = service.get_chat_by_id(chat_id=10)
print(f"对话标题: {chat['Title']}")
print(f"用户类型: {chat['User_Type']}")
print(f"消息总数: {chat['Total_Messages']}")
```

##### 4. 更新对话信息

```python
# 更新标题
service.update_chat_title(chat_id=10, title="新标题")

# 更新摘要
service.update_chat_summary(chat_id=10, summary="这是一段对话摘要...")

# 更新状态
service.update_chat_status(chat_id=10, status='archived')

# 归档对话（快捷方法）
service.archive_chat(chat_id=10)

# 关闭对话（快捷方法）
service.close_chat(chat_id=10)
```

##### 5. 删除对话

```python
# 删除对话（会级联删除所有相关消息）
service.delete_chat(chat_id=10)
```

#### 消息管理

##### 1. 保存消息

```python
# 保存用户消息
message_id = service.save_message(
    chat_id=10,
    message_content="我最近眼睛有点不舒服",
    message_type='user',
    sender_info='患者张三',
    context={'symptoms': ['眼睛干涩', '视力模糊']},
    tokens_used=None
)

# 保存AI消息
message_id = service.save_message(
    chat_id=10,
    message_content="您好，请详细描述一下症状...",
    message_type='ai',
    sender_info='agent_1',
    context={'stage': 'symptom_assessment'},
    tokens_used=150
)
```

##### 2. 查询消息

```python
# 获取对话的所有消息
messages = service.get_chat_messages(
    chat_id=10,
    limit=None,  # None表示所有消息
    offset=0
)

# 分页查询
messages_page1 = service.get_chat_messages(chat_id=10, limit=10, offset=0)
messages_page2 = service.get_chat_messages(chat_id=10, limit=10, offset=10)

# 查询单条消息
message = service.get_message_by_id(message_id=123)
```

##### 3. 更新和删除消息

```python
# 更新消息内容
service.update_message_content(
    message_id=123,
    new_content="修改后的消息内容"
)

# 删除消息
service.delete_message(message_id=123)
```

#### 高级查询

##### 1. 获取最近对话及最后一条消息

```python
chats = service.get_recent_chats_with_last_message(
    user_type='patient',
    user_id=1,
    limit=10
)

for chat in chats:
    print(f"对话: {chat['Title']}")
    if chat['last_message']:
        print(f"  最后消息: {chat['last_message']['Message_Content'][:50]}...")
```

##### 2. 获取对话统计信息

```python
stats = service.get_chat_statistics(chat_id=10)
print(f"总消息数: {stats['total_messages']}")
print(f"用户消息: {stats['user_messages']}")
print(f"AI消息: {stats['ai_messages']}")
print(f"总token数: {stats['total_tokens']}")
```

##### 3. 搜索消息

```python
# 搜索包含关键词的消息
results = service.search_messages(
    chat_id=10,
    keyword='眼睛',
    message_type='user'  # 可选: 'user'/'ai'/None
)

for msg in results:
    print(f"[{msg['Message_Order']}] {msg['Message_Content']}")
```

---

## 使用示例

### 示例 1: 患者咨询流程

```python
from database.chat_service import ChatService

service = ChatService()

# 1. 患者开始新对话
patient_id = 1  # 假设患者ID为1
chat_id = service.create_chat_for_patient(
    patient_id=patient_id,
    title="眼部不适咨询",
    conversation_type='consultation',
    ai_agent='agent_1'
)

# 2. 患者发送第一条消息
service.save_message(
    chat_id=chat_id,
    message_content="医生您好，我最近眼睛有点不舒服",
    message_type='user',
    sender_info=f'Patient_{patient_id}'
)

# 3. AI回复
service.save_message(
    chat_id=chat_id,
    message_content="您好！请详细描述一下您的症状，比如是疼痛还是干涩？",
    message_type='ai',
    sender_info='agent_1',
    context={'stage': 'symptom_assessment'},
    tokens_used=85
)

# 4. 后续对话...
service.save_message(
    chat_id=chat_id,
    message_content="主要是干涩，有时候还有点痒",
    message_type='user'
)

# 5. 对话结束后更新摘要
service.update_chat_summary(
    chat_id=chat_id,
    summary="患者主诉眼睛干涩、发痒，建议进一步检查"
)

# 6. 归档对话
service.archive_chat(chat_id)
```

### 示例 2: 医生查看对话历史

```python
# 1. 获取医生的所有对话
doctor_id = 5
chats = service.get_user_chats(
    user_type='doctor',
    user_id=doctor_id,
    status='active',
    limit=20
)

# 2. 查看某个对话的详细消息
selected_chat_id = chats[0]['Chat_ID']
messages = service.get_chat_messages(chat_id=selected_chat_id)

print(f"对话标题: {chats[0]['Title']}")
print(f"消息数量: {len(messages)}")
print("\n对话记录:")
for msg in messages:
    sender = "医生" if msg['Message_Type'] == 'ai' else "患者"
    print(f"[{sender}] {msg['Message_Content']}")
```

### 示例 3: 集成到Agent中

```python
from agents.agent_1 import HealthAgent
from database.chat_service import ChatService

# 初始化Agent和ChatService
agent = HealthAgent(user_id=None, phone_number="13800138000", role="patient")
chat_service = ChatService()

# 获取或创建对话会话
patient_id = 1  # 从phone_number查询得到
chat_id = chat_service.create_chat_for_patient(
    patient_id=patient_id,
    conversation_type='consultation',
    ai_agent='agent_1'
)

# 用户发送消息
user_message = "我想预约眼科门诊"
chat_service.save_message(
    chat_id=chat_id,
    message_content=user_message,
    message_type='user'
)

# Agent处理消息
ai_response = agent.chat(user_message)

# 保存AI回复
chat_service.save_message(
    chat_id=chat_id,
    message_content=ai_response,
    message_type='ai',
    sender_info='agent_1',
    context={'stage': agent.stage.value}
)
```

---

## 常用查询

### SQL查询示例

```sql
-- 1. 查询某个患者的所有对话（按时间倒序）
SELECT * FROM chat_conversation
WHERE User_Type = 'patient' AND Patient_ID = 1
ORDER BY Created_At DESC;

-- 2. 查询某个医生的所有对话
SELECT * FROM chat_conversation
WHERE User_Type = 'doctor' AND Doctor_ID = 5
ORDER BY Created_At DESC;

-- 3. 查询某个对话的所有消息（按顺序）
SELECT * FROM chat_message
WHERE Chat_ID = 10
ORDER BY Message_Order ASC;

-- 4. 查询最近7天的活跃对话
SELECT * FROM chat_conversation
WHERE Patient_ID = 1
AND Status = 'active'
AND Created_At >= DATE_SUB(NOW(), INTERVAL 7 DAY)
ORDER BY Updated_At DESC;

-- 5. 查询某个对话的消息统计
SELECT
    Chat_ID,
    COUNT(*) as total_messages,
    SUM(CASE WHEN Message_Type = 'user' THEN 1 ELSE 0 END) as user_messages,
    SUM(CASE WHEN Message_Type = 'ai' THEN 1 ELSE 0 END) as ai_messages,
    SUM(COALESCE(Tokens_Used, 0)) as total_tokens
FROM chat_message
WHERE Chat_ID = 10
GROUP BY Chat_ID;

-- 6. 通过电话号查询患者的所有对话
SELECT cc.* FROM chat_conversation cc
INNER JOIN patient p ON cc.Patient_ID = p.Patient_ID
WHERE p.Phone_Number = '13900000001' AND cc.User_Type = 'patient'
ORDER BY cc.Created_At DESC;

-- 7. 查询所有活跃对话及其最后一条消息
SELECT
    cc.*,
    cm.Message_Content as Last_Message,
    cm.Created_At as Last_Message_Time
FROM chat_conversation cc
LEFT JOIN (
    SELECT Chat_ID, Message_Content, Created_At
    FROM chat_message cm1
    WHERE Message_Order = (
        SELECT MAX(Message_Order)
        FROM chat_message cm2
        WHERE cm2.Chat_ID = cm1.Chat_ID
    )
) cm ON cc.Chat_ID = cm.Chat_ID
WHERE cc.Status = 'active'
ORDER BY cc.Updated_At DESC;
```

---

## 集成到现有系统

### 方法1: 在main.py中集成

```python
from fastapi import FastAPI
from database.chat_service import ChatService
from database.user_history_service_v2 import UserHistoryServiceV2

app = FastAPI()

@app.post("/api/chat")
async def chat_endpoint(request: dict):
    phone = request.get("phone_number")
    message = request.get("message")

    # 获取用户信息
    user_service = UserHistoryServiceV2()
    user = user_service.get_user_by_phone(phone)

    if not user:
        return {"error": "用户不存在"}

    patient_id = user['Patient_ID']

    # 获取或创建对话
    chat_service = ChatService()

    # 检查是否有活跃对话
    active_chats = chat_service.get_user_chats(
        user_type='patient',
        user_id=patient_id,
        status='active',
        limit=1
    )

    if active_chats:
        chat_id = active_chats[0]['Chat_ID']
    else:
        # 创建新对话
        chat_id = chat_service.create_chat_for_patient(
            patient_id=patient_id,
            conversation_type='consultation',
            ai_agent='agent_1'
        )

    # 保存用户消息
    chat_service.save_message(
        chat_id=chat_id,
        message_content=message,
        message_type='user'
    )

    # Agent处理...
    ai_response = "AI的回复内容"

    # 保存AI消息
    chat_service.save_message(
        chat_id=chat_id,
        message_content=ai_response,
        message_type='ai',
        sender_info='agent_1'
    )

    return {"response": ai_response, "chat_id": chat_id}
```

### 方法2: 在Agent中集成

在 `agents/agent_1.py` 中添加对话历史记录功能:

```python
from database.chat_service import ChatService

class HealthAgent:
    def __init__(self, user_id, phone_number, role="patient"):
        # ... 原有代码 ...
        self.chat_service = ChatService()
        self.current_chat_id = None

    def start_new_conversation(self):
        """开始新对话"""
        if self.user_id:
            self.current_chat_id = self.chat_service.create_chat_for_patient(
                patient_id=self.user_id,
                conversation_type='consultation',
                ai_agent='agent_1'
            )

    def chat(self, message: str) -> str:
        """处理用户消息并保存对话历史"""
        # 如果没有活跃对话，创建新对话
        if not self.current_chat_id:
            self.start_new_conversation()

        # 保存用户消息
        self.chat_service.save_message(
            chat_id=self.current_chat_id,
            message_content=message,
            message_type='user'
        )

        # ... 原有的Agent处理逻辑 ...
        response = self._process_message(message)

        # 保存AI回复
        self.chat_service.save_message(
            chat_id=self.current_chat_id,
            message_content=response,
            message_type='ai',
            sender_info='agent_1',
            context={'stage': self.stage.value}
        )

        return response
```

---

## 注意事项

1. **用户类型区分**:
   - 创建对话时必须指定用户类型(patient或doctor)
   - 使用对应的创建方法: `create_chat_for_patient()` 或 `create_chat_for_doctor()`

2. **消息顺序**:
   - `Message_Order` 由服务自动管理，从1开始递增
   - 不需要手动指定消息序号

3. **Context字段**:
   - 支持存储字典格式的上下文信息
   - 服务会自动将字典转为JSON存储，查询时自动转回字典

4. **级联删除**:
   - 删除对话会自动删除所有相关消息
   - 删除用户(patient/doctor)会自动删除其所有对话和消息

5. **性能优化**:
   - 对常用查询字段已建立索引
   - 大量历史消息建议使用分页查询

---

## 相关文件

- **SQL脚本**: `database/chat_history_table.sql`
- **初始化脚本**: `database/execute_chat_init.py`
- **服务类**: `database/chat_service.py`
- **数据库配置**: `database/db_config.py`
- **数据库连接**: `database/db_connection.py`

---

## 支持

如有问题或建议，请查看项目主README或联系开发团队。
