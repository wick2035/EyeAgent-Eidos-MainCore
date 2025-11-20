"""
演示数据生成脚本
创建日期：2025-11-20
功能：生成医疗系统的演示数据SQL脚本，包含患者、医生、病例、预约、处方等完整业务数据
"""

import uuid
from datetime import datetime, timedelta
import random

# 配置
PATIENT_COUNT = 10
MEDICAL_RECORD_COUNT = 20
APPOINTMENT_COUNT = 15
PRESCRIPTION_COUNT = 10
PRESCRIPTION_DETAIL_PER_RX = 3
DRUG_COUNT = 20
TIME_SLOT_COUNT = 80
BIOMECHANICS_SCAN_COUNT = 8
CHAT_CONVERSATION_COUNT = 10
CHAT_MESSAGE_PER_CONV = 6
REMINDER_COUNT = 10

# 基础数据
CHINESE_SURNAMES = ['张', '李', '王', '刘', '陈', '杨', '黄', '赵', '周', '吴', '徐', '孙', '马', '朱', '胡', '郭', '何', '高', '林', '罗']
CHINESE_GIVEN_NAMES = ['伟', '芳', '娜', '敏', '静', '丽', '强', '磊', '军', '洋', '勇', '艳', '杰', '涛', '明', '超', '秀英', '桂英', '建国', '建华']
GENDERS = ['男', '女']
EYE_DISEASES = [
    ('近视', '双眼视力下降', '轻度近视，建议配镜矫正'),
    ('白内障', '视物模糊，眩光', '老年性白内障，建议手术治疗'),
    ('青光眼', '眼压升高，视野缺损', '原发性开角型青光眼，需长期药物治疗'),
    ('干眼症', '眼睛干涩，异物感', '睑板腺功能障碍，建议热敷和人工泪液'),
    ('结膜炎', '眼红、分泌物增多', '细菌性结膜炎，抗生素眼药水治疗'),
    ('角膜炎', '眼痛、畏光、流泪', '单疱病毒性角膜炎，抗病毒治疗'),
    ('视网膜脱离', '视野缺损、飞蚊症', '孔源性视网膜脱离，需紧急手术'),
    ('黄斑变性', '视物变形、中心视力下降', '年龄相关性黄斑变性，玻璃体腔注药')
]

EYE_DRUGS = [
    ('盐酸左氧氟沙星滴眼液', '5ml:15mg', '滴眼液', 12.50, '抗感染'),
    ('玻璃酸钠滴眼液', '5ml:5mg', '滴眼液', 28.00, '缓解干眼'),
    ('妥布霉素滴眼液', '5ml:15mg', '滴眼液', 15.80, '抗感染'),
    ('氯霉素滴眼液', '8ml:20mg', '滴眼液', 8.50, '抗感染'),
    ('红霉素眼膏', '2g:0.5%', '眼膏', 6.00, '抗感染'),
    ('地塞米松滴眼液', '5ml:5mg', '滴眼液', 18.00, '抗炎'),
    ('双氯芬酸钠滴眼液', '5ml:5mg', '滴眼液', 22.00, '抗炎'),
    ('噻吗洛尔滴眼液', '5ml:25mg', '滴眼液', 35.00, '降眼压'),
    ('拉坦前列素滴眼液', '2.5ml', '滴眼液', 185.00, '降眼压'),
    ('布林佐胺滴眼液', '5ml:10mg', '滴眼液', 158.00, '降眼压'),
    ('七叶洋地黄双苷滴眼液', '5ml', '滴眼液', 42.00, '改善循环'),
    ('维生素A棕榈酸酯眼用凝胶', '5g', '眼用凝胶', 38.00, '角膜营养'),
    ('小牛血去蛋白提取物眼用凝胶', '5g', '眼用凝胶', 68.00, '角膜修复'),
    ('阿昔洛韦滴眼液', '8ml:40mg', '滴眼液', 18.50, '抗病毒'),
    ('更昔洛韦眼用凝胶', '5g:0.15g', '眼用凝胶', 78.00, '抗病毒'),
    ('托吡卡胺滴眼液', '5ml', '滴眼液', 25.00, '散瞳'),
    ('复方托吡卡胺滴眼液', '5ml', '滴眼液', 32.00, '散瞳'),
    ('盐酸卡替洛尔滴眼液', '5ml:10mg', '滴眼液', 45.00, '降眼压'),
    ('贝美前列素滴眼液', '3ml', '滴眼液', 168.00, '降眼压'),
    ('羟丙甲纤维素滴眼液', '10ml', '滴眼液', 16.00, '人工泪液')
]

APPOINTMENT_STATUS = ['已完成', '已预约', '已取消']

def generate_uuid():
    """生成UUID字符串"""
    return str(uuid.uuid4())

def generate_phone():
    """生成手机号"""
    return f"1{random.choice([3, 5, 7, 8, 9])}{random.randint(100000000, 999999999)}"

def generate_chinese_name():
    """生成中文姓名"""
    return random.choice(CHINESE_SURNAMES) + random.choice(CHINESE_GIVEN_NAMES)

def generate_date(days_ago=365, days_ahead=7):
    """生成日期（days_ago天前到days_ahead天后）"""
    today = datetime.now()
    start = today - timedelta(days=days_ago)
    end = today + timedelta(days=days_ahead)
    random_date = start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))
    return random_date.strftime('%Y-%m-%d')

def generate_datetime(days_ago=30, days_ahead=7):
    """生成日期时间"""
    today = datetime.now()
    start = today - timedelta(days=days_ago)
    end = today + timedelta(days=days_ahead)
    random_datetime = start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))
    return random_datetime.strftime('%Y-%m-%d %H:%M:%S')

def generate_time():
    """生成时间（工作时间8:00-18:00）"""
    hour = random.randint(8, 17)
    minute = random.choice([0, 30])
    return f"{hour:02d}:{minute:02d}:00"

def escape_sql_string(s):
    """转义SQL字符串"""
    return s.replace("'", "''")

def generate_demo_data_sql():
    """生成演示数据SQL脚本"""

    sql_lines = []
    sql_lines.append("-- ============================================================")
    sql_lines.append("-- 医疗系统演示数据")
    sql_lines.append(f"-- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sql_lines.append("-- ============================================================\n")

    sql_lines.append("USE medical_db;\n")
    sql_lines.append("SET FOREIGN_KEY_CHECKS = 0;\n")
    sql_lines.append("\n-- 清理触发器生成的空UUID记录")
    sql_lines.append("DELETE FROM reminder_config WHERE Config_UUID IS NULL OR Config_UUID = '';\n")

    # ========== 1. 患者数据 ==========
    sql_lines.append("\n-- ========== 患者数据 (补充10条) ==========")
    patients = []
    for i in range(PATIENT_COUNT):
        patient_id = 14 + i  # 从14开始（避开触发器自动生成的配置）
        patient_uuid = generate_uuid()
        name = generate_chinese_name()
        gender = random.choice(GENDERS)
        age = random.randint(18, 80)
        phone = generate_phone()
        address = f"{random.choice(['北京', '上海', '广州', '深圳', '杭州'])}市{random.choice(['朝阳', '海淀', '浦东', '天河', '南山'])}区{random.choice(['中山', '建设', '解放', '人民', '和平'])}路{random.randint(1, 200)}号"

        patients.append({
            'id': patient_id,
            'uuid': patient_uuid,
            'name': name,
            'gender': gender,
            'age': age,
            'phone': phone,
            'address': address
        })

        sql_lines.append(f"INSERT INTO patient (Patient_ID, Patient_UUID, Name, Gender, Age, Phone_Number, Address, Created_At, Version, Deleted)")
        sql_lines.append(f"  VALUES ({patient_id}, '{patient_uuid}', '{name}', '{gender}', {age}, '{phone}', '{address}', NOW(), 0, 0);")

    # ========== 2. 药品数据 ==========
    sql_lines.append("\n-- ========== 药品数据 (补充15条) ==========")
    drugs = []
    for i in range(DRUG_COUNT):
        drug_id = 6 + i  # 从6开始（已有5条）
        drug_name, spec, form, price, category = EYE_DRUGS[i % len(EYE_DRUGS)]

        drugs.append({
            'id': drug_id,
            'name': drug_name,
            'spec': spec,
            'form': form,
            'price': price,
            'category': category
        })

        sql_lines.append(f"INSERT INTO drugs (drug_id, drug_name, drug_specification, drug_dosage_form, price, manufacturer, drug_category, created_at, Version, Deleted)")
        sql_lines.append(f"  VALUES ('{drug_id}', '{drug_name}', '{spec}', '{form}', {price}, '某某制药', '{category}', NOW(), 0, 0);")

    # ========== 3. 病例记录 ==========
    sql_lines.append("\n-- ========== 病例记录 (补充17条) ==========")
    medical_records = []
    for i in range(MEDICAL_RECORD_COUNT):
        record_id = 4 + i  # 从4开始（已有3条）
        record_uuid = generate_uuid()
        # 随机分配给患者（前10个患者）
        patient = random.choice(patients[:min(10, len(patients))])
        patient_uuid = patient['uuid']

        visit_card_number = f"2025-{1001 + i:06d}"
        visit_date = generate_date(days_ago=180, days_ahead=0)
        visit_time = generate_time()

        disease, chief_complaint, diagnosis = random.choice(EYE_DISEASES)

        medical_records.append({
            'id': record_id,
            'uuid': record_uuid,
            'patient_uuid': patient_uuid,
            'visit_date': visit_date,
            'diagnosis': diagnosis
        })

        sql_lines.append(f"INSERT INTO medical_record (Medical_Record_ID, Medical_Record_UUID, Patient_UUID, Visit_Card_Number, Visit_Date, Visit_Time, Department, Chief_Complaint, Present_Illness, Diagnosis, Treatment_Plan, Created_At, Version, Deleted)")
        sql_lines.append(f"  VALUES ({record_id}, '{record_uuid}', '{patient_uuid}', '{visit_card_number}', '{visit_date}', '{visit_time}', '眼科', '{chief_complaint}', '{chief_complaint}', '{diagnosis}', '观察治疗，定期复查', NOW(), 0, 0);")

    # ========== 4. 预约数据 ==========
    sql_lines.append("\n-- ========== 预约数据 (新增15条) ==========")
    # 假设医生ID 1-5已存在，时间段先用NULL
    appointments = []
    for i in range(APPOINTMENT_COUNT):
        appt_id = 1 + i
        appt_uuid = generate_uuid()

        # 随机选择患者和医生
        patient = random.choice(patients[:min(10, len(patients))])
        patient_uuid = patient['uuid']
        doctor_id = random.randint(1, 5)
        doctor_uuid = f"doctor-uuid-{doctor_id}"  # 假设已有doctor UUID

        # 随机选择病例记录
        if medical_records:
            record = random.choice([r for r in medical_records if r['patient_uuid'] == patient_uuid] or medical_records)
            record_uuid = record['uuid']
        else:
            record_uuid = None

        # 预约时间（过去30天到未来7天）
        appt_time = generate_datetime(days_ago=30, days_ahead=7)
        status = random.choice(APPOINTMENT_STATUS)
        category = random.choice(['普通门诊', '专家门诊', '急诊'])
        severity = random.choice(['普通', '紧急', '非常紧急'])

        appointments.append({
            'id': appt_id,
            'uuid': appt_uuid,
            'patient_uuid': patient_uuid,
            'doctor_uuid': doctor_uuid,
            'appt_time': appt_time,
            'status': status
        })

        record_uuid_str = f"'{record_uuid}'" if record_uuid else "NULL"
        sql_lines.append(f"INSERT INTO appointment (Appointment_ID, Appointment_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Appointment_Time, Appointment_Category, Severity_Level, Appointment_Status, Description, Created_At, Version, Deleted)")
        sql_lines.append(f"  VALUES ({appt_id}, '{appt_uuid}', '{patient_uuid}', '{doctor_uuid}', {record_uuid_str}, '{appt_time}', '{category}', '{severity}', '{status}', '预约就诊', NOW(), 0, 0);")

    # ========== 5. 处方数据 ==========
    sql_lines.append("\n-- ========== 处方主表 (补充8条) ==========")
    prescriptions = []
    for i in range(PRESCRIPTION_COUNT):
        rx_id = 3 + i  # 从3开始（已有2条）
        rx_uuid = generate_uuid()
        rx_number = f"RX-2025-{10001 + i}"

        # 随机选择患者和医生
        patient = random.choice(patients[:min(10, len(patients))])
        patient_uuid = patient['uuid']
        doctor_id = random.randint(1, 5)
        doctor_uuid = f"doctor-uuid-{doctor_id}"

        # 关联病例
        related_records = [r for r in medical_records if r['patient_uuid'] == patient_uuid]
        if related_records:
            record = random.choice(related_records)
            record_uuid = record['uuid']
            diagnosis = record['diagnosis']
        else:
            record_uuid = None
            diagnosis = '常规用药'

        rx_date = generate_date(days_ago=60, days_ahead=0)
        rx_type = random.choice(['普通', '急诊', '慢性病'])
        total_amount = round(random.uniform(50, 300), 2)

        prescriptions.append({
            'id': rx_id,
            'uuid': rx_uuid,
            'number': rx_number,
            'patient_uuid': patient_uuid,
            'doctor_uuid': doctor_uuid,
            'record_uuid': record_uuid,
            'total_amount': total_amount
        })

        record_uuid_str = f"'{record_uuid}'" if record_uuid else "NULL"
        sql_lines.append(f"INSERT INTO prescription (Prescription_ID, Prescription_UUID, Patient_UUID, Doctor_UUID, Medical_Record_UUID, Prescription_Number, Prescription_Date, Prescription_Type, Diagnosis_Description, Total_Amount, Prescription_Status, Prescriber_Name, Created_At, Version, Deleted)")
        sql_lines.append(f"  VALUES ({rx_id}, '{rx_uuid}', '{patient_uuid}', '{doctor_uuid}', {record_uuid_str}, '{rx_number}', '{rx_date}', '{rx_type}', '{escape_sql_string(diagnosis)}', {total_amount}, '已开立', '医生{doctor_id}', NOW(), 0, 0);")

    # ========== 6. 处方详情 ==========
    sql_lines.append("\n-- ========== 处方详情 (每个处方3种药品) ==========")
    detail_id = 5  # 从5开始（已有4条）
    for rx in prescriptions:
        rx_uuid = rx['uuid']
        # 每个处方随机选择3种药品
        selected_drugs = random.sample(drugs, min(PRESCRIPTION_DETAIL_PER_RX, len(drugs)))

        for drug in selected_drugs:
            detail_uuid = generate_uuid()
            quantity = random.randint(1, 3)
            unit = '盒'
            dosage = '1滴/次' if '滴眼液' in drug['form'] else '适量'
            frequency = random.choice(['每日3次', '每日2次', '每日1次', '每日4次'])
            duration = random.choice(['7天', '10天', '14天', '21天'])
            route = '滴眼' if '滴眼液' in drug['form'] or '眼膏' in drug['form'] else '口服'
            subtotal = round(drug['price'] * quantity, 2)

            sql_lines.append(f"INSERT INTO prescription_detail (Detail_ID, Detail_UUID, Prescription_UUID, Drug_ID, Drug_Name, Drug_Specification, Quantity, Unit, Dosage, Frequency, Duration, Administration_Route, Unit_Price, Subtotal, Created_At, Version, Deleted)")
            sql_lines.append(f"  VALUES ({detail_id}, '{detail_uuid}', '{rx_uuid}', {drug['id']}, '{drug['name']}', '{drug['spec']}', {quantity}, '{unit}', '{dosage}', '{frequency}', '{duration}', '{route}', {drug['price']}, {subtotal}, NOW(), 0, 0);")
            detail_id += 1

    # ========== 7. 时间段数据 ==========
    sql_lines.append("\n-- ========== 医生时间段 (未来7天) ==========")
    slot_id = 1
    for day_offset in range(7):
        target_date = (datetime.now() + timedelta(days=day_offset)).strftime('%Y-%m-%d')

        for doctor_id in range(1, 6):  # 医生1-5
            doctor_uuid = f"doctor-uuid-{doctor_id}"
            # 每个医生每天2-3个时间段
            time_slots_count = random.randint(2, 3)

            for _ in range(time_slots_count):
                slot_uuid = generate_uuid()
                start_time = f"{random.randint(8, 16):02d}:00:00"
                end_time = f"{random.randint(9, 18):02d}:00:00"
                max_appts = random.randint(3, 8)
                status = random.choice(['可预约', '可预约', '可预约', '已满'])

                sql_lines.append(f"INSERT INTO doctor_time_slots (Slot_ID, Slot_UUID, Doctor_UUID, Slot_Date, Start_Time, End_Time, Max_Appointments, Status, Created_At, Version, Deleted)")
                sql_lines.append(f"  VALUES ({slot_id}, '{slot_uuid}', '{doctor_uuid}', '{target_date}', '{start_time}', '{end_time}', {max_appts}, '{status}', NOW(), 0, 0);")
                slot_id += 1

    # ========== 8. 生物力学检查 ==========
    sql_lines.append("\n-- ========== 生物力学检查数据 (8条) ==========")
    for i in range(BIOMECHANICS_SCAN_COUNT):
        scan_id = 1 + i
        scan_uuid = generate_uuid()

        patient = random.choice(patients[:min(10, len(patients))])
        patient_uuid = patient['uuid']

        related_records = [r for r in medical_records if r['patient_uuid'] == patient_uuid]
        if related_records:
            record = random.choice(related_records)
            record_uuid = record['uuid']
        else:
            record_uuid = None

        scan_date = generate_date(days_ago=90, days_ahead=0)
        left_data = f'{{"curvature": {random.uniform(42, 45):.2f}, "thickness": {random.randint(480, 560)}}}'
        right_data = f'{{"curvature": {random.uniform(42, 45):.2f}, "thickness": {random.randint(480, 560)}}}'

        record_uuid_str = f"'{record_uuid}'" if record_uuid else "NULL"
        sql_lines.append(f"INSERT INTO biomechanics_scan (Scan_ID, Scan_UUID, Patient_UUID, Medical_Record_UUID, Scan_Date, Left_Eye_Data, Right_Eye_Data, Device_Type, Created_At, Version, Deleted)")
        sql_lines.append(f"  VALUES ({scan_id}, '{scan_uuid}', '{patient_uuid}', {record_uuid_str}, '{scan_date}', '{left_data}', '{right_data}', 'Corvis ST', NOW(), 0, 0);")

    # ========== 9. 聊天对话 ==========
    sql_lines.append("\n-- ========== 聊天对话数据 (10条) ==========")
    conversations = []
    for i in range(CHAT_CONVERSATION_COUNT):
        chat_id = 1 + i
        chat_uuid = generate_uuid()

        patient = random.choice(patients[:min(10, len(patients))])
        patient_uuid = patient['uuid']

        title = random.choice(['咨询预约', '症状咨询', '报告查询', '用药咨询', '复查提醒'])
        conv_type = 'consultation'
        ai_agent = random.choice(['agent_1', 'agent_2'])

        conversations.append({
            'id': chat_id,
            'uuid': chat_uuid,
            'patient_uuid': patient_uuid
        })

        sql_lines.append(f"INSERT INTO chat_conversation (Chat_ID, Chat_UUID, User_Type, Patient_UUID, Title, Conversation_Type, AI_Agent, Total_Messages, Status, Created_At, Version, Deleted)")
        sql_lines.append(f"  VALUES ({chat_id}, '{chat_uuid}', 'patient', '{patient_uuid}', '{title}', '{conv_type}', '{ai_agent}', 0, 'active', NOW(), 0, 0);")

    # ========== 10. 聊天消息 ==========
    sql_lines.append("\n-- ========== 聊天消息数据 (每个对话6条) ==========")
    message_id = 1
    for conv in conversations:
        chat_uuid = conv['uuid']

        for msg_order in range(1, CHAT_MESSAGE_PER_CONV + 1):
            message_uuid = generate_uuid()
            message_type = 'user' if msg_order % 2 == 1 else 'ai'

            if message_type == 'user':
                content = random.choice([
                    '你好，我想预约眼科检查',
                    '最近眼睛有点干涩，该怎么办',
                    '我的检查报告出来了吗',
                    '这个药怎么用',
                    '下次什么时候复查'
                ])
            else:
                content = random.choice([
                    '您好，我是智能助手，很高兴为您服务',
                    '根据您的症状，建议使用人工泪液',
                    '您的报告已经生成，请查收',
                    '请按说明书指导使用，每日3次',
                    '建议您两周后复查'
                ])

            sql_lines.append(f"INSERT INTO chat_message (Message_ID, Message_UUID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Created_At, Version, Deleted)")
            sql_lines.append(f"  VALUES ({message_id}, '{message_uuid}', '{chat_uuid}', {msg_order}, '{content}', '{message_type}', 'system', NOW(), 0, 0);")
            message_id += 1

    # ========== 11. 提醒数据 ==========
    sql_lines.append("\n-- ========== 提醒数据 (10条) ==========")
    for i in range(REMINDER_COUNT):
        reminder_id = 1 + i
        reminder_uuid = generate_uuid()

        patient = random.choice(patients[:min(10, len(patients))])
        patient_uuid = patient['uuid']

        reminder_type = random.choice(['appointment', 'medication', 'followup'])
        reminder_time = generate_datetime(days_ago=0, days_ahead=14)
        status = random.choice(['pending', 'sent', 'completed'])

        if appointments:
            appt = random.choice(appointments)
            appt_uuid = appt['uuid']
        else:
            appt_uuid = None

        appt_uuid_str = f"'{appt_uuid}'" if appt_uuid else "NULL"
        sql_lines.append(f"INSERT INTO reminder (Reminder_ID, Reminder_UUID, Patient_UUID, Appointment_UUID, Reminder_Type, Reminder_Time, Status, Message, Created_At, Version, Deleted)")
        sql_lines.append(f"  VALUES ({reminder_id}, '{reminder_uuid}', '{patient_uuid}', {appt_uuid_str}, '{reminder_type}', '{reminder_time}', '{status}', '您有一条提醒', NOW(), 0, 0);")

    sql_lines.append("\nSET FOREIGN_KEY_CHECKS = 1;")
    sql_lines.append("\n-- ========== 数据插入完成 ==========\n")

    return '\n'.join(sql_lines)

if __name__ == '__main__':
    print("Generating demo data SQL script...")
    sql_content = generate_demo_data_sql()

    output_file = 'd:/Agent/pythonProject1/database/demo_data_seed.sql'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(sql_content)

    print(f"[OK] Demo data SQL script generated: {output_file}")
    print(f"\nStatistics:")
    print(f"  - Patients: {PATIENT_COUNT} records")
    print(f"  - Drugs: {DRUG_COUNT} records")
    print(f"  - Medical Records: {MEDICAL_RECORD_COUNT} records")
    print(f"  - Appointments: {APPOINTMENT_COUNT} records")
    print(f"  - Prescriptions: {PRESCRIPTION_COUNT} records")
    print(f"  - Prescription Details: {PRESCRIPTION_COUNT * PRESCRIPTION_DETAIL_PER_RX} records")
    print(f"  - Time Slots: ~{TIME_SLOT_COUNT} records")
    print(f"  - Biomechanics Scans: {BIOMECHANICS_SCAN_COUNT} records")
    print(f"  - Chat Conversations: {CHAT_CONVERSATION_COUNT} records")
    print(f"  - Chat Messages: {CHAT_CONVERSATION_COUNT * CHAT_MESSAGE_PER_CONV} records")
    print(f"  - Reminders: {REMINDER_COUNT} records")
