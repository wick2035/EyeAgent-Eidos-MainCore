-- Agent3 提醒功能数据库扩展
-- 创建日期：2025-11-17
-- 功能：支持复诊提醒、预约提醒、用药提醒等功能

USE medical_db;

-- 1. 提醒记录表 (reminder)
CREATE TABLE IF NOT EXISTS reminder (
    Reminder_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '提醒ID',
    Patient_ID INT NOT NULL COMMENT '患者ID',
    Medical_Record_ID INT DEFAULT NULL COMMENT '关联病例ID（可选）',
    Appointment_ID INT DEFAULT NULL COMMENT '关联预约ID（可选）',
    Prescription_ID INT DEFAULT NULL COMMENT '关联处方ID（可选）',

    Reminder_Type ENUM('follow_up', 'appointment', 'medication', 'checkup', 'custom') NOT NULL COMMENT '提醒类型：复诊/预约/用药/检查/自定义',
    Reminder_Title VARCHAR(200) NOT NULL COMMENT '提醒标题',
    Reminder_Content TEXT NOT NULL COMMENT '提醒内容',

    Scheduled_Time DATETIME NOT NULL COMMENT '计划提醒时间',
    Advance_Days INT DEFAULT 1 COMMENT '提前提醒天数',

    Status ENUM('pending', 'sent', 'completed', 'cancelled', 'expired') DEFAULT 'pending' COMMENT '提醒状态',
    Priority ENUM('low', 'normal', 'high', 'urgent') DEFAULT 'normal' COMMENT '优先级',

    Sent_Time DATETIME DEFAULT NULL COMMENT '实际发送时间',
    Completed_Time DATETIME DEFAULT NULL COMMENT '完成时间（用户确认）',
    Cancelled_Time DATETIME DEFAULT NULL COMMENT '取消时间',

    Repeat_Type ENUM('once', 'daily', 'weekly', 'monthly', 'custom') DEFAULT 'once' COMMENT '重复类型',
    Repeat_Count INT DEFAULT 0 COMMENT '已重复次数',
    Max_Repeat_Count INT DEFAULT 1 COMMENT '最大重复次数',

    Notification_Method VARCHAR(100) DEFAULT 'system' COMMENT '通知方式：system/sms/email/wechat',

    Created_By VARCHAR(50) DEFAULT 'system' COMMENT '创建者（system/doctor/patient）',
    Notes TEXT COMMENT '备注信息',

    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    FOREIGN KEY (Medical_Record_ID) REFERENCES medical_record(Medical_Record_ID) ON DELETE SET NULL,
    FOREIGN KEY (Appointment_ID) REFERENCES appointment(Appointment_ID) ON DELETE SET NULL,
    FOREIGN KEY (Prescription_ID) REFERENCES prescription(Prescription_ID) ON DELETE SET NULL,

    INDEX idx_patient (Patient_ID),
    INDEX idx_scheduled_time (Scheduled_Time),
    INDEX idx_status (Status),
    INDEX idx_type (Reminder_Type),
    INDEX idx_priority (Priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提醒记录表';

-- 2. 提醒历史表 (reminder_history)
CREATE TABLE IF NOT EXISTS reminder_history (
    History_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '历史记录ID',
    Reminder_ID INT NOT NULL COMMENT '提醒ID',
    Action_Type ENUM('created', 'sent', 'read', 'completed', 'cancelled', 'rescheduled') NOT NULL COMMENT '操作类型',
    Action_Time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    Action_By VARCHAR(50) COMMENT '操作人',
    Action_Details TEXT COMMENT '操作详情',

    FOREIGN KEY (Reminder_ID) REFERENCES reminder(Reminder_ID) ON DELETE CASCADE,
    INDEX idx_reminder (Reminder_ID),
    INDEX idx_action_time (Action_Time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提醒历史记录表';

-- 3. 提醒配置表 (reminder_config) - 用户个性化设置
CREATE TABLE IF NOT EXISTS reminder_config (
    Config_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '配置ID',
    Patient_ID INT NOT NULL COMMENT '患者ID',

    Enable_Follow_Up BOOLEAN DEFAULT TRUE COMMENT '启用复诊提醒',
    Enable_Appointment BOOLEAN DEFAULT TRUE COMMENT '启用预约提醒',
    Enable_Medication BOOLEAN DEFAULT TRUE COMMENT '启用用药提醒',

    Default_Advance_Days INT DEFAULT 1 COMMENT '默认提前天数',
    Preferred_Notification_Method VARCHAR(100) DEFAULT 'system' COMMENT '偏好通知方式',
    Quiet_Hours_Start TIME DEFAULT '22:00:00' COMMENT '免打扰开始时间',
    Quiet_Hours_End TIME DEFAULT '08:00:00' COMMENT '免打扰结束时间',

    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    UNIQUE KEY unique_patient (Patient_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提醒配置表';

-- 添加示例数据

-- 示例1：复诊提醒（假设Patient_ID=1存在）
INSERT INTO reminder (
    Patient_ID, Medical_Record_ID, Reminder_Type, Reminder_Title, Reminder_Content,
    Scheduled_Time, Advance_Days, Priority, Created_By
) VALUES (
    1, 1, 'follow_up', '复诊提醒',
    '您的眼科复诊日期即将到来，请准时就诊。医生建议：继续观察眼部症状变化。',
    DATE_ADD(NOW(), INTERVAL 7 DAY), 1, 'high', 'system'
);

-- 示例2：用药提醒
INSERT INTO reminder (
    Patient_ID, Prescription_ID, Reminder_Type, Reminder_Title, Reminder_Content,
    Scheduled_Time, Advance_Days, Repeat_Type, Max_Repeat_Count, Priority, Created_By
) VALUES (
    1, 1, 'medication', '用药提醒',
    '请按时服用玻璃酸钠滴眼液，每日3次，每次1-2滴。',
    DATE_ADD(NOW(), INTERVAL 1 DAY), 0, 'daily', 7, 'normal', 'system'
);

-- 示例3：预约提醒
INSERT INTO reminder (
    Patient_ID, Appointment_ID, Reminder_Type, Reminder_Title, Reminder_Content,
    Scheduled_Time, Advance_Days, Priority, Created_By
) VALUES (
    1, 1, 'appointment', '预约就诊提醒',
    '您预约的眼科门诊时间为明天，请携带医保卡和就诊卡准时就诊。',
    DATE_ADD(NOW(), INTERVAL 1 DAY), 1, 'high', 'doctor'
);

-- 创建默认配置（为所有现有患者）
INSERT INTO reminder_config (Patient_ID)
SELECT Patient_ID FROM patient
ON DUPLICATE KEY UPDATE Updated_At = CURRENT_TIMESTAMP;

-- 添加触发器：新患者自动创建配置
DELIMITER $$

CREATE TRIGGER after_patient_insert
AFTER INSERT ON patient
FOR EACH ROW
BEGIN
    INSERT INTO reminder_config (Patient_ID) VALUES (NEW.Patient_ID);
END$$

DELIMITER ;

-- 查询即将到期的提醒（用于定时任务）
-- SELECT * FROM reminder
-- WHERE Status = 'pending'
-- AND Scheduled_Time <= DATE_ADD(NOW(), INTERVAL Advance_Days DAY)
-- ORDER BY Priority DESC, Scheduled_Time ASC;
