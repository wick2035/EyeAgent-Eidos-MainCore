-- ============================================================
-- 医疗系统演示数据
-- 生成时间: 2025-11-20 19:54:08
-- ============================================================

USE medical_db;

SET FOREIGN_KEY_CHECKS = 0;


-- 清理触发器生成的空UUID记录
DELETE FROM reminder_config WHERE Config_UUID IS NULL OR Config_UUID = '';


-- ========== 患者数据 (补充10条) ==========
INSERT INTO patient (Patient_ID, Patient_UUID, Name, Gender, Age, Phone_Number, Address, Created_At, Version, Deleted)
  VALUES (14, '062dff06-8af7-4215-9666-d6cf95886aa8', '罗丽', '男', 33, '19604727470', '上海市海淀区和平路7号', NOW(), 0, 0);
INSERT INTO patient (Patient_ID, Patient_UUID, Name, Gender, Age, Phone_Number, Address, Created_At, Version, Deleted)
  VALUES (15, 'ef0fddef-585c-4bc9-95fc-6d1d867eaf25', '何芳', '男', 56, '15131057204', '深圳市朝阳区人民路168号', NOW(), 0, 0);
INSERT INTO patient (Patient_ID, Patient_UUID, Name, Gender, Age, Phone_Number, Address, Created_At, Version, Deleted)
  VALUES (16, 'ca8bddd7-5df6-4b69-9833-7a03059c6ebd', '李涛', '男', 43, '15448531509', '深圳市朝阳区解放路183号', NOW(), 0, 0);
INSERT INTO patient (Patient_ID, Patient_UUID, Name, Gender, Age, Phone_Number, Address, Created_At, Version, Deleted)
  VALUES (17, 'c1e1bf27-a614-4b4a-8d4d-583c9c05a716', '何超', '女', 80, '13605124240', '广州市朝阳区解放路84号', NOW(), 0, 0);
INSERT INTO patient (Patient_ID, Patient_UUID, Name, Gender, Age, Phone_Number, Address, Created_At, Version, Deleted)
  VALUES (18, '4f677e70-9b28-4fc9-9498-a9651a02c800', '马娜', '男', 29, '17117411017', '深圳市浦东区解放路44号', NOW(), 0, 0);
INSERT INTO patient (Patient_ID, Patient_UUID, Name, Gender, Age, Phone_Number, Address, Created_At, Version, Deleted)
  VALUES (19, '620df5a1-189d-4955-a051-1d9a0010afb8', '黄超', '男', 64, '18958491349', '杭州市海淀区建设路121号', NOW(), 0, 0);
INSERT INTO patient (Patient_ID, Patient_UUID, Name, Gender, Age, Phone_Number, Address, Created_At, Version, Deleted)
  VALUES (20, '5524343b-1b56-428b-8aa3-2d4e7a734103', '孙建华', '男', 78, '13958457525', '杭州市天河区和平路197号', NOW(), 0, 0);
INSERT INTO patient (Patient_ID, Patient_UUID, Name, Gender, Age, Phone_Number, Address, Created_At, Version, Deleted)
  VALUES (21, 'd528a20e-dfa5-4768-8c27-fc0bb9046d4e', '孙明', '女', 51, '17807019473', '上海市南山区中山路96号', NOW(), 0, 0);
INSERT INTO patient (Patient_ID, Patient_UUID, Name, Gender, Age, Phone_Number, Address, Created_At, Version, Deleted)
  VALUES (22, '67502405-0c9d-4e94-afc3-28a11e43749e', '朱丽', '男', 45, '17572579741', '广州市南山区中山路30号', NOW(), 0, 0);
INSERT INTO patient (Patient_ID, Patient_UUID, Name, Gender, Age, Phone_Number, Address, Created_At, Version, Deleted)
  VALUES (23, 'a6787d32-77ed-470d-84bf-1b4f6816c5d4', '赵涛', '男', 61, '17840439059', '深圳市南山区建设路187号', NOW(), 0, 0);

-- ========== 药品数据 (补充15条) ==========
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('6', '盐酸左氧氟沙星滴眼液', '5ml:15mg', '滴眼液', 12.5, '某某制药', '抗感染', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('7', '玻璃酸钠滴眼液', '5ml:5mg', '滴眼液', 28.0, '某某制药', '缓解干眼', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('8', '妥布霉素滴眼液', '5ml:15mg', '滴眼液', 15.8, '某某制药', '抗感染', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('9', '氯霉素滴眼液', '8ml:20mg', '滴眼液', 8.5, '某某制药', '抗感染', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('10', '红霉素眼膏', '2g:0.5%', '眼膏', 6.0, '某某制药', '抗感染', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('11', '地塞米松滴眼液', '5ml:5mg', '滴眼液', 18.0, '某某制药', '抗炎', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('12', '双氯芬酸钠滴眼液', '5ml:5mg', '滴眼液', 22.0, '某某制药', '抗炎', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('13', '噻吗洛尔滴眼液', '5ml:25mg', '滴眼液', 35.0, '某某制药', '降眼压', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('14', '拉坦前列素滴眼液', '2.5ml', '滴眼液', 185.0, '某某制药', '降眼压', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('15', '布林佐胺滴眼液', '5ml:10mg', '滴眼液', 158.0, '某某制药', '降眼压', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('16', '七叶洋地黄双苷滴眼液', '5ml', '滴眼液', 42.0, '某某制药', '改善循环', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('17', '维生素A棕榈酸酯眼用凝胶', '5g', '眼用凝胶', 38.0, '某某制药', '角膜营养', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('18', '小牛血去蛋白提取物眼用凝胶', '5g', '眼用凝胶', 68.0, '某某制药', '角膜修复', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('19', '阿昔洛韦滴眼液', '8ml:40mg', '滴眼液', 18.5, '某某制药', '抗病毒', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('20', '更昔洛韦眼用凝胶', '5g:0.15g', '眼用凝胶', 78.0, '某某制药', '抗病毒', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('21', '托吡卡胺滴眼液', '5ml', '滴眼液', 25.0, '某某制药', '散瞳', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('22', '复方托吡卡胺滴眼液', '5ml', '滴眼液', 32.0, '某某制药', '散瞳', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('23', '盐酸卡替洛尔滴眼液', '5ml:10mg', '滴眼液', 45.0, '某某制药', '降眼压', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('24', '贝美前列素滴眼液', '3ml', '滴眼液', 168.0, '某某制药', '降眼压', NOW(), 0, 0);
INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)
  VALUES ('25', '羟丙甲纤维素滴眼液', '10ml', '滴眼液', 16.0, '某某制药', '人工泪液', NOW(), 0, 0);

-- ========== 病例记录 (补充17条) ==========
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (4, '791ecba9-b8eb-47d5-b8e0-e7e968b01650', '620df5a1-189d-4955-a051-1d9a0010afb8', '2025-001001', '2025-07-28', '17:00:00', '眼科', '双眼视力下降', '双眼视力下降', '轻度近视，建议配镜矫正', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (5, '093581cc-b2a7-464e-a02f-90cf91e7fcdc', 'a6787d32-77ed-470d-84bf-1b4f6816c5d4', '2025-001002', '2025-11-02', '15:00:00', '眼科', '眼睛干涩，异物感', '眼睛干涩，异物感', '睑板腺功能障碍，建议热敷和人工泪液', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (6, '8c63c454-2199-4d89-b954-772825cb0c8a', 'a6787d32-77ed-470d-84bf-1b4f6816c5d4', '2025-001003', '2025-08-28', '12:30:00', '眼科', '眼痛、畏光、流泪', '眼痛、畏光、流泪', '单疱病毒性角膜炎，抗病毒治疗', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (7, '515dbfcb-4db1-4e36-a864-a6fb7f6222bd', 'ca8bddd7-5df6-4b69-9833-7a03059c6ebd', '2025-001004', '2025-08-06', '13:30:00', '眼科', '双眼视力下降', '双眼视力下降', '轻度近视，建议配镜矫正', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (8, '5c8c5d0d-81c8-4090-9399-7292ad28bdc8', 'ef0fddef-585c-4bc9-95fc-6d1d867eaf25', '2025-001005', '2025-09-23', '14:30:00', '眼科', '视物模糊，眩光', '视物模糊，眩光', '老年性白内障，建议手术治疗', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (9, '34c0fca9-30d8-409c-bd1f-1ccd242af084', 'a6787d32-77ed-470d-84bf-1b4f6816c5d4', '2025-001006', '2025-09-11', '09:30:00', '眼科', '视野缺损、飞蚊症', '视野缺损、飞蚊症', '孔源性视网膜脱离，需紧急手术', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (10, '09df96be-57c7-47e1-b78d-de307ce5aec4', 'ef0fddef-585c-4bc9-95fc-6d1d867eaf25', '2025-001007', '2025-07-06', '11:00:00', '眼科', '眼睛干涩，异物感', '眼睛干涩，异物感', '睑板腺功能障碍，建议热敷和人工泪液', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (11, '6c330342-c1de-4f51-aac2-69d35b002bad', '67502405-0c9d-4e94-afc3-28a11e43749e', '2025-001008', '2025-10-14', '14:30:00', '眼科', '双眼视力下降', '双眼视力下降', '轻度近视，建议配镜矫正', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (12, 'a25f2b28-09a6-4d45-a709-bcd2454ea213', '062dff06-8af7-4215-9666-d6cf95886aa8', '2025-001009', '2025-09-06', '11:30:00', '眼科', '视野缺损、飞蚊症', '视野缺损、飞蚊症', '孔源性视网膜脱离，需紧急手术', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (13, '5c7638ff-2caa-42c1-aea2-0b6e9786777f', '67502405-0c9d-4e94-afc3-28a11e43749e', '2025-001010', '2025-06-02', '08:00:00', '眼科', '眼红、分泌物增多', '眼红、分泌物增多', '细菌性结膜炎，抗生素眼药水治疗', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (14, '9d1bf408-c54c-4aa3-a050-94412cc7c3da', 'a6787d32-77ed-470d-84bf-1b4f6816c5d4', '2025-001011', '2025-07-17', '12:00:00', '眼科', '双眼视力下降', '双眼视力下降', '轻度近视，建议配镜矫正', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (15, '1588b7b6-6e3a-438e-94f5-8250ca0c1458', '67502405-0c9d-4e94-afc3-28a11e43749e', '2025-001012', '2025-09-17', '08:00:00', '眼科', '视物变形、中心视力下降', '视物变形、中心视力下降', '年龄相关性黄斑变性，玻璃体腔注药', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (16, '2a398014-ac24-4a7f-a91b-23790c373a4c', '620df5a1-189d-4955-a051-1d9a0010afb8', '2025-001013', '2025-07-26', '16:00:00', '眼科', '眼压升高，视野缺损', '眼压升高，视野缺损', '原发性开角型青光眼，需长期药物治疗', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (17, 'cca05a2e-0ade-46d7-aaa5-9050dc3aa963', '67502405-0c9d-4e94-afc3-28a11e43749e', '2025-001014', '2025-11-04', '09:00:00', '眼科', '视物变形、中心视力下降', '视物变形、中心视力下降', '年龄相关性黄斑变性，玻璃体腔注药', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (18, 'af491b0e-cc97-4cb5-b858-8a5a94afbdb1', '4f677e70-9b28-4fc9-9498-a9651a02c800', '2025-001015', '2025-11-13', '09:30:00', '眼科', '视物模糊，眩光', '视物模糊，眩光', '老年性白内障，建议手术治疗', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (19, '0a920f13-d4aa-4fbe-bd5d-2726809763d3', 'c1e1bf27-a614-4b4a-8d4d-583c9c05a716', '2025-001016', '2025-09-15', '15:00:00', '眼科', '眼红、分泌物增多', '眼红、分泌物增多', '细菌性结膜炎，抗生素眼药水治疗', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (20, 'e79c431d-34da-4dfc-9f9a-c0ed7a42dc46', '4f677e70-9b28-4fc9-9498-a9651a02c800', '2025-001017', '2025-05-25', '13:30:00', '眼科', '双眼视力下降', '双眼视力下降', '轻度近视，建议配镜矫正', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (21, 'f4ed22c8-916d-46fe-8c89-2315560b33c5', 'a6787d32-77ed-470d-84bf-1b4f6816c5d4', '2025-001018', '2025-10-26', '17:00:00', '眼科', '视物模糊，眩光', '视物模糊，眩光', '老年性白内障，建议手术治疗', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (22, 'd07264e9-b901-454a-bbc1-b4e367bcc226', 'ca8bddd7-5df6-4b69-9833-7a03059c6ebd', '2025-001019', '2025-08-22', '12:30:00', '眼科', '视野缺损、飞蚊症', '视野缺损、飞蚊症', '孔源性视网膜脱离，需紧急手术', '观察治疗，定期复查', NOW(), 0, 0);
INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)
  VALUES (23, '7cb502c1-2044-4969-9da8-3d0569d518d0', 'c1e1bf27-a614-4b4a-8d4d-583c9c05a716', '2025-001020', '2025-08-23', '13:00:00', '眼科', '视物模糊，眩光', '视物模糊，眩光', '老年性白内障，建议手术治疗', '观察治疗，定期复查', NOW(), 0, 0);

-- ========== 预约数据 (新增15条) ==========
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (1, '360a0196-be42-4fc8-8118-87cbf8d1ffe5', '062dff06-8af7-4215-9666-d6cf95886aa8', 'doctor-uuid-4', 'a25f2b28-09a6-4d45-a709-bcd2454ea213', '2025-11-25 09:19:42', '专家门诊', '紧急', '已预约', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (2, '27c107df-0295-45b8-a50f-2d343b76520b', '620df5a1-189d-4955-a051-1d9a0010afb8', 'doctor-uuid-2', '791ecba9-b8eb-47d5-b8e0-e7e968b01650', '2025-11-23 11:05:53', '急诊', '紧急', '已完成', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (3, '4c032a78-994f-46c7-9283-9e681e02d34b', 'a6787d32-77ed-470d-84bf-1b4f6816c5d4', 'doctor-uuid-2', '093581cc-b2a7-464e-a02f-90cf91e7fcdc', '2025-11-21 15:38:52', '专家门诊', '普通', '已取消', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (4, 'c1e56857-1aca-4e65-a36c-73ac1b1e6307', 'c1e1bf27-a614-4b4a-8d4d-583c9c05a716', 'doctor-uuid-4', '7cb502c1-2044-4969-9da8-3d0569d518d0', '2025-11-19 01:23:23', '普通门诊', '非常紧急', '已取消', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (5, '27a33020-b9e4-43e2-8e6c-dd0925b863d7', '4f677e70-9b28-4fc9-9498-a9651a02c800', 'doctor-uuid-2', 'e79c431d-34da-4dfc-9f9a-c0ed7a42dc46', '2025-11-27 13:07:16', '专家门诊', '紧急', '已完成', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (6, 'a8d5988c-a56e-432e-8300-b44e1426aeb6', '4f677e70-9b28-4fc9-9498-a9651a02c800', 'doctor-uuid-1', 'af491b0e-cc97-4cb5-b858-8a5a94afbdb1', '2025-10-29 12:30:11', '普通门诊', '普通', '已取消', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (7, '050d53e6-6e48-47cb-a017-ba4cac22d059', 'd528a20e-dfa5-4768-8c27-fc0bb9046d4e', 'doctor-uuid-3', '2a398014-ac24-4a7f-a91b-23790c373a4c', '2025-11-27 06:09:38', '急诊', '非常紧急', '已完成', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (8, '97e3ef94-efc9-451d-ba15-1528e4f1ec6d', 'ca8bddd7-5df6-4b69-9833-7a03059c6ebd', 'doctor-uuid-3', '515dbfcb-4db1-4e36-a864-a6fb7f6222bd', '2025-11-07 22:19:45', '专家门诊', '非常紧急', '已完成', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (9, '7876ab8b-320d-46a7-a075-c6eda6f26385', '620df5a1-189d-4955-a051-1d9a0010afb8', 'doctor-uuid-3', '791ecba9-b8eb-47d5-b8e0-e7e968b01650', '2025-11-05 07:45:13', '普通门诊', '紧急', '已完成', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (10, '27bc5e87-2270-413f-97df-ec6724857bdb', 'ef0fddef-585c-4bc9-95fc-6d1d867eaf25', 'doctor-uuid-3', '09df96be-57c7-47e1-b78d-de307ce5aec4', '2025-11-16 23:51:28', '急诊', '普通', '已取消', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (11, 'c6783ec7-28fb-415c-9c17-9286d108f5f9', '67502405-0c9d-4e94-afc3-28a11e43749e', 'doctor-uuid-1', '5c7638ff-2caa-42c1-aea2-0b6e9786777f', '2025-10-30 23:56:00', '专家门诊', '普通', '已预约', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (12, 'a1e08568-ba06-4f8f-a57c-a7eb192198a2', 'a6787d32-77ed-470d-84bf-1b4f6816c5d4', 'doctor-uuid-3', '8c63c454-2199-4d89-b954-772825cb0c8a', '2025-11-01 08:20:08', '专家门诊', '非常紧急', '已预约', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (13, '84952b53-490c-425e-bf29-2f676dab0177', 'a6787d32-77ed-470d-84bf-1b4f6816c5d4', 'doctor-uuid-4', '34c0fca9-30d8-409c-bd1f-1ccd242af084', '2025-10-26 20:56:27', '普通门诊', '非常紧急', '已完成', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (14, '63801db0-4f5f-45f8-91b9-f7ad0040c1e3', '5524343b-1b56-428b-8aa3-2d4e7a734103', 'doctor-uuid-1', '6c330342-c1de-4f51-aac2-69d35b002bad', '2025-11-07 03:25:58', '专家门诊', '非常紧急', '已取消', '预约就诊', NOW(), 0, 0);
INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)
  VALUES (15, 'd62117d1-7801-48ab-9a76-886ec3932b3d', 'a6787d32-77ed-470d-84bf-1b4f6816c5d4', 'doctor-uuid-1', '093581cc-b2a7-464e-a02f-90cf91e7fcdc', '2025-11-23 04:35:40', '急诊', '紧急', '已取消', '预约就诊', NOW(), 0, 0);

-- ========== 处方主表 (补充8条) ==========
INSERT INTO prescription (Prescription_ID, Prescription_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Prescription_Number, Prescription_Date, Prescription_Type, Diagnosis_Description, Total_Amount, Prescription_Status, Prescriber_Name, Created_At, Version, Deleted)
  VALUES (3, '7be42f2a-9cf5-4daf-a275-1982062eec6e', 'c1e1bf27-a614-4b4a-8d4d-583c9c05a716', 'doctor-uuid-1', '0a920f13-d4aa-4fbe-bd5d-2726809763d3', 'RX-2025-10001', '2025-09-24', '急诊', '细菌性结膜炎，抗生素眼药水治疗', 138.36, '已开立', '医生1', NOW(), 0, 0);
INSERT INTO prescription (Prescription_ID, Prescription_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Prescription_Number, Prescription_Date, Prescription_Type, Diagnosis_Description, Total_Amount, Prescription_Status, Prescriber_Name, Created_At, Version, Deleted)
  VALUES (4, 'fcfc419a-1618-4ee7-af79-8815a80c627b', 'a6787d32-77ed-470d-84bf-1b4f6816c5d4', 'doctor-uuid-5', 'f4ed22c8-916d-46fe-8c89-2315560b33c5', 'RX-2025-10002', '2025-11-06', '慢性病', '老年性白内障，建议手术治疗', 176.12, '已开立', '医生5', NOW(), 0, 0);
INSERT INTO prescription (Prescription_ID, Prescription_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Prescription_Number, Prescription_Date, Prescription_Type, Diagnosis_Description, Total_Amount, Prescription_Status, Prescriber_Name, Created_At, Version, Deleted)
  VALUES (5, '3455cf97-198c-4fc8-91ba-ce8cdf6716d6', 'ef0fddef-585c-4bc9-95fc-6d1d867eaf25', 'doctor-uuid-1', '09df96be-57c7-47e1-b78d-de307ce5aec4', 'RX-2025-10003', '2025-10-13', '普通', '睑板腺功能障碍，建议热敷和人工泪液', 232.94, '已开立', '医生1', NOW(), 0, 0);
INSERT INTO prescription (Prescription_ID, Prescription_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Prescription_Number, Prescription_Date, Prescription_Type, Diagnosis_Description, Total_Amount, Prescription_Status, Prescriber_Name, Created_At, Version, Deleted)
  VALUES (6, '1e213b97-a828-4612-84a9-f2898da2e22a', 'ef0fddef-585c-4bc9-95fc-6d1d867eaf25', 'doctor-uuid-3', '09df96be-57c7-47e1-b78d-de307ce5aec4', 'RX-2025-10004', '2025-09-27', '慢性病', '睑板腺功能障碍，建议热敷和人工泪液', 61.65, '已开立', '医生3', NOW(), 0, 0);
INSERT INTO prescription (Prescription_ID, Prescription_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Prescription_Number, Prescription_Date, Prescription_Type, Diagnosis_Description, Total_Amount, Prescription_Status, Prescriber_Name, Created_At, Version, Deleted)
  VALUES (7, 'b88516b7-b522-46d5-8134-0225e168c0ba', '5524343b-1b56-428b-8aa3-2d4e7a734103', 'doctor-uuid-1', NULL, 'RX-2025-10005', '2025-10-21', '慢性病', '常规用药', 117.1, '已开立', '医生1', NOW(), 0, 0);
INSERT INTO prescription (Prescription_ID, Prescription_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Prescription_Number, Prescription_Date, Prescription_Type, Diagnosis_Description, Total_Amount, Prescription_Status, Prescriber_Name, Created_At, Version, Deleted)
  VALUES (8, '14be4e2d-1eec-48f7-af8b-b1fa1cbeff6c', 'ef0fddef-585c-4bc9-95fc-6d1d867eaf25', 'doctor-uuid-4', '5c8c5d0d-81c8-4090-9399-7292ad28bdc8', 'RX-2025-10006', '2025-11-03', '急诊', '老年性白内障，建议手术治疗', 205.33, '已开立', '医生4', NOW(), 0, 0);
INSERT INTO prescription (Prescription_ID, Prescription_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Prescription_Number, Prescription_Date, Prescription_Type, Diagnosis_Description, Total_Amount, Prescription_Status, Prescriber_Name, Created_At, Version, Deleted)
  VALUES (9, 'bcbaf246-7d8d-4a9d-a925-11948ff953e7', '620df5a1-189d-4955-a051-1d9a0010afb8', 'doctor-uuid-1', '791ecba9-b8eb-47d5-b8e0-e7e968b01650', 'RX-2025-10007', '2025-09-27', '慢性病', '轻度近视，建议配镜矫正', 125.68, '已开立', '医生1', NOW(), 0, 0);
INSERT INTO prescription (Prescription_ID, Prescription_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Prescription_Number, Prescription_Date, Prescription_Type, Diagnosis_Description, Total_Amount, Prescription_Status, Prescriber_Name, Created_At, Version, Deleted)
  VALUES (10, '14d9135e-9dba-4c1d-8ac2-4dedc021681f', 'ca8bddd7-5df6-4b69-9833-7a03059c6ebd', 'doctor-uuid-3', '515dbfcb-4db1-4e36-a864-a6fb7f6222bd', 'RX-2025-10008', '2025-10-02', '慢性病', '轻度近视，建议配镜矫正', 256.98, '已开立', '医生3', NOW(), 0, 0);
INSERT INTO prescription (Prescription_ID, Prescription_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Prescription_Number, Prescription_Date, Prescription_Type, Diagnosis_Description, Total_Amount, Prescription_Status, Prescriber_Name, Created_At, Version, Deleted)
  VALUES (11, 'b8634432-dc0d-4cd9-a943-8edcb8d936e1', '620df5a1-189d-4955-a051-1d9a0010afb8', 'doctor-uuid-2', '791ecba9-b8eb-47d5-b8e0-e7e968b01650', 'RX-2025-10009', '2025-10-20', '普通', '轻度近视，建议配镜矫正', 183.98, '已开立', '医生2', NOW(), 0, 0);
INSERT INTO prescription (Prescription_ID, Prescription_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Prescription_Number, Prescription_Date, Prescription_Type, Diagnosis_Description, Total_Amount, Prescription_Status, Prescriber_Name, Created_At, Version, Deleted)
  VALUES (12, '888c9196-1ba6-4be1-9b12-ee49865d827a', '062dff06-8af7-4215-9666-d6cf95886aa8', 'doctor-uuid-1', 'a25f2b28-09a6-4d45-a709-bcd2454ea213', 'RX-2025-10010', '2025-09-25', '慢性病', '孔源性视网膜脱离，需紧急手术', 112.46, '已开立', '医生1', NOW(), 0, 0);

-- ========== 处方详情 (每个处方3种药品) ==========
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (5, '028e1b9a-8cb5-4f13-b462-a31d7453ac1e', '7be42f2a-9cf5-4daf-a275-1982062eec6e', 8, '妥布霉素滴眼液', '5ml:15mg', 1, '盒', '1滴/次', '每日4次', '14天', '滴眼', 15.8, 15.8, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (6, 'a320a36c-42c0-4437-a79e-e6320c626bd0', '7be42f2a-9cf5-4daf-a275-1982062eec6e', 6, '盐酸左氧氟沙星滴眼液', '5ml:15mg', 1, '盒', '1滴/次', '每日4次', '14天', '滴眼', 12.5, 12.5, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (7, '4edfe185-918c-4fce-98a9-7c4931169134', '7be42f2a-9cf5-4daf-a275-1982062eec6e', 25, '羟丙甲纤维素滴眼液', '10ml', 1, '盒', '1滴/次', '每日4次', '14天', '滴眼', 16.0, 16.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (8, '77be65b9-8540-4fd4-b606-23091e8c5020', 'fcfc419a-1618-4ee7-af79-8815a80c627b', 22, '复方托吡卡胺滴眼液', '5ml', 2, '盒', '1滴/次', '每日2次', '21天', '滴眼', 32.0, 64.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (9, '338f8576-c12c-4aa2-b350-bb2ffacb5b53', 'fcfc419a-1618-4ee7-af79-8815a80c627b', 7, '玻璃酸钠滴眼液', '5ml:5mg', 3, '盒', '1滴/次', '每日1次', '21天', '滴眼', 28.0, 84.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (10, '3f0ee62a-9b77-42be-9357-c3514bd7e7e5', 'fcfc419a-1618-4ee7-af79-8815a80c627b', 12, '双氯芬酸钠滴眼液', '5ml:5mg', 2, '盒', '1滴/次', '每日2次', '14天', '滴眼', 22.0, 44.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (11, '7ca1208b-3e5b-44f7-8060-64337dcb0c0a', '3455cf97-198c-4fc8-91ba-ce8cdf6716d6', 14, '拉坦前列素滴眼液', '2.5ml', 2, '盒', '1滴/次', '每日4次', '10天', '滴眼', 185.0, 370.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (12, '6c353b4d-fa85-4f10-8cb5-139ff646f422', '3455cf97-198c-4fc8-91ba-ce8cdf6716d6', 8, '妥布霉素滴眼液', '5ml:15mg', 2, '盒', '1滴/次', '每日4次', '14天', '滴眼', 15.8, 31.6, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (13, '42657638-71ad-4943-9933-a94af6c5ba69', '3455cf97-198c-4fc8-91ba-ce8cdf6716d6', 16, '七叶洋地黄双苷滴眼液', '5ml', 3, '盒', '1滴/次', '每日2次', '21天', '滴眼', 42.0, 126.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (14, '67ce7ac8-18b6-435a-a1b9-af142ca8c613', '1e213b97-a828-4612-84a9-f2898da2e22a', 14, '拉坦前列素滴眼液', '2.5ml', 3, '盒', '1滴/次', '每日1次', '14天', '滴眼', 185.0, 555.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (15, '02e10fad-87eb-49ac-bd51-cd34a567a36b', '1e213b97-a828-4612-84a9-f2898da2e22a', 23, '盐酸卡替洛尔滴眼液', '5ml:10mg', 3, '盒', '1滴/次', '每日1次', '10天', '滴眼', 45.0, 135.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (16, 'bcbe37c5-c268-4a39-9716-061c8c220436', '1e213b97-a828-4612-84a9-f2898da2e22a', 25, '羟丙甲纤维素滴眼液', '10ml', 2, '盒', '1滴/次', '每日1次', '10天', '滴眼', 16.0, 32.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (17, '26823174-273a-40a4-acde-f7d42a023253', 'b88516b7-b522-46d5-8134-0225e168c0ba', 21, '托吡卡胺滴眼液', '5ml', 1, '盒', '1滴/次', '每日2次', '10天', '滴眼', 25.0, 25.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (18, 'b6c3ed65-d159-4216-95fe-7d4fd96df2f4', 'b88516b7-b522-46d5-8134-0225e168c0ba', 19, '阿昔洛韦滴眼液', '8ml:40mg', 1, '盒', '1滴/次', '每日2次', '10天', '滴眼', 18.5, 18.5, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (19, '5ff8d2d8-6ef4-4b30-acce-42c32feaaf3f', 'b88516b7-b522-46d5-8134-0225e168c0ba', 18, '小牛血去蛋白提取物眼用凝胶', '5g', 3, '盒', '适量', '每日1次', '10天', '口服', 68.0, 204.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (20, '3f06ec20-2e8a-436f-a944-db42d32f3dcc', '14be4e2d-1eec-48f7-af8b-b1fa1cbeff6c', 23, '盐酸卡替洛尔滴眼液', '5ml:10mg', 3, '盒', '1滴/次', '每日2次', '7天', '滴眼', 45.0, 135.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (21, '6c6eaa7b-2f31-4577-89c0-93a605e1db63', '14be4e2d-1eec-48f7-af8b-b1fa1cbeff6c', 9, '氯霉素滴眼液', '8ml:20mg', 3, '盒', '1滴/次', '每日1次', '21天', '滴眼', 8.5, 25.5, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (22, '6c057bd4-5670-49c8-9f10-0ed89af894d9', '14be4e2d-1eec-48f7-af8b-b1fa1cbeff6c', 6, '盐酸左氧氟沙星滴眼液', '5ml:15mg', 3, '盒', '1滴/次', '每日1次', '10天', '滴眼', 12.5, 37.5, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (23, 'c2eeb395-930e-4e01-9c05-953e7590a48d', 'bcbaf246-7d8d-4a9d-a925-11948ff953e7', 13, '噻吗洛尔滴眼液', '5ml:25mg', 1, '盒', '1滴/次', '每日2次', '14天', '滴眼', 35.0, 35.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (24, 'f4358553-6193-48ad-8e37-5187c79f6cb5', 'bcbaf246-7d8d-4a9d-a925-11948ff953e7', 6, '盐酸左氧氟沙星滴眼液', '5ml:15mg', 3, '盒', '1滴/次', '每日1次', '10天', '滴眼', 12.5, 37.5, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (25, '3cbc2b6d-e479-47e7-8859-cf220c6e8ccd', 'bcbaf246-7d8d-4a9d-a925-11948ff953e7', 22, '复方托吡卡胺滴眼液', '5ml', 3, '盒', '1滴/次', '每日3次', '21天', '滴眼', 32.0, 96.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (26, 'b085b872-da4c-45f7-8915-359872ebcad7', '14d9135e-9dba-4c1d-8ac2-4dedc021681f', 19, '阿昔洛韦滴眼液', '8ml:40mg', 3, '盒', '1滴/次', '每日4次', '14天', '滴眼', 18.5, 55.5, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (27, 'e85d244f-4566-4c53-9545-26c6becce759', '14d9135e-9dba-4c1d-8ac2-4dedc021681f', 12, '双氯芬酸钠滴眼液', '5ml:5mg', 3, '盒', '1滴/次', '每日2次', '21天', '滴眼', 22.0, 66.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (28, '1f8a85c0-991a-4146-b0cb-af08e291c7d1', '14d9135e-9dba-4c1d-8ac2-4dedc021681f', 8, '妥布霉素滴眼液', '5ml:15mg', 3, '盒', '1滴/次', '每日4次', '21天', '滴眼', 15.8, 47.4, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (29, 'eb1a983a-10ca-4c4a-84c8-513a6e55983a', 'b8634432-dc0d-4cd9-a943-8edcb8d936e1', 11, '地塞米松滴眼液', '5ml:5mg', 1, '盒', '1滴/次', '每日3次', '7天', '滴眼', 18.0, 18.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (30, 'bfdfca3d-17a2-4cb8-b7b7-84fcbb625b17', 'b8634432-dc0d-4cd9-a943-8edcb8d936e1', 7, '玻璃酸钠滴眼液', '5ml:5mg', 1, '盒', '1滴/次', '每日1次', '14天', '滴眼', 28.0, 28.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (31, 'a374d03b-640b-4ca6-92bc-edda9e4a3309', 'b8634432-dc0d-4cd9-a943-8edcb8d936e1', 19, '阿昔洛韦滴眼液', '8ml:40mg', 3, '盒', '1滴/次', '每日3次', '14天', '滴眼', 18.5, 55.5, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (32, '6f583f1e-7285-4cad-b588-840f60f605bb', '888c9196-1ba6-4be1-9b12-ee49865d827a', 18, '小牛血去蛋白提取物眼用凝胶', '5g', 2, '盒', '适量', '每日4次', '7天', '口服', 68.0, 136.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (33, 'cfef97f2-65df-4da8-ac44-d960946c57cd', '888c9196-1ba6-4be1-9b12-ee49865d827a', 21, '托吡卡胺滴眼液', '5ml', 3, '盒', '1滴/次', '每日2次', '7天', '滴眼', 25.0, 75.0, NOW(), 0, 0);
INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)
  VALUES (34, '7bef61c6-27a4-468f-8dd2-60c38c530da5', '888c9196-1ba6-4be1-9b12-ee49865d827a', 16, '七叶洋地黄双苷滴眼液', '5ml', 2, '盒', '1滴/次', '每日1次', '10天', '滴眼', 42.0, 84.0, NOW(), 0, 0);

-- ========== 医生时间段 (未来7天) ==========
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (1, '3152ff10-d390-47c4-abce-4591aa63df25', 'doctor-uuid-1', '2025-11-20', '12:00:00', '15:00:00', 7, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (2, '2bd0589d-2402-4d2b-99b8-c41d156830cc', 'doctor-uuid-1', '2025-11-20', '10:00:00', '17:00:00', 7, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (3, '82122603-7ece-4c71-9194-a4cd88dfbcee', 'doctor-uuid-1', '2025-11-20', '11:00:00', '17:00:00', 8, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (4, 'd4a5ae06-509c-4cee-87ff-5e9ad4e9b3ba', 'doctor-uuid-2', '2025-11-20', '10:00:00', '09:00:00', 4, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (5, 'e68893c5-26f4-4502-9f12-6be48ac5195d', 'doctor-uuid-2', '2025-11-20', '12:00:00', '11:00:00', 4, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (6, 'd51fe8aa-d137-4fab-8c19-26ef79afa888', 'doctor-uuid-2', '2025-11-20', '09:00:00', '13:00:00', 5, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (7, 'e4dfe8cd-8ab7-4f52-85d7-46ba1373cef0', 'doctor-uuid-3', '2025-11-20', '16:00:00', '17:00:00', 4, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (8, '8caf011c-1f13-4e5f-b5cf-71e5c97c1c91', 'doctor-uuid-3', '2025-11-20', '13:00:00', '13:00:00', 5, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (9, '3b1fd795-7772-4639-9bcb-98488761cbdf', 'doctor-uuid-3', '2025-11-20', '11:00:00', '10:00:00', 8, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (10, 'face0913-a585-4a23-a1b4-8df2f465079c', 'doctor-uuid-4', '2025-11-20', '12:00:00', '14:00:00', 6, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (11, '1a70e001-2377-4cb9-a37f-6aae68f260bd', 'doctor-uuid-4', '2025-11-20', '12:00:00', '13:00:00', 6, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (12, '7b09693b-6a16-4cdf-b8e3-9c598510acf7', 'doctor-uuid-4', '2025-11-20', '14:00:00', '11:00:00', 3, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (13, 'bb6f93ec-25c7-4784-a70e-017c4a0bd7d8', 'doctor-uuid-5', '2025-11-20', '13:00:00', '18:00:00', 5, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (14, '3280977b-d947-4d64-8146-5a08e3926656', 'doctor-uuid-5', '2025-11-20', '14:00:00', '16:00:00', 6, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (15, 'd9520633-e722-4f8b-be7e-8d70c29c5e68', 'doctor-uuid-5', '2025-11-20', '14:00:00', '11:00:00', 4, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (16, 'd4959af4-2863-49af-80a9-938a6d2b3e00', 'doctor-uuid-1', '2025-11-21', '10:00:00', '14:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (17, '4d6bed23-5346-4b07-93d6-34f70f3fd3fc', 'doctor-uuid-1', '2025-11-21', '15:00:00', '11:00:00', 5, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (18, 'd451add4-9523-468f-98fd-d4b2c2c6ca9a', 'doctor-uuid-2', '2025-11-21', '10:00:00', '17:00:00', 4, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (19, '1eed588b-03fa-4c94-b10b-be9462ea3ac1', 'doctor-uuid-2', '2025-11-21', '13:00:00', '11:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (20, 'b6a0f2c5-c21e-4b66-a43a-6e4d365bad17', 'doctor-uuid-2', '2025-11-21', '11:00:00', '16:00:00', 5, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (21, 'e7a49180-e135-4d2c-a340-d0d2b65e764b', 'doctor-uuid-3', '2025-11-21', '10:00:00', '12:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (22, '698bfc09-7f2b-4317-aafc-dd0b54ef1513', 'doctor-uuid-3', '2025-11-21', '14:00:00', '12:00:00', 5, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (23, 'c6acd7d3-c94e-4341-a772-1f8e327b72c8', 'doctor-uuid-4', '2025-11-21', '11:00:00', '14:00:00', 8, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (24, 'dd2f846c-b124-4090-b3eb-f54cf07a2f49', 'doctor-uuid-4', '2025-11-21', '16:00:00', '18:00:00', 5, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (25, '5d1246ac-0ded-4718-8ad7-ee3c9dff1236', 'doctor-uuid-5', '2025-11-21', '10:00:00', '13:00:00', 5, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (26, '37994785-ea66-4ec3-b6c7-c1699d99e1d2', 'doctor-uuid-5', '2025-11-21', '16:00:00', '13:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (27, '7200fec9-54c2-4d38-9fb0-17457a22633b', 'doctor-uuid-5', '2025-11-21', '10:00:00', '16:00:00', 6, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (28, 'b8865684-c5c0-4dae-9276-da29d0996b8f', 'doctor-uuid-1', '2025-11-22', '14:00:00', '18:00:00', 3, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (29, 'bd2e7380-f022-4059-be28-7d48b0317fdd', 'doctor-uuid-1', '2025-11-22', '16:00:00', '16:00:00', 4, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (30, '63071eda-9201-484d-a630-08df46b20d25', 'doctor-uuid-1', '2025-11-22', '11:00:00', '12:00:00', 4, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (31, 'e9796efb-6b4e-4803-9fc7-3df5be608e9b', 'doctor-uuid-2', '2025-11-22', '12:00:00', '14:00:00', 3, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (32, '37f6d908-0c06-45f4-8798-eee4282263be', 'doctor-uuid-2', '2025-11-22', '12:00:00', '14:00:00', 8, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (33, 'fe26a761-1a0c-44c3-bf5d-a657e560c005', 'doctor-uuid-3', '2025-11-22', '13:00:00', '09:00:00', 3, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (34, '297c3b7e-8eec-45fb-8775-0a87a94203d0', 'doctor-uuid-3', '2025-11-22', '13:00:00', '14:00:00', 7, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (35, 'f9bed3a5-e4bd-4718-a544-19cc01f6d1b4', 'doctor-uuid-4', '2025-11-22', '13:00:00', '14:00:00', 5, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (36, 'cf3a34f4-0bfc-4eab-971f-c2d8e496f604', 'doctor-uuid-4', '2025-11-22', '16:00:00', '10:00:00', 5, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (37, '11b50e1d-b351-46ad-90d3-da72c9ccabea', 'doctor-uuid-4', '2025-11-22', '15:00:00', '12:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (38, '1a949c35-200f-4dcc-b627-f4cb9cb01ede', 'doctor-uuid-5', '2025-11-22', '13:00:00', '11:00:00', 5, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (39, '5e1c5f81-b631-4bd6-abc9-96fbb87f4cc6', 'doctor-uuid-5', '2025-11-22', '15:00:00', '16:00:00', 6, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (40, 'f3ad02ef-34f3-4c2b-b06d-5e9a70251d53', 'doctor-uuid-1', '2025-11-23', '08:00:00', '16:00:00', 6, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (41, '86414802-163c-4a72-be9e-82e04b2822d5', 'doctor-uuid-1', '2025-11-23', '13:00:00', '18:00:00', 7, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (42, '376abebd-b3a9-4687-bbbb-93dfcef9cb20', 'doctor-uuid-1', '2025-11-23', '10:00:00', '09:00:00', 4, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (43, 'c3518b7e-ef22-4a65-adc0-4f13d2079860', 'doctor-uuid-2', '2025-11-23', '16:00:00', '13:00:00', 4, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (44, 'daf722c1-978c-4566-b9eb-5e6177818bd5', 'doctor-uuid-2', '2025-11-23', '08:00:00', '18:00:00', 4, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (45, 'b6e5b460-dd9d-412c-86a2-fa192f676744', 'doctor-uuid-3', '2025-11-23', '12:00:00', '13:00:00', 6, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (46, 'd5051d3c-8fa8-4112-b403-d9efe11d51f2', 'doctor-uuid-3', '2025-11-23', '13:00:00', '10:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (47, '95f2b2af-40ce-4f9d-b532-34da438b662d', 'doctor-uuid-4', '2025-11-23', '12:00:00', '13:00:00', 6, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (48, 'f27c3e66-b326-4b2a-bdd7-6270f95d8e8c', 'doctor-uuid-4', '2025-11-23', '13:00:00', '10:00:00', 6, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (49, 'fef3d64e-1ae2-4dea-b801-e95f486d013b', 'doctor-uuid-5', '2025-11-23', '16:00:00', '16:00:00', 3, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (50, 'f50f30cb-c929-493e-a913-77f48c478877', 'doctor-uuid-5', '2025-11-23', '08:00:00', '13:00:00', 3, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (51, 'd70ed983-96ed-4112-94d3-c56049b2b0a4', 'doctor-uuid-5', '2025-11-23', '11:00:00', '11:00:00', 6, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (52, '8f564fbd-c88d-4ada-b0e6-fe5c2f19012f', 'doctor-uuid-1', '2025-11-24', '09:00:00', '15:00:00', 4, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (53, '60734b7d-dcab-437d-9fdc-3de59e5f67f8', 'doctor-uuid-1', '2025-11-24', '08:00:00', '11:00:00', 5, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (54, '3302f306-b3ed-456a-8262-d81557090c74', 'doctor-uuid-1', '2025-11-24', '09:00:00', '10:00:00', 3, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (55, 'b88d0db2-ab90-4364-92fb-0eaa9b314811', 'doctor-uuid-2', '2025-11-24', '08:00:00', '13:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (56, 'c930e413-c501-4b85-9fc9-30d20977dd57', 'doctor-uuid-2', '2025-11-24', '10:00:00', '11:00:00', 4, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (57, 'f3425316-92e9-4479-8f15-425838159a0e', 'doctor-uuid-3', '2025-11-24', '09:00:00', '12:00:00', 8, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (58, 'd562fc3a-bc63-49b6-9a51-781f19a80c20', 'doctor-uuid-3', '2025-11-24', '12:00:00', '15:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (59, '7660b539-2791-4271-801b-11dfad2b168b', 'doctor-uuid-4', '2025-11-24', '14:00:00', '10:00:00', 8, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (60, 'e499d8b0-fb64-48db-81c1-7b87dcad5a4f', 'doctor-uuid-4', '2025-11-24', '13:00:00', '16:00:00', 4, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (61, 'f389ce22-62da-470c-8224-ce15299fad6d', 'doctor-uuid-5', '2025-11-24', '16:00:00', '17:00:00', 5, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (62, '5c9e76a2-8f10-4952-8d6d-2fdca82f54d4', 'doctor-uuid-5', '2025-11-24', '08:00:00', '16:00:00', 4, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (63, '27788798-7c4f-45ab-8136-f71b7373c9d0', 'doctor-uuid-5', '2025-11-24', '08:00:00', '13:00:00', 6, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (64, 'bad03aa1-bc31-4164-939a-b896c497001c', 'doctor-uuid-1', '2025-11-25', '14:00:00', '15:00:00', 8, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (65, '8ca0693b-84fc-4289-ab52-8b9a2f5b57f0', 'doctor-uuid-1', '2025-11-25', '11:00:00', '16:00:00', 6, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (66, '004debf0-3c9e-4cd2-a670-2d8165beb2c3', 'doctor-uuid-1', '2025-11-25', '12:00:00', '17:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (67, '3c1cd581-83e8-4149-b79d-180da82497d8', 'doctor-uuid-2', '2025-11-25', '14:00:00', '09:00:00', 6, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (68, 'eb184ab5-e885-4a92-8c92-b7aeefbbde3c', 'doctor-uuid-2', '2025-11-25', '10:00:00', '15:00:00', 5, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (69, '56033c49-2834-420f-8ea8-f27f78dfc9f7', 'doctor-uuid-3', '2025-11-25', '11:00:00', '15:00:00', 6, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (70, '71a5d8c8-0674-4b92-8765-235261ca095b', 'doctor-uuid-3', '2025-11-25', '10:00:00', '16:00:00', 4, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (71, 'd58ef05d-9e14-42a7-af18-78d784eb591f', 'doctor-uuid-4', '2025-11-25', '08:00:00', '10:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (72, '0cb6bae8-b7c4-407d-b850-278d7bcd398c', 'doctor-uuid-4', '2025-11-25', '16:00:00', '14:00:00', 3, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (73, 'efa8daf7-6682-4d47-9046-ad3becf58dfb', 'doctor-uuid-4', '2025-11-25', '11:00:00', '14:00:00', 4, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (74, '3f6455a5-7e70-4d56-a27a-83cf5c814733', 'doctor-uuid-5', '2025-11-25', '13:00:00', '10:00:00', 3, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (75, 'b7d8c08b-01ca-42f7-a0bf-048c68166877', 'doctor-uuid-5', '2025-11-25', '10:00:00', '13:00:00', 8, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (76, '5b1cb8d3-db76-4072-8980-2b7cc6838951', 'doctor-uuid-5', '2025-11-25', '14:00:00', '12:00:00', 7, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (77, 'c0913017-ffc0-4358-a625-1e348a95f14d', 'doctor-uuid-1', '2025-11-26', '12:00:00', '17:00:00', 5, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (78, '5dd5c36b-753c-480f-a20a-4490e135f08f', 'doctor-uuid-1', '2025-11-26', '14:00:00', '09:00:00', 3, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (79, 'd880e1c7-08f4-4aec-86da-8b90a4ad2055', 'doctor-uuid-1', '2025-11-26', '10:00:00', '17:00:00', 5, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (80, 'caf7c0f5-fadb-4c2e-aa2a-4031da3de7a0', 'doctor-uuid-2', '2025-11-26', '08:00:00', '12:00:00', 4, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (81, 'bb9b3c8f-56ee-432b-91a4-15abbdc29e64', 'doctor-uuid-2', '2025-11-26', '12:00:00', '09:00:00', 3, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (82, '26d4f355-be51-4b2f-b9df-94480f0cb72e', 'doctor-uuid-2', '2025-11-26', '16:00:00', '14:00:00', 8, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (83, '9bd34537-26f2-4075-9c49-7e4a6a69a658', 'doctor-uuid-3', '2025-11-26', '11:00:00', '11:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (84, '216cf417-9749-4a54-8b7a-9c5ea544e142', 'doctor-uuid-3', '2025-11-26', '11:00:00', '12:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (85, '6d53e024-5b33-454a-ae5c-90eda1838382', 'doctor-uuid-3', '2025-11-26', '16:00:00', '09:00:00', 7, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (86, '7135d7d3-3bfa-4838-86f3-16a35b1124a1', 'doctor-uuid-4', '2025-11-26', '11:00:00', '11:00:00', 6, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (87, 'e954fee7-d0df-48c2-828a-ebb0309e74b8', 'doctor-uuid-4', '2025-11-26', '13:00:00', '13:00:00', 6, '可预约', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (88, 'ab32b61c-09c9-4051-b0d8-991830b7fd83', 'doctor-uuid-5', '2025-11-26', '14:00:00', '12:00:00', 8, '已满', NOW(), 0, 0);
INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)
  VALUES (89, 'f224a016-4958-43ab-84a2-3113114157f3', 'doctor-uuid-5', '2025-11-26', '10:00:00', '18:00:00', 8, '已满', NOW(), 0, 0);

-- ========== 生物力学检查数据 (8条) ==========
INSERT INTO biomechanics_scan (Scan_ID, Scan_UUID, Patient_UUID, Medical_Record_UUID, Scan_Date, Left_Eye_Data, Right_Eye_Data, Device_Type, Created_At, Version, Deleted)
  VALUES (1, '8786f6dc-fb86-4ceb-bbdd-94dfbf85fce4', '5524343b-1b56-428b-8aa3-2d4e7a734103', NULL, '2025-09-17', '{"curvature": 44.67, "thickness": 504}', '{"curvature": 43.71, "thickness": 498}', 'Corvis ST', NOW(), 0, 0);
INSERT INTO biomechanics_scan (Scan_ID, Scan_UUID, Patient_UUID, Medical_Record_UUID, Scan_Date, Left_Eye_Data, Right_Eye_Data, Device_Type, Created_At, Version, Deleted)
  VALUES (2, '7aa89064-7284-4406-916b-4415256096d1', '062dff06-8af7-4215-9666-d6cf95886aa8', 'a25f2b28-09a6-4d45-a709-bcd2454ea213', '2025-11-18', '{"curvature": 43.41, "thickness": 505}', '{"curvature": 42.70, "thickness": 532}', 'Corvis ST', NOW(), 0, 0);
INSERT INTO biomechanics_scan (Scan_ID, Scan_UUID, Patient_UUID, Medical_Record_UUID, Scan_Date, Left_Eye_Data, Right_Eye_Data, Device_Type, Created_At, Version, Deleted)
  VALUES (3, '1a496ded-b300-47d8-9dad-f5d0eb36b893', '4f677e70-9b28-4fc9-9498-a9651a02c800', 'e79c431d-34da-4dfc-9f9a-c0ed7a42dc46', '2025-10-17', '{"curvature": 44.87, "thickness": 518}', '{"curvature": 42.23, "thickness": 559}', 'Corvis ST', NOW(), 0, 0);
INSERT INTO biomechanics_scan (Scan_ID, Scan_UUID, Patient_UUID, Medical_Record_UUID, Scan_Date, Left_Eye_Data, Right_Eye_Data, Device_Type, Created_At, Version, Deleted)
  VALUES (4, 'd0087f17-7ba7-4077-8c49-22f6a07eefdb', 'a6787d32-77ed-470d-84bf-1b4f6816c5d4', '093581cc-b2a7-464e-a02f-90cf91e7fcdc', '2025-11-14', '{"curvature": 42.73, "thickness": 486}', '{"curvature": 42.57, "thickness": 551}', 'Corvis ST', NOW(), 0, 0);
INSERT INTO biomechanics_scan (Scan_ID, Scan_UUID, Patient_UUID, Medical_Record_UUID, Scan_Date, Left_Eye_Data, Right_Eye_Data, Device_Type, Created_At, Version, Deleted)
  VALUES (5, '0b0bfb98-ecc6-45d5-8b80-1a6f6bd223bf', '062dff06-8af7-4215-9666-d6cf95886aa8', 'a25f2b28-09a6-4d45-a709-bcd2454ea213', '2025-11-02', '{"curvature": 42.62, "thickness": 529}', '{"curvature": 44.20, "thickness": 517}', 'Corvis ST', NOW(), 0, 0);
INSERT INTO biomechanics_scan (Scan_ID, Scan_UUID, Patient_UUID, Medical_Record_UUID, Scan_Date, Left_Eye_Data, Right_Eye_Data, Device_Type, Created_At, Version, Deleted)
  VALUES (6, 'f20c9900-8a4f-4bff-aa98-398fbb4a9d30', '620df5a1-189d-4955-a051-1d9a0010afb8', '2a398014-ac24-4a7f-a91b-23790c373a4c', '2025-09-03', '{"curvature": 42.12, "thickness": 515}', '{"curvature": 42.56, "thickness": 502}', 'Corvis ST', NOW(), 0, 0);
INSERT INTO biomechanics_scan (Scan_ID, Scan_UUID, Patient_UUID, Medical_Record_UUID, Scan_Date, Left_Eye_Data, Right_Eye_Data, Device_Type, Created_At, Version, Deleted)
  VALUES (7, '24c6bd3b-b568-485a-bfb1-de5801b01331', 'd528a20e-dfa5-4768-8c27-fc0bb9046d4e', NULL, '2025-09-07', '{"curvature": 44.72, "thickness": 538}', '{"curvature": 42.12, "thickness": 486}', 'Corvis ST', NOW(), 0, 0);
INSERT INTO biomechanics_scan (Scan_ID, Scan_UUID, Patient_UUID, Medical_Record_UUID, Scan_Date, Left_Eye_Data, Right_Eye_Data, Device_Type, Created_At, Version, Deleted)
  VALUES (8, '932fd5c9-c418-48d9-bb88-bfe000f633e2', 'ca8bddd7-5df6-4b69-9833-7a03059c6ebd', 'd07264e9-b901-454a-bbc1-b4e367bcc226', '2025-11-12', '{"curvature": 43.12, "thickness": 518}', '{"curvature": 43.31, "thickness": 560}', 'Corvis ST', NOW(), 0, 0);

-- ========== 聊天对话数据 (10条) ==========
INSERT INTO chat_conversation (Chat_ID, Chat_UUID, User_Type, Patient_UUID, Title, Conversation_Type, AI_Agent, Total_Messages, Status, Created_At, Version, Deleted)
  VALUES (1, '98a16a7d-04e0-4c41-91dd-5bc413fa53dc', 'patient', '67502405-0c9d-4e94-afc3-28a11e43749e', '咨询预约', 'consultation', 'agent_1', 0, 'active', NOW(), 0, 0);
INSERT INTO chat_conversation (Chat_ID, Chat_UUID, User_Type, Patient_UUID, Title, Conversation_Type, AI_Agent, Total_Messages, Status, Created_At, Version, Deleted)
  VALUES (2, '03afe534-dcb1-40c1-aa23-f3f848290fd4', 'patient', '062dff06-8af7-4215-9666-d6cf95886aa8', '复查提醒', 'consultation', 'agent_2', 0, 'active', NOW(), 0, 0);
INSERT INTO chat_conversation (Chat_ID, Chat_UUID, User_Type, Patient_UUID, Title, Conversation_Type, AI_Agent, Total_Messages, Status, Created_At, Version, Deleted)
  VALUES (3, 'a9452839-1ea5-47ea-ae3c-6265df4fcca5', 'patient', '062dff06-8af7-4215-9666-d6cf95886aa8', '复查提醒', 'consultation', 'agent_1', 0, 'active', NOW(), 0, 0);
INSERT INTO chat_conversation (Chat_ID, Chat_UUID, User_Type, Patient_UUID, Title, Conversation_Type, AI_Agent, Total_Messages, Status, Created_At, Version, Deleted)
  VALUES (4, '83cbcd13-1e72-4111-a700-14d6ceb154a6', 'patient', '4f677e70-9b28-4fc9-9498-a9651a02c800', '复查提醒', 'consultation', 'agent_1', 0, 'active', NOW(), 0, 0);
INSERT INTO chat_conversation (Chat_ID, Chat_UUID, User_Type, Patient_UUID, Title, Conversation_Type, AI_Agent, Total_Messages, Status, Created_At, Version, Deleted)
  VALUES (5, '1ace6584-56a8-4175-a6e1-1140dda11bc3', 'patient', 'ef0fddef-585c-4bc9-95fc-6d1d867eaf25', '症状咨询', 'consultation', 'agent_2', 0, 'active', NOW(), 0, 0);
INSERT INTO chat_conversation (Chat_ID, Chat_UUID, User_Type, Patient_UUID, Title, Conversation_Type, AI_Agent, Total_Messages, Status, Created_At, Version, Deleted)
  VALUES (6, 'a750e444-75ba-493e-b888-d6ffabd4cc27', 'patient', 'ef0fddef-585c-4bc9-95fc-6d1d867eaf25', '用药咨询', 'consultation', 'agent_1', 0, 'active', NOW(), 0, 0);
INSERT INTO chat_conversation (Chat_ID, Chat_UUID, User_Type, Patient_UUID, Title, Conversation_Type, AI_Agent, Total_Messages, Status, Created_At, Version, Deleted)
  VALUES (7, '465fe9f9-fa64-4f50-a1fa-34b17baecdb1', 'patient', 'ca8bddd7-5df6-4b69-9833-7a03059c6ebd', '咨询预约', 'consultation', 'agent_1', 0, 'active', NOW(), 0, 0);
INSERT INTO chat_conversation (Chat_ID, Chat_UUID, User_Type, Patient_UUID, Title, Conversation_Type, AI_Agent, Total_Messages, Status, Created_At, Version, Deleted)
  VALUES (8, 'ebd52057-a36d-4464-b229-5f9de336544d', 'patient', 'ca8bddd7-5df6-4b69-9833-7a03059c6ebd', '用药咨询', 'consultation', 'agent_1', 0, 'active', NOW(), 0, 0);
INSERT INTO chat_conversation (Chat_ID, Chat_UUID, User_Type, Patient_UUID, Title, Conversation_Type, AI_Agent, Total_Messages, Status, Created_At, Version, Deleted)
  VALUES (9, '5b3735d4-d031-4cff-99a2-1a392ab1d8aa', 'patient', 'd528a20e-dfa5-4768-8c27-fc0bb9046d4e', '症状咨询', 'consultation', 'agent_2', 0, 'active', NOW(), 0, 0);
INSERT INTO chat_conversation (Chat_ID, Chat_UUID, User_Type, Patient_UUID, Title, Conversation_Type, AI_Agent, Total_Messages, Status, Created_At, Version, Deleted)
  VALUES (10, '1d90b622-ca3e-4e65-aec3-3197cb355837', 'patient', '062dff06-8af7-4215-9666-d6cf95886aa8', '症状咨询', 'consultation', 'agent_2', 0, 'active', NOW(), 0, 0);

-- ========== 聊天消息数据 (每个对话6条) ==========
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (1, '7ed04a95-873e-408e-8cbe-58c9791df9a2', '98a16a7d-04e0-4c41-91dd-5bc413fa53dc', 1, '你好，我想预约眼科检查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (2, '7d873bff-b6c3-455e-b501-be494f78b152', '98a16a7d-04e0-4c41-91dd-5bc413fa53dc', 2, '根据您的症状，建议使用人工泪液', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (3, 'aff1595d-f0e5-4e9a-a5b6-8f4b4383f7f6', '98a16a7d-04e0-4c41-91dd-5bc413fa53dc', 3, '这个药怎么用', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (4, '69bfa5d4-494d-4f0e-b900-808217d813b1', '98a16a7d-04e0-4c41-91dd-5bc413fa53dc', 4, '建议您两周后复查', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (5, '6e4fb5c1-eb92-49cc-9916-1022ba2411d5', '98a16a7d-04e0-4c41-91dd-5bc413fa53dc', 5, '我的检查报告出来了吗', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (6, 'f70a0cc1-44c8-4982-8e63-3415f09fec4f', '98a16a7d-04e0-4c41-91dd-5bc413fa53dc', 6, '您的报告已经生成，请查收', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (7, 'a6a0a1e4-fa4e-41eb-9233-2e00af718d83', '03afe534-dcb1-40c1-aa23-f3f848290fd4', 1, '这个药怎么用', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (8, '0c5f08a5-b2fe-44c4-95fb-37780d118ea3', '03afe534-dcb1-40c1-aa23-f3f848290fd4', 2, '请按说明书指导使用，每日3次', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (9, '2a0a8a37-ce3c-4afe-8974-85ba13d87eb5', '03afe534-dcb1-40c1-aa23-f3f848290fd4', 3, '最近眼睛有点干涩，该怎么办', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (10, '8c6e428c-2d5c-4b05-aab8-1207f596bb8a', '03afe534-dcb1-40c1-aa23-f3f848290fd4', 4, '您好，我是智能助手，很高兴为您服务', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (11, 'b0605b50-9e53-4315-99be-e89c3237d9ba', '03afe534-dcb1-40c1-aa23-f3f848290fd4', 5, '最近眼睛有点干涩，该怎么办', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (12, '758969d4-f40d-46be-8630-9dee0b42733b', '03afe534-dcb1-40c1-aa23-f3f848290fd4', 6, '您的报告已经生成，请查收', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (13, '8c665dff-a638-4bb5-96df-992ba8e0914a', 'a9452839-1ea5-47ea-ae3c-6265df4fcca5', 1, '这个药怎么用', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (14, '1aed8f3a-4e0d-4511-80c4-351720cf107b', 'a9452839-1ea5-47ea-ae3c-6265df4fcca5', 2, '根据您的症状，建议使用人工泪液', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (15, 'ef816d96-1d23-4994-bff0-ac3f773429fc', 'a9452839-1ea5-47ea-ae3c-6265df4fcca5', 3, '你好，我想预约眼科检查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (16, '3688353e-ba48-4742-8cf0-6742f22568eb', 'a9452839-1ea5-47ea-ae3c-6265df4fcca5', 4, '您的报告已经生成，请查收', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (17, '2f9d0ce5-8130-4fba-ba8c-971e46f44c6f', 'a9452839-1ea5-47ea-ae3c-6265df4fcca5', 5, '你好，我想预约眼科检查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (18, '962439e7-7aad-4781-95c8-9297eb50eac5', 'a9452839-1ea5-47ea-ae3c-6265df4fcca5', 6, '您好，我是智能助手，很高兴为您服务', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (19, '99b5a1ab-956f-4f2a-b7ce-50ac503ed475', '83cbcd13-1e72-4111-a700-14d6ceb154a6', 1, '最近眼睛有点干涩，该怎么办', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (20, '9316b996-1e6a-40d4-a2d1-8c072059da38', '83cbcd13-1e72-4111-a700-14d6ceb154a6', 2, '根据您的症状，建议使用人工泪液', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (21, 'b210e4e0-12ef-4078-9cf4-24e900ceeacb', '83cbcd13-1e72-4111-a700-14d6ceb154a6', 3, '我的检查报告出来了吗', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (22, 'a921bdc2-8b6a-432a-a728-fbf0b7a15413', '83cbcd13-1e72-4111-a700-14d6ceb154a6', 4, '您好，我是智能助手，很高兴为您服务', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (23, 'a00cd475-b872-4d39-b58b-6a0f94af1691', '83cbcd13-1e72-4111-a700-14d6ceb154a6', 5, '下次什么时候复查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (24, '030005b7-1566-4973-899b-caba16e05cde', '83cbcd13-1e72-4111-a700-14d6ceb154a6', 6, '建议您两周后复查', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (25, '15c3d588-f5cd-4be9-9b53-3308abe1328e', '1ace6584-56a8-4175-a6e1-1140dda11bc3', 1, '你好，我想预约眼科检查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (26, 'e2bec276-7592-4c73-a20c-9eb77b6d09a3', '1ace6584-56a8-4175-a6e1-1140dda11bc3', 2, '您好，我是智能助手，很高兴为您服务', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (27, '8a29cbff-acdf-4248-800d-79bb1fa9c700', '1ace6584-56a8-4175-a6e1-1140dda11bc3', 3, '你好，我想预约眼科检查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (28, 'b99db4b7-2a3d-4677-b0f6-8de3b6071716', '1ace6584-56a8-4175-a6e1-1140dda11bc3', 4, '根据您的症状，建议使用人工泪液', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (29, 'da0ce4e2-d26a-4d4c-885c-abfca62ef593', '1ace6584-56a8-4175-a6e1-1140dda11bc3', 5, '下次什么时候复查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (30, 'ab9228e5-ca5f-4dc4-96c6-172f0dd142a9', '1ace6584-56a8-4175-a6e1-1140dda11bc3', 6, '根据您的症状，建议使用人工泪液', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (31, '703699f7-ad7a-4371-89b3-ccd0039b2915', 'a750e444-75ba-493e-b888-d6ffabd4cc27', 1, '你好，我想预约眼科检查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (32, '009a8a9a-2db7-4171-81ea-af1777425b2b', 'a750e444-75ba-493e-b888-d6ffabd4cc27', 2, '根据您的症状，建议使用人工泪液', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (33, '421f4a94-cfde-4f2b-be07-7e7819b09cd4', 'a750e444-75ba-493e-b888-d6ffabd4cc27', 3, '你好，我想预约眼科检查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (34, 'ec609dac-9282-4fb4-a3c6-c3986b853a4b', 'a750e444-75ba-493e-b888-d6ffabd4cc27', 4, '根据您的症状，建议使用人工泪液', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (35, 'a978bd21-daf8-490f-85af-b69d9705da0b', 'a750e444-75ba-493e-b888-d6ffabd4cc27', 5, '这个药怎么用', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (36, '96eba405-af08-4710-bbfa-634c97694c87', 'a750e444-75ba-493e-b888-d6ffabd4cc27', 6, '您的报告已经生成，请查收', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (37, 'd460fcf6-7c30-4dc7-b09a-f01f255325ef', '465fe9f9-fa64-4f50-a1fa-34b17baecdb1', 1, '最近眼睛有点干涩，该怎么办', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (38, '9af2d83f-cd0d-478c-b81d-7a988a1f2e11', '465fe9f9-fa64-4f50-a1fa-34b17baecdb1', 2, '您的报告已经生成，请查收', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (39, '1a5c747a-e545-4661-a640-6f293dcbe86d', '465fe9f9-fa64-4f50-a1fa-34b17baecdb1', 3, '我的检查报告出来了吗', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (40, 'dbd6f009-5f06-48aa-ab8c-e40eb51c8e49', '465fe9f9-fa64-4f50-a1fa-34b17baecdb1', 4, '根据您的症状，建议使用人工泪液', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (41, '3be57d8d-1724-4183-b42e-72ae148ebee4', '465fe9f9-fa64-4f50-a1fa-34b17baecdb1', 5, '下次什么时候复查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (42, '613d43d5-13c6-4049-ae1c-71a321d5f00e', '465fe9f9-fa64-4f50-a1fa-34b17baecdb1', 6, '建议您两周后复查', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (43, 'dffea0c6-3bf7-4865-a8aa-054057a2eb0e', 'ebd52057-a36d-4464-b229-5f9de336544d', 1, '你好，我想预约眼科检查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (44, '096ff304-46ae-426d-928b-bbf9351f846d', 'ebd52057-a36d-4464-b229-5f9de336544d', 2, '根据您的症状，建议使用人工泪液', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (45, 'c06bc7bc-e494-4e66-b5a3-596cfe3c108b', 'ebd52057-a36d-4464-b229-5f9de336544d', 3, '下次什么时候复查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (46, '653f0036-b7ce-495c-9dfc-4fbe59db634f', 'ebd52057-a36d-4464-b229-5f9de336544d', 4, '建议您两周后复查', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (47, 'd0a565f9-b1ba-40ba-9f8b-800c00ab97d0', 'ebd52057-a36d-4464-b229-5f9de336544d', 5, '下次什么时候复查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (48, '76d356e2-dde0-4bba-89c6-d84026061fca', 'ebd52057-a36d-4464-b229-5f9de336544d', 6, '您好，我是智能助手，很高兴为您服务', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (49, '6e1ed30c-7bae-46f6-adb5-690944550a46', '5b3735d4-d031-4cff-99a2-1a392ab1d8aa', 1, '你好，我想预约眼科检查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (50, '00185494-64bc-4e54-8bfd-eae464050168', '5b3735d4-d031-4cff-99a2-1a392ab1d8aa', 2, '根据您的症状，建议使用人工泪液', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (51, '8d826d34-b785-4218-b71e-3e566afe5dec', '5b3735d4-d031-4cff-99a2-1a392ab1d8aa', 3, '下次什么时候复查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (52, 'ea41782d-6401-4adc-969c-797418320bbd', '5b3735d4-d031-4cff-99a2-1a392ab1d8aa', 4, '请按说明书指导使用，每日3次', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (53, '3fb9a7fe-3ddd-45d3-b4f5-db9bbb247647', '5b3735d4-d031-4cff-99a2-1a392ab1d8aa', 5, '这个药怎么用', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (54, 'e9341187-e7c4-46b3-9c25-89d24319f648', '5b3735d4-d031-4cff-99a2-1a392ab1d8aa', 6, '您的报告已经生成，请查收', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (55, '8aefcd1e-5308-4019-954f-26f920449a35', '1d90b622-ca3e-4e65-aec3-3197cb355837', 1, '下次什么时候复查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (56, 'd126e931-10c5-4e4f-a829-57699297f7c4', '1d90b622-ca3e-4e65-aec3-3197cb355837', 2, '根据您的症状，建议使用人工泪液', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (57, 'bc4f0be2-9fcc-4a7b-b917-82ef15e674dd', '1d90b622-ca3e-4e65-aec3-3197cb355837', 3, '我的检查报告出来了吗', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (58, '742c447e-f3a3-40e1-8592-2115163bbbcc', '1d90b622-ca3e-4e65-aec3-3197cb355837', 4, '您好，我是智能助手，很高兴为您服务', 'ai', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (59, 'ae374292-72aa-478c-9322-d0c1bd333a00', '1d90b622-ca3e-4e65-aec3-3197cb355837', 5, '下次什么时候复查', 'user', 'system', NOW(), 0, 0);
INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)
  VALUES (60, '2163fb9e-c550-4840-89a5-26c17563cb2c', '1d90b622-ca3e-4e65-aec3-3197cb355837', 6, '根据您的症状，建议使用人工泪液', 'ai', 'system', NOW(), 0, 0);

-- ========== 提醒数据 (10条) ==========
INSERT INTO reminder (Reminder_ID, Reminder_UUID, Patient_UUID, Appointment_UUID, Reminder_Type, Reminder_Time, Status, Message, Created_At, Version, Deleted)
  VALUES (1, 'd16d889d-5a0e-43f5-a3fc-f87ea073dc76', 'd528a20e-dfa5-4768-8c27-fc0bb9046d4e', 'a1e08568-ba06-4f8f-a57c-a7eb192198a2', 'followup', '2025-11-24 20:15:51', 'completed', '您有一条提醒', NOW(), 0, 0);
INSERT INTO reminder (Reminder_ID, Reminder_UUID, Patient_UUID, Appointment_UUID, Reminder_Type, Reminder_Time, Status, Message, Created_At, Version, Deleted)
  VALUES (2, '47f77e82-e89c-415e-bb5c-4bd9d82b621e', '4f677e70-9b28-4fc9-9498-a9651a02c800', '050d53e6-6e48-47cb-a017-ba4cac22d059', 'followup', '2025-11-30 00:18:59', 'sent', '您有一条提醒', NOW(), 0, 0);
INSERT INTO reminder (Reminder_ID, Reminder_UUID, Patient_UUID, Appointment_UUID, Reminder_Type, Reminder_Time, Status, Message, Created_At, Version, Deleted)
  VALUES (3, 'd5437bb2-0aa7-40a8-b2dd-6808d0f08ca4', '5524343b-1b56-428b-8aa3-2d4e7a734103', '27bc5e87-2270-413f-97df-ec6724857bdb', 'followup', '2025-12-01 02:36:38', 'completed', '您有一条提醒', NOW(), 0, 0);
INSERT INTO reminder (Reminder_ID, Reminder_UUID, Patient_UUID, Appointment_UUID, Reminder_Type, Reminder_Time, Status, Message, Created_At, Version, Deleted)
  VALUES (4, 'bc7864de-52a5-4c83-b748-c69d673ca66e', 'ef0fddef-585c-4bc9-95fc-6d1d867eaf25', '27bc5e87-2270-413f-97df-ec6724857bdb', 'followup', '2025-11-30 09:49:53', 'completed', '您有一条提醒', NOW(), 0, 0);
INSERT INTO reminder (Reminder_ID, Reminder_UUID, Patient_UUID, Appointment_UUID, Reminder_Type, Reminder_Time, Status, Message, Created_At, Version, Deleted)
  VALUES (5, '7c21d7f4-b51a-4157-8f4c-9448148728a2', '4f677e70-9b28-4fc9-9498-a9651a02c800', '27c107df-0295-45b8-a50f-2d343b76520b', 'followup', '2025-12-01 01:00:04', 'completed', '您有一条提醒', NOW(), 0, 0);
INSERT INTO reminder (Reminder_ID, Reminder_UUID, Patient_UUID, Appointment_UUID, Reminder_Type, Reminder_Time, Status, Message, Created_At, Version, Deleted)
  VALUES (6, '8312b0f8-0257-4d92-8751-ba15ab6cf7c2', '67502405-0c9d-4e94-afc3-28a11e43749e', '97e3ef94-efc9-451d-ba15-1528e4f1ec6d', 'appointment', '2025-11-29 02:49:52', 'pending', '您有一条提醒', NOW(), 0, 0);
INSERT INTO reminder (Reminder_ID, Reminder_UUID, Patient_UUID, Appointment_UUID, Reminder_Type, Reminder_Time, Status, Message, Created_At, Version, Deleted)
  VALUES (7, '630c8f66-a485-4efc-a9fd-3b908104c888', '4f677e70-9b28-4fc9-9498-a9651a02c800', '97e3ef94-efc9-451d-ba15-1528e4f1ec6d', 'medication', '2025-12-03 23:52:59', 'sent', '您有一条提醒', NOW(), 0, 0);
INSERT INTO reminder (Reminder_ID, Reminder_UUID, Patient_UUID, Appointment_UUID, Reminder_Type, Reminder_Time, Status, Message, Created_At, Version, Deleted)
  VALUES (8, '24175239-591d-47fc-a249-8a7d84c490e9', '5524343b-1b56-428b-8aa3-2d4e7a734103', '27c107df-0295-45b8-a50f-2d343b76520b', 'followup', '2025-12-01 10:41:25', 'pending', '您有一条提醒', NOW(), 0, 0);
INSERT INTO reminder (Reminder_ID, Reminder_UUID, Patient_UUID, Appointment_UUID, Reminder_Type, Reminder_Time, Status, Message, Created_At, Version, Deleted)
  VALUES (9, '12e9b19a-13b6-4b13-bf80-3a375fc684e2', 'ef0fddef-585c-4bc9-95fc-6d1d867eaf25', '97e3ef94-efc9-451d-ba15-1528e4f1ec6d', 'medication', '2025-11-21 17:33:04', 'completed', '您有一条提醒', NOW(), 0, 0);
INSERT INTO reminder (Reminder_ID, Reminder_UUID, Patient_UUID, Appointment_UUID, Reminder_Type, Reminder_Time, Status, Message, Created_At, Version, Deleted)
  VALUES (10, 'aaa9c8dd-9acb-484b-b116-e19eec44d5ec', '4f677e70-9b28-4fc9-9498-a9651a02c800', '050d53e6-6e48-47cb-a017-ba4cac22d059', 'medication', '2025-11-29 04:39:28', 'pending', '您有一条提醒', NOW(), 0, 0);

SET FOREIGN_KEY_CHECKS = 1;

-- ========== 数据插入完成 ==========
