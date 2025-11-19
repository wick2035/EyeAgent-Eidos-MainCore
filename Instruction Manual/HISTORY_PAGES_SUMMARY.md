# 历史记录查询页面总览

本项目包含两个历史记录查询页面,分别用于不同的数据查询需求。

## 📊 页面对比

| 特性 | `/history` | `/chat-history` |
|------|------------|-----------------|
| **用途** | 查询患者医疗记录 | 查询对话历史记录 |
| **数据来源** | patient, medical_record, appointment, prescription 表 | chat_conversation, chat_message 表 |
| **查询方式** | 手机号 | 患者ID/手机号 或 医生ID |
| **显示内容** | 就诊记录、预约、处方 | 对话会话、消息内容 |
| **适用场景** | 医疗档案查询 | 聊天记录回顾 |
| **布局** | 单页展示 | 双栏布局(列表+详情) |

---

## 1️⃣ 医疗记录查询页面 (`/history`)

### 访问地址
```
http://localhost:8000/history
```

### 功能特点
- ✅ 通过手机号查询患者完整医疗档案
- ✅ 显示患者基本信息(姓名、性别、年龄等)
- ✅ 显示所有就诊记录(病历号、诊断、治疗方案)
- ✅ 显示预约记录(时间、医生、状态)
- ✅ 显示处方记录(药品、用法、剂量)

### API端点
```
GET /api/patients/history/{phone_number}
```

### 使用示例
```bash
# 查询手机号 13900000001 的患者记录
curl http://localhost:8000/api/patients/history/13900000001
```

### 返回数据示例
```json
{
  "success": true,
  "patient": {
    "Patient_ID": 1,
    "Name": "张三",
    "Phone_Number": "13900000001",
    "Gender": "男",
    "Age": 35
  },
  "medical_records": [...],
  "appointments": [...],
  "prescriptions": [...]
}
```

### 详细文档
📖 查看 [HISTORY_PAGE_USAGE.md](HISTORY_PAGE_USAGE.md)

---

## 2️⃣ 对话历史记录查询页面 (`/chat-history`)

### 访问地址
```
http://localhost:8000/chat-history
```

### 功能特点
- ✅ 双栏布局:左侧对话列表,右侧消息详情
- ✅ 支持患者和医生两种用户类型切换
- ✅ 显示对话元信息(Agent、类型、消息数、状态)
- ✅ 显示完整对话消息(用户消息和AI回复)
- ✅ 消息按序号排序,支持时间显示

### API端点
```
GET /api/chat/history/patient/{patient_id}      # 患者对话列表
GET /api/chat/history/phone/{phone_number}      # 通过手机号查询
GET /api/chat/history/doctor/{doctor_id}        # 医生对话列表
GET /api/chat/messages/{chat_id}                # 对话消息详情
```

### 使用示例
```bash
# 查询患者ID为1的对话列表
curl http://localhost:8000/api/chat/history/patient/1

# 通过手机号查询对话列表
curl http://localhost:8000/api/chat/history/phone/13900000001

# 查询对话ID为6的所有消息
curl http://localhost:8000/api/chat/messages/6
```

### 返回数据示例
```json
{
  "success": true,
  "chat": {
    "Chat_ID": 6,
    "Title": "我的手机号多少",
    "AI_Agent": "agent_1",
    "Total_Messages": 2
  },
  "messages": [
    {
      "Message_Order": 1,
      "Message_Type": "user",
      "Message_Content": "我的手机号多少",
      "Created_At": "2025-11-19T12:00:10"
    },
    {
      "Message_Order": 2,
      "Message_Type": "ai",
      "Message_Content": "您的手机号是: 13900000001",
      "Created_At": "2025-11-19T12:00:15"
    }
  ]
}
```

### 详细文档
📖 查看 [CHAT_HISTORY_USAGE.md](CHAT_HISTORY_USAGE.md)

---

## 🚀 快速开始

### 1. 启动服务器
```bash
python main.py
```

### 2. 访问页面

**主聊天界面:**
```
http://localhost:8000/
```

**医疗记录查询:**
```
http://localhost:8000/history
```

**对话历史查询:**
```
http://localhost:8000/chat-history
```

---

## 📝 测试数据

根据日志,当前数据库中有以下测试数据:

### 患者数据
- **患者ID**: 1
- **姓名**: 张三
- **手机号**: 13900000001
- **性别**: 男
- **年龄**: 35

### 医疗记录
- 4条就诊记录(眼科相关)
- 2条历史预约记录
- 1条处方记录

### 对话记录
- **对话ID**: 6
- **标题**: "我的手机号多少"
- **消息数**: 2条
- **AI Agent**: agent_1

### 测试方法

#### 测试医疗记录查询:
1. 访问 http://localhost:8000/history
2. 输入手机号: `13900000001`
3. 点击查询

#### 测试对话历史查询:
1. 访问 http://localhost:8000/chat-history
2. 确保选择"患者"标签
3. 输入患者ID: `1` 或手机号: `13900000001`
4. 按Enter键查询
5. 点击左侧的对话项查看消息详情

---

## 🔧 技术实现

### 后端服务
- **框架**: FastAPI
- **数据库**: MySQL
- **服务类**:
  - `UserHistoryServiceV2` - 医疗记录查询
  - `ChatService` - 对话历史查询
  - `PrescriptionService` - 处方查询

### 前端技术
- **HTML5 + CSS3**: 响应式布局
- **原生JavaScript**: 无框架依赖
- **Fetch API**: RESTful接口调用

### 数据表结构

#### 医疗记录相关表:
- `patient` - 患者基本信息
- `medical_record` - 就诊记录
- `appointment` - 预约信息
- `prescription` - 处方信息

#### 对话历史相关表:
- `chat_conversation` - 对话会话
- `chat_message` - 消息详情

详细表结构请参考:
- [database/CHAT_HISTORY_README.md](database/CHAT_HISTORY_README.md)
- [CLAUDE.md](CLAUDE.md)

---

## 📚 相关文档

- [HISTORY_PAGE_USAGE.md](HISTORY_PAGE_USAGE.md) - 医疗记录查询页面使用说明
- [CHAT_HISTORY_USAGE.md](CHAT_HISTORY_USAGE.md) - 对话历史查询页面使用说明
- [CLAUDE.md](CLAUDE.md) - 项目整体说明
- [database/CHAT_HISTORY_README.md](database/CHAT_HISTORY_README.md) - 对话历史数据库文档

---

## 🎯 使用建议

### 何时使用医疗记录查询页面 (`/history`):
- 查看患者的就诊历史
- 查询预约记录
- 查看处方信息
- 生成医疗报告前的数据确认

### 何时使用对话历史查询页面 (`/chat-history`):
- 回顾与患者的对话内容
- 查看AI助手的回复历史
- 追溯问题诊断过程
- 评估AI助手表现
- 医患沟通记录归档

---

## ⚠️ 注意事项

1. **手机号格式**: 必须是11位有效的中国大陆手机号(1开头)
2. **数据权限**: 当前为演示版本,生产环境需添加权限验证
3. **会话管理**: 对话历史会自动保存,无需手动操作
4. **性能优化**: 大量数据时建议添加分页功能
5. **浏览器兼容**: 建议使用现代浏览器(Chrome, Firefox, Edge)

---

## 🔮 未来改进

- [ ] 添加数据导出功能(Excel/PDF)
- [ ] 实现数据筛选和排序
- [ ] 添加日期范围查询
- [ ] 支持模糊搜索
- [ ] 添加数据统计图表
- [ ] 实现实时数据更新
- [ ] 添加打印功能
- [ ] 移动端优化
