# 医疗数据库设计文档

## 1. `doctor` 表

### 表结构说明：
- **医生ID**（Doctor_ID）：唯一标识每位医生的主键。
- **姓名**（Name）：医生的姓名。
- **院区**（Hospital_Area）：医生所在的院区。
- **职称**（Title）：医生的职称，例如主任医师、副主任医师等。
- **性别**（Gender）：医生的性别（例如：“男”，“女”）。
- **年龄**（Age）：医生的年龄。
- **手机号**（Phone_Number）：医生的联系电话。
- **主治领域**（Specialty）：医生的主治科目或领域。
- **当前空闲时间**（Available_Time）：医生的当前空闲时间，包括日期、时间段及是否可以预约。

### 示例：
| Doctor_ID | Name   | Hospital_Area | Title    | Gender | Age  | Phone_Number | Specialty | Available_Time              |
| --------- | ------ | ------------- | -------- | ------ | ---- | ------------ | --------- | --------------------------- |
| 1         | 张医生 | 眼科医院      | 主任医师 | 男     | 45   | 138XXXXXXX   | 眼科      | 2025-11-14, 14:00-16:00, 是 |

---

## 2. `appointment` 表

### 表结构说明：
- **预约ID**（Appointment_ID）：唯一标识每次预约的主键。
- **患者ID**（Patient_ID）：关联患者表的患者ID。
- **医生ID**（Doctor_ID）：关联医生表的医生ID。
- **患者名字**（Patient_Name）：患者的姓名。
- **预约时间**（Appointment_Time）：预约的时间。
- **预约分类**（Appointment_Category）：预约的类型，如普通、紧急等。
- **严重等级**（Severity_Level）：患者病情的严重程度。
- **简要描述**（Description）：患者简要的症状描述。
- **预约状态**（Appointment_Status）：预约的状态，如已确认、已取消、已完成等。
- **预约时间变化记录**（Appointment_Time_Change_Record）：记录患者更改预约时间的历史。

### 示例：
| Appointment_ID | Patient_ID | Doctor_ID | Patient_Name | Appointment_Time | Appointment_Category | Severity_Level | Description | Appointment_Status | Appointment_Time_Change_Record |
| -------------- | ---------- | --------- | ------------ | ---------------- | -------------------- | -------------- | ----------- | ------------------ | ------------------------------ |
| 1001           | 101        | 1         | 李明         | 2025-11-14 14:00 | 普通                 | 中等           | 眼部不适    | 已确认             | 无                             |

---

## 3. `patient` 表

### 表结构说明：
- **患者ID**（Patient_ID）：唯一标识每位患者的主键。
- **就诊卡号**（Visit_Card_Number）：患者的就诊卡号。
- **姓名**（Name）：患者的姓名。
- **性别**（Gender）：患者的性别。
- **出生日期**（Date_of_Birth）：患者的出生日期，用于计算年龄。
- **年龄**（Age）：患者的年龄。
- **联系方式**（Phone_Number）：患者的电话号码。
- **地址**（Address）：患者的住址。
- **电子邮件**（Email）：患者的电子邮件地址。
- **紧急联系人**（Emergency_Contact）：紧急联系人姓名。
- **紧急联系人电话**（Emergency_Contact_Phone）：紧急联系人电话号码。
- **就诊日期记录**（Visit_Date）：患者就诊的日期。
- **主诉**（Chief_Complaint）：患者主诉的症状。
- **诊断**（Diagnosis）：患者的诊断结果。
- **治疗方案**（Treatment_Plan）：医生为患者制定的治疗方案。
- **药物治疗**（Medication）：患者正在使用的药物。
- **手术历史**（Surgical_History）：患者是否有手术历史。
- **住院信息**（Hospitalization_Info）：患者住院信息。
- **过敏史**（Allergy_History）：患者是否对某些药物或物质过敏。
- **既往病史**（Medical_History）：患者的既往病史。
- **家族病史**（Family_History）：家族中的病史。
- **眼部检查结果**（Eye_Exam_Results）：眼部检查结果。
- **复诊日期**（Follow_Up_Date）：下次复诊日期。
- **医师姓名**（Physician_Name）：主治医生的姓名。
- **就诊科室**（Department）：患者就诊的科室。
- **医保情况**（Insurance_Status）：患者的医保信息。
- **医保卡号**（Insurance_Card_Number）：医保卡号。

### 示例：
| Patient_ID | Visit_Card_Number | Name | Gender | Date_of_Birth | Age  | Phone_Number | Address | Email             | Emergency_Contact | Emergency_Contact_Phone | Visit_Date | Chief_Complaint | Diagnosis | Treatment_Plan | Medication | Surgical_History | Allergy_History | Medical_History | Family_History | Eye_Exam_Results | Follow_Up_Date | Physician_Name | Department | Insurance_Status | Insurance_Card_Number |
| ---------- | ----------------- | ---- | ------ | ------------- | ---- | ------------ | ------- | ----------------- | ----------------- | ----------------------- | ---------- | --------------- | --------- | -------------- | ---------- | ---------------- | --------------- | --------------- | -------------- | ---------------- | -------------- | -------------- | ---------- | ---------------- | --------------------- |
| 101        | 2025-123456       | 李明 | 男     | 1985-08-01    | 40   | 138XXXXXXX   | 北京市  | example@email.com | 张伟              | 139XXXXXXX              | 2025-11-12 | 眼部不适        | 白内障    | 手术治疗       | 眼药水     | 无               | 无              | 高血压          | 无             | 视力下降         | 2025-11-20     | 张医生         | 眼科       | 有医保           | 123456789012345       |

---

