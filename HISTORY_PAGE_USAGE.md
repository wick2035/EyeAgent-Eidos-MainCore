# 历史记录查询页面使用说明

## 访问方式

启动服务器后,访问以下地址查看历史记录查询页面:

```
http://localhost:8000/history
```

或者在浏览器中访问:
```
http://127.0.0.1:8000/history
```

## 功能说明

这是一个简单的历史记录查询测试页面,可以根据患者手机号查询完整的就诊历史。

### 查询内容包括:

1. **患者基本信息**
   - 姓名
   - 手机号
   - 性别
   - 年龄
   - 患者ID
   - 注册日期

2. **就诊记录**
   - 病历号
   - 就诊日期
   - 主诉
   - 症状
   - 诊断
   - 治疗方案
   - 接诊医生

3. **预约记录**
   - 预约号
   - 预约时间
   - 预约医生
   - 预约原因
   - 预约状态(已完成/已取消/待就诊等)
   - 备注信息

4. **处方记录**
   - 处方号
   - 处方日期
   - 药品名称
   - 用法用量
   - 频率
   - 疗程
   - 开方医生

## 使用方法

1. 在搜索框中输入11位手机号(例如: 13800138000)
2. 点击"查询"按钮或按Enter键
3. 系统会显示该手机号对应患者的所有历史记录

## API 接口

如果需要通过API调用,可以使用以下接口:

```
GET /api/patients/history/{phone_number}
```

### 示例:
```bash
curl http://localhost:8000/api/patients/history/13800138000
```

### 返回数据格式:
```json
{
  "success": true,
  "patient": {
    "Patient_ID": 1,
    "Name": "张三",
    "Phone_Number": "13800138000",
    "Gender": "男",
    "Age": 45,
    "Registration_Date": "2024-01-01"
  },
  "medical_records": [
    {
      "Record_ID": 1,
      "Visit_Date": "2024-01-15",
      "Chief_Complaint": "视力模糊",
      "Symptoms": "看东西不清楚",
      "Diagnosis": "白内障",
      "Treatment": "药物治疗",
      "Doctor_ID": "D001"
    }
  ],
  "appointments": [
    {
      "Appointment_ID": 1,
      "Appointment_Date": "2024-01-20",
      "Appointment_Time": "09:00:00",
      "Doctor_ID": "D001",
      "Status": "已完成",
      "Reason": "复查"
    }
  ],
  "prescriptions": [
    {
      "Prescription_Number": "P001",
      "Prescription_Date": "2024-01-15",
      "Drug_Name": "眼药水",
      "Dosage": "每次1滴",
      "Frequency": "每日3次",
      "Duration": "7天"
    }
  ]
}
```

## 测试数据

你可以使用以下手机号进行测试(需要先在数据库中有对应的患者记录):
- 查看数据库中现有的患者手机号
- 或者通过主聊天界面创建新的患者记录后再查询

## 注意事项

- 手机号必须是11位有效的中国大陆手机号
- 如果查询不到记录,会显示"未找到该手机号的患者信息"
- 所有日期和时间字段都会按照数据库中的格式显示
- 页面会自动显示不同状态的预约记录(使用不同颜色标识)
