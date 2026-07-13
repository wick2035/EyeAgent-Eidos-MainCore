-- =====================================================
-- LangGraph Checkpoint MySQL 表结构
-- 用于持久化 LangGraph 图状态
--
-- 创建日期: 2025-12-16
-- 数据库: eye_agent_db
-- =====================================================

-- -----------------------------------------------------
-- 表: langgraph_checkpoint
-- 说明: 检查点主表，存储图的状态快照
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS langgraph_checkpoint (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    thread_id VARCHAR(128) NOT NULL COMMENT '线程ID（会话标识）',
    checkpoint_id VARCHAR(128) NOT NULL COMMENT '检查点ID',
    parent_checkpoint_id VARCHAR(128) DEFAULT NULL COMMENT '父检查点ID',
    checkpoint_data LONGBLOB NOT NULL COMMENT '序列化的状态数据（pickle）',
    is_compressed TINYINT(1) DEFAULT 0 COMMENT '数据是否压缩: 0-否, 1-是',
    checkpoint_metadata JSON DEFAULT NULL COMMENT '检查点元数据',
    channel_versions JSON DEFAULT NULL COMMENT '通道版本信息',

    -- 通用字段
    version INT DEFAULT 1 COMMENT '乐观锁版本号',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '软删除标记: 0-正常, 1-已删除',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at TIMESTAMP NULL DEFAULT NULL COMMENT '删除时间',

    -- 索引
    UNIQUE KEY uk_thread_checkpoint (thread_id, checkpoint_id),
    INDEX idx_thread_id (thread_id),
    INDEX idx_created_at (created_at),
    INDEX idx_is_deleted (is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='LangGraph 检查点主表';


-- -----------------------------------------------------
-- 表: langgraph_checkpoint_writes
-- 说明: 检查点写入缓存，存储待处理的写操作
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS langgraph_checkpoint_writes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    thread_id VARCHAR(128) NOT NULL COMMENT '线程ID',
    checkpoint_id VARCHAR(128) NOT NULL COMMENT '检查点ID',
    task_id VARCHAR(128) NOT NULL COMMENT '任务ID',
    channel VARCHAR(255) NOT NULL COMMENT '通道名称',
    value LONGBLOB NOT NULL COMMENT '序列化的值',

    -- 通用字段
    version INT DEFAULT 1 COMMENT '乐观锁版本号',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '软删除标记: 0-正常, 1-已删除',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at TIMESTAMP NULL DEFAULT NULL COMMENT '删除时间',

    -- 索引
    UNIQUE KEY uk_write (thread_id, checkpoint_id, task_id, channel),
    INDEX idx_thread_checkpoint (thread_id, checkpoint_id),
    INDEX idx_is_deleted (is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='LangGraph 检查点写入缓存';


-- -----------------------------------------------------
-- 表: langgraph_thread_mapping
-- 说明: ID映射表，关联 thread_id 与业务ID
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS langgraph_thread_mapping (
    thread_id VARCHAR(128) PRIMARY KEY COMMENT 'LangGraph线程ID',
    conversation_id VARCHAR(64) DEFAULT NULL COMMENT '关联 chat_conversation.id',
    session_id VARCHAR(64) DEFAULT NULL COMMENT '会话ID',
    patient_id VARCHAR(64) DEFAULT NULL COMMENT '患者UUID；科研模式为空',
    doctor_id VARCHAR(64) DEFAULT NULL COMMENT '医生UUID',
    agent_type VARCHAR(32) DEFAULT 'health' COMMENT 'Agent类型',
    status VARCHAR(16) DEFAULT 'active' COMMENT '状态: active/archived/deleted',

    -- 通用字段
    version INT DEFAULT 1 COMMENT '乐观锁版本号',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '软删除标记: 0-正常, 1-已删除',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at TIMESTAMP NULL DEFAULT NULL COMMENT '删除时间',

    -- 索引
    INDEX idx_conversation (conversation_id),
    INDEX idx_patient (patient_id),
    INDEX idx_session (session_id),
    INDEX idx_status (status),
    INDEX idx_is_deleted (is_deleted)

    -- 外键（可选，根据实际需求启用）
    -- FOREIGN KEY (conversation_id) REFERENCES chat_conversation(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='LangGraph 线程ID映射表';


-- -----------------------------------------------------
-- 表: langgraph_thread_agent_history
-- 说明: Agent 切换历史记录，追踪对话中使用的所有 Agent
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS langgraph_thread_agent_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    thread_id VARCHAR(128) NOT NULL COMMENT '线程ID',
    agent_type VARCHAR(32) NOT NULL COMMENT 'Agent类型',
    checkpoint_id VARCHAR(128) DEFAULT NULL COMMENT '切换时的检查点ID',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Agent 开始使用时间',
    ended_at TIMESTAMP NULL DEFAULT NULL COMMENT 'Agent 结束使用时间',

    -- 通用字段
    version INT DEFAULT 1 COMMENT '乐观锁版本号',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '软删除标记: 0-正常, 1-已删除',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at TIMESTAMP NULL DEFAULT NULL COMMENT '删除时间',

    -- 索引
    INDEX idx_thread_id (thread_id),
    INDEX idx_agent_type (agent_type),
    INDEX idx_started_at (started_at),
    INDEX idx_is_deleted (is_deleted),
    INDEX idx_thread_agent (thread_id, agent_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='LangGraph Agent 切换历史记录';


-- -----------------------------------------------------
-- 清理过期数据的存储过程（软删除版本）
-- 说明: 软删除指定天数之前的检查点数据
-- -----------------------------------------------------
DELIMITER //

CREATE PROCEDURE IF NOT EXISTS cleanup_old_checkpoints(IN days_to_keep INT)
BEGIN
    DECLARE cutoff_date TIMESTAMP;
    DECLARE affected_writes INT DEFAULT 0;
    DECLARE affected_checkpoints INT DEFAULT 0;
    DECLARE affected_agent_history INT DEFAULT 0;

    SET cutoff_date = DATE_SUB(NOW(), INTERVAL days_to_keep DAY);

    -- 软删除旧的检查点写入
    UPDATE langgraph_checkpoint_writes
    SET is_deleted = 1,
        deleted_at = NOW(),
        version = version + 1
    WHERE created_at < cutoff_date
      AND is_deleted = 0;

    SET affected_writes = ROW_COUNT();

    -- 软删除旧的检查点（保留每个线程最新的一条）
    UPDATE langgraph_checkpoint cp
    SET cp.is_deleted = 1,
        cp.deleted_at = NOW(),
        cp.version = cp.version + 1
    WHERE cp.created_at < cutoff_date
      AND cp.is_deleted = 0
      AND cp.checkpoint_id NOT IN (
          SELECT checkpoint_id FROM (
              SELECT checkpoint_id
              FROM langgraph_checkpoint
              WHERE thread_id = cp.thread_id
                AND is_deleted = 0
              ORDER BY created_at DESC
              LIMIT 1
          ) AS latest
      );

    SET affected_checkpoints = ROW_COUNT();

    -- 软删除旧的 Agent 切换历史（保留每个线程最新的一条）
    UPDATE langgraph_thread_agent_history ah
    SET ah.is_deleted = 1,
        ah.deleted_at = NOW(),
        ah.version = ah.version + 1
    WHERE ah.created_at < cutoff_date
      AND ah.is_deleted = 0
      AND ah.id NOT IN (
          SELECT id FROM (
              SELECT id
              FROM langgraph_thread_agent_history
              WHERE thread_id = ah.thread_id
                AND is_deleted = 0
              ORDER BY started_at DESC
              LIMIT 1
          ) AS latest
      );

    SET affected_agent_history = ROW_COUNT();

    -- 返回软删除的记录数
    SELECT affected_writes AS deleted_writes,
           affected_checkpoints AS deleted_checkpoints,
           affected_agent_history AS deleted_agent_history,
           (affected_writes + affected_checkpoints + affected_agent_history) AS total_deleted;
END //

DELIMITER ;


-- -----------------------------------------------------
-- 物理删除已软删除数据的存储过程（可选，定期执行）
-- 说明: 永久删除已软删除超过指定天数的数据
-- -----------------------------------------------------
DELIMITER //

CREATE PROCEDURE IF NOT EXISTS purge_deleted_checkpoints(IN days_after_deletion INT)
BEGIN
    DECLARE cutoff_date TIMESTAMP;
    DECLARE purged_writes INT DEFAULT 0;
    DECLARE purged_checkpoints INT DEFAULT 0;
    DECLARE purged_mappings INT DEFAULT 0;
    DECLARE purged_agent_history INT DEFAULT 0;

    SET cutoff_date = DATE_SUB(NOW(), INTERVAL days_after_deletion DAY);

    -- 物理删除写入记录
    DELETE FROM langgraph_checkpoint_writes
    WHERE is_deleted = 1
      AND deleted_at < cutoff_date;

    SET purged_writes = ROW_COUNT();

    -- 物理删除检查点记录
    DELETE FROM langgraph_checkpoint
    WHERE is_deleted = 1
      AND deleted_at < cutoff_date;

    SET purged_checkpoints = ROW_COUNT();

    -- 物理删除映射记录
    DELETE FROM langgraph_thread_mapping
    WHERE is_deleted = 1
      AND deleted_at < cutoff_date;

    SET purged_mappings = ROW_COUNT();

    -- 物理删除 Agent 切换历史记录
    DELETE FROM langgraph_thread_agent_history
    WHERE is_deleted = 1
      AND deleted_at < cutoff_date;

    SET purged_agent_history = ROW_COUNT();

    -- 返回物理删除的记录数
    SELECT purged_writes AS purged_writes,
           purged_checkpoints AS purged_checkpoints,
           purged_mappings AS purged_mappings,
           purged_agent_history AS purged_agent_history,
           (purged_writes + purged_checkpoints + purged_mappings + purged_agent_history) AS total_purged;
END //

DELIMITER ;


-- -----------------------------------------------------
-- 示例调用
-- -----------------------------------------------------
-- 软删除30天前的数据（保留每个线程最新记录）
-- CALL cleanup_old_checkpoints(30);

-- 物理删除已软删除超过90天的数据
-- CALL purge_deleted_checkpoints(90);
