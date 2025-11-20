-- ========================================
-- 对话历史记录表结构 SQL 脚本
-- 创建日期: 2025-11-19
-- 用途: 存储患者和医生的对话历史记录
-- ========================================

-- 1. 聊天对话主表 (chat_conversation)
-- 描述: 存储每个独立的对话会话信息，支持患者和医生两种用户类型
CREATE TABLE IF NOT EXISTS chat_conversation (
    Chat_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '对话ID（唯一标识一个对话会话）',

    -- 用户身份字段(支持患者或医生)
    User_Type ENUM('patient', 'doctor') NOT NULL COMMENT '用户类型（patient=患者，doctor=医生）',
    Patient_ID INT DEFAULT NULL COMMENT '患者ID（当User_Type=patient时必填，外键关联patient表）',
    Doctor_ID INT DEFAULT NULL COMMENT '医生ID（当User_Type=doctor时必填，外键关联doctor表）',

    -- 对话基本信息
    Title VARCHAR(255) DEFAULT NULL COMMENT '对话标题（可选，用户自定义或AI总结）',
    Conversation_Type VARCHAR(50) DEFAULT 'general' COMMENT '对话类型（general/consultation/appointment/report等）',
    AI_Agent VARCHAR(100) DEFAULT NULL COMMENT '处理此对话的AI智能体（agent_1/agent_2/agent_3等）',
    Summary TEXT DEFAULT NULL COMMENT '对话摘要（可选，用于快速查阅）',
    Total_Messages INT DEFAULT 0 COMMENT '消息总数',
    Status ENUM('active', 'archived', 'closed') DEFAULT 'active' COMMENT '对话状态（active=活跃，archived=已归档，closed=已关闭）',

    -- 时间戳
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',

    -- 外键约束
    FOREIGN KEY (Patient_ID) REFERENCES patient(Patient_ID) ON DELETE CASCADE,
    FOREIGN KEY (Doctor_ID) REFERENCES doctor(Doctor_ID) ON DELETE CASCADE,

    -- 索引优化查询性能
    INDEX idx_patient (Patient_ID),
    INDEX idx_doctor (Doctor_ID),
    INDEX idx_user_type (User_Type),
    INDEX idx_created_at (Created_At),
    INDEX idx_status (Status),
    INDEX idx_conversation_type (Conversation_Type),

    -- 约束:确保根据User_Type正确填写对应的ID
    CHECK (
        (User_Type = 'patient' AND Patient_ID IS NOT NULL AND Doctor_ID IS NULL) OR
        (User_Type = 'doctor' AND Doctor_ID IS NOT NULL AND Patient_ID IS NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='聊天对话主表（支持患者和医生用户）';


-- 2. 聊天消息详情表 (chat_message)
-- 描述: 存储对话中的每一条消息（用户消息和AI消息）
CREATE TABLE IF NOT EXISTS chat_message (
    Message_ID INT PRIMARY KEY AUTO_INCREMENT COMMENT '消息ID（唯一标识）',
    Chat_ID INT NOT NULL COMMENT '对话ID（外键，链接到对话会话）',

    -- 消息内容
    Message_Order INT NOT NULL COMMENT '消息序号（会话内的顺序号，从1开始）',
    Message_Content LONGTEXT NOT NULL COMMENT '消息内容',
    Message_Type ENUM('user', 'ai') NOT NULL COMMENT '消息类型（user=用户消息，ai=AI消息）',
    Sender_Info VARCHAR(255) DEFAULT NULL COMMENT '发送者信息（用户名/AI代理名称，如agent_1）',

    -- 上下文和元数据
    Context TEXT DEFAULT NULL COMMENT '消息上下文（用于记录特殊参数、医学信息等，可存储JSON格式）',
    Tokens_Used INT DEFAULT NULL COMMENT '此消息消耗的token数（可选，用于统计API成本）',

    -- 时间戳
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '消息创建时间',
    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '消息修改时间（仅在编辑时更新）',

    -- 外键约束
    FOREIGN KEY (Chat_ID) REFERENCES chat_conversation(Chat_ID) ON DELETE CASCADE,

    -- 索引优化查询性能
    INDEX idx_chat (Chat_ID),
    INDEX idx_message_type (Message_Type),
    INDEX idx_created_at (Created_At),

    -- 唯一约束:确保每个对话中的消息顺序唯一
    UNIQUE KEY unique_chat_order (Chat_ID, Message_Order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='聊天消息详情表（一条记录代表一条消息）';


-- ========================================
-- 常用查询示例
-- ========================================

-- 查询某个患者的所有对话（按时间倒序）
-- SELECT * FROM chat_conversation
-- WHERE User_Type = 'patient' AND Patient_ID = 1
-- ORDER BY Created_At DESC;

-- 查询某个医生的所有对话
-- SELECT * FROM chat_conversation
-- WHERE User_Type = 'doctor' AND Doctor_ID = 5
-- ORDER BY Created_At DESC;

-- 查询某个对话的所有消息（按顺序）
-- SELECT * FROM chat_message
-- WHERE Chat_ID = 10
-- ORDER BY Message_Order ASC;

-- 查询最近7天的活跃对话
-- SELECT * FROM chat_conversation
-- WHERE Patient_ID = 1
-- AND Status = 'active'
-- AND Created_At >= DATE_SUB(NOW(), INTERVAL 7 DAY)
-- ORDER BY Updated_At DESC;

-- 查询某个对话的消息统计
-- SELECT
--     Chat_ID,
--     COUNT(*) as total_messages,
--     SUM(CASE WHEN Message_Type = 'user' THEN 1 ELSE 0 END) as user_messages,
--     SUM(CASE WHEN Message_Type = 'ai' THEN 1 ELSE 0 END) as ai_messages,
--     SUM(Tokens_Used) as total_tokens
-- FROM chat_message
-- WHERE Chat_ID = 10
-- GROUP BY Chat_ID;

-- 通过电话号查询患者的所有对话
-- SELECT cc.* FROM chat_conversation cc
-- INNER JOIN patient p ON cc.Patient_ID = p.Patient_ID
-- WHERE p.Phone_Number = '13900000001' AND cc.User_Type = 'patient'
-- ORDER BY cc.Created_At DESC;

-- 查询所有活跃对话及其最后一条消息
-- SELECT
--     cc.*,
--     cm.Message_Content as Last_Message,
--     cm.Created_At as Last_Message_Time
-- FROM chat_conversation cc
-- LEFT JOIN (
--     SELECT Chat_ID, Message_Content, Created_At
--     FROM chat_message cm1
--     WHERE Message_Order = (
--         SELECT MAX(Message_Order)
--         FROM chat_message cm2
--         WHERE cm2.Chat_ID = cm1.Chat_ID
--     )
-- ) cm ON cc.Chat_ID = cm.Chat_ID
-- WHERE cc.Status = 'active'
-- ORDER BY cc.Updated_At DESC;
