# 对话历史记录查询页面使用说明

## 访问方式

启动服务器后,访问以下地址查看对话历史记录查询页面:

```
http://localhost:8000/chat-history
```

或者在浏览器中访问:
```
http://127.0.0.1:8000/chat-history
```

## 功能说明

这是一个专门用于查看对话历史记录的页面,基于 `chat_conversation` 和 `chat_message` 数据表。

### 主要功能:

1. **双栏布局**
   - 左侧: 对话列表
   - 右侧: 消息详情

2. **用户类型切换**
   - 👤 患者模式 - 查看患者的对话记录
   - 👨‍⚕️ 医生模式 - 查看医生的对话记录

3. **对话列表显示**
   - 对话标题
   - 对话状态(active/archived/closed)
   - AI Agent信息
   - 对话类型
   - 消息数量
   - 创建时间
   - 对话摘要

4. **消息详情显示**
   - 消息发送者(用户/AI)
   - 消息内容
   - 发送时间
   - 消息序号
   - 上下文信息

## 使用方法

### 查询患者对话记录:

1. 确保选择"患者"标签
2. 在搜索框输入患者ID或手机号(例如: 1 或 13900000001)
3. 按Enter键或点击查询
4. 从左侧列表选择一个对话
5. 右侧会显示该对话的所有消息

### 查询医生对话记录:

1. 点击"医生"标签
2. 在搜索框输入医生ID
3. 按Enter键或点击查询
4. 从左侧列表选择一个对话
5. 右侧会显示该对话的所有消息

## 数据来源

### 1. chat_conversation 表
存储对话会话信息:
- Chat_ID - 对话唯一标识
- User_Type - 用户类型(patient/doctor)
- Patient_ID - 患者ID
- Doctor_ID - 医生ID
- Title - 对话标题
- Conversation_Type - 对话类型(general/consultation/appointment/report等)
- AI_Agent - 处理此对话的AI智能体(agent_1/agent_2/agent_3等)
- Summary - 对话摘要
- Total_Messages - 消息总数
- Status - 对话状态(active/archived/closed)
- Created_At - 创建时间
- Updated_At - 最后更新时间

### 2. chat_message 表
存储对话消息详情:
- Message_ID - 消息唯一标识
- Chat_ID - 关联到对话会话
- Message_Order - 消息序号
- Message_Content - 消息内容
- Message_Type - 消息类型(user/ai)
- Sender_Info - 发送者信息
- Context - 消息上下文
- Tokens_Used - 消耗的token数
- Created_At - 创建时间

## API 接口

### 1. 查询患者的对话列表
```
GET /api/chat/history/patient/{patient_id}
```

示例:
```bash
curl http://localhost:8000/api/chat/history/patient/1
```

### 2. 通过手机号查询对话列表
```
GET /api/chat/history/phone/{phone_number}
```

示例:
```bash
curl http://localhost:8000/api/chat/history/phone/13900000001
```

### 3. 查询医生的对话列表
```
GET /api/chat/history/doctor/{doctor_id}
```

示例:
```bash
curl http://localhost:8000/api/chat/history/doctor/5
```

### 4. 查询对话的所有消息
```
GET /api/chat/messages/{chat_id}
```

示例:
```bash
curl http://localhost:8000/api/chat/messages/6
```

### 返回数据格式示例:

#### 对话列表返回格式:
```json
{
  "success": true,
  "chats": [
    {
      "Chat_ID": 6,
      "User_Type": "patient",
      "Patient_ID": 1,
      "Title": "我的手机号多少",
      "Conversation_Type": "general",
      "AI_Agent": "agent_1",
      "Summary": null,
      "Total_Messages": 2,
      "Status": "active",
      "Created_At": "2025-11-19T12:00:00",
      "Updated_At": "2025-11-19T12:01:00"
    }
  ]
}
```

#### 消息详情返回格式:
```json
{
  "success": true,
  "chat": {
    "Chat_ID": 6,
    "Title": "我的手机号多少",
    "AI_Agent": "agent_1",
    "Conversation_Type": "general",
    "Total_Messages": 2,
    "Created_At": "2025-11-19T12:00:00"
  },
  "messages": [
    {
      "Message_ID": 9,
      "Chat_ID": 6,
      "Message_Order": 1,
      "Message_Content": "我的手机号多少",
      "Message_Type": "user",
      "Sender_Info": "张三",
      "Created_At": "2025-11-19T12:00:10"
    },
    {
      "Message_ID": 10,
      "Chat_ID": 6,
      "Message_Order": 2,
      "Message_Content": "您的手机号是: 13900000001",
      "Message_Type": "ai",
      "Sender_Info": "AI助手",
      "Created_At": "2025-11-19T12:00:15"
    }
  ]
}
```

## 测试数据

根据日志输出,目前数据库中有以下测试数据:
- 患者ID: 1, 姓名: 张三, 手机号: 13900000001
- 对话ID: 6 (包含2条消息)

你可以使用这些数据进行测试。

## 界面特性

- ✅ 双栏响应式布局
- ✅ 实时搜索和过滤
- ✅ 对话状态颜色标识
- ✅ 用户/AI消息区分显示
- ✅ 消息时间格式化
- ✅ 消息序号显示
- ✅ 平滑滚动和动画效果
- ✅ 加载状态提示
- ✅ 错误友好提示

## 页面对比

### /history 页面
- 用途: 查询患者的**就诊记录、预约记录、处方记录**
- 数据来源: patient, medical_record, appointment, prescription 表
- 适合: 医疗记录查询

### /chat-history 页面
- 用途: 查询**对话历史记录和消息内容**
- 数据来源: chat_conversation, chat_message 表
- 适合: 对话记录查询、聊天内容回顾

## 注意事项

- 对话记录会在每次聊天时自动保存到数据库
- 支持通过患者ID或手机号查询
- 消息按序号顺序显示
- 对话状态可以是 active/archived/closed
- 页面支持实时刷新,可以看到最新的对话
