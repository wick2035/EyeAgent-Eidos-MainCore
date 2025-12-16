-- ============================================
-- 对话消息表增加状态字段
-- 用于支持两阶段写入（B+ 方案）
-- ============================================
-- 执行时间: 根据数据量可能需要几秒到几分钟
-- 建议: 在低峰期执行，或考虑使用 pt-online-schema-change

-- 1. 添加 status 字段
-- 状态说明:
--   running: AI 正在生成回复（占位）
--   success: 消息保存成功
--   failed: AI 生成失败
--   cancelled: 用户取消或超时
ALTER TABLE chat_message
ADD COLUMN status VARCHAR(20) DEFAULT 'success' COMMENT '消息状态: running/success/failed/cancelled'
AFTER token_used;

-- 2. 添加 error_message 字段
-- 用于记录失败时的错误信息
ALTER TABLE chat_message
ADD COLUMN error_message TEXT NULL COMMENT '错误信息（失败时）'
AFTER status;

-- 3. 为 status 字段添加索引（可选，用于查询失败的消息）
CREATE INDEX idx_chat_message_status ON chat_message(status);

-- 4. 验证字段是否添加成功
-- SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, COLUMN_COMMENT
-- FROM INFORMATION_SCHEMA.COLUMNS
-- WHERE TABLE_NAME = 'chat_message'
-- AND COLUMN_NAME IN ('status', 'error_message');

-- ============================================
-- 回滚脚本（如需回滚）
-- ============================================
-- ALTER TABLE chat_message DROP COLUMN error_message;
-- ALTER TABLE chat_message DROP COLUMN status;
-- DROP INDEX idx_chat_message_status ON chat_message;
