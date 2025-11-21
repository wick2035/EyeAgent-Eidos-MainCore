/*
================================================================================
修复 chat_conversation 和 appointment 表的主键 AUTO_INCREMENT 问题
================================================================================

问题描述:
  - 错误: Field 'Chat_ID' doesn't have a default value
  - 原因: UUID迁移后触发器可能影响了AUTO_INCREMENT

解决方案:
  - 确保INT主键仍然设置为 AUTO_INCREMENT
  - 保留UUID列和触发器用于渐进式迁移

日期: 2025-11-20
================================================================================
*/

USE medical_db;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- 修复 chat_conversation 表
-- ============================================================================

-- 检查当前表结构
SHOW CREATE TABLE chat_conversation;

-- 确保 Chat_ID 有 AUTO_INCREMENT
ALTER TABLE chat_conversation MODIFY COLUMN Chat_ID INT AUTO_INCREMENT COMMENT '对话ID(唯一标识一个对话会话)';

-- 验证修复
SELECT
    'chat_conversation' AS table_name,
    COLUMN_NAME,
    COLUMN_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    EXTRA
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
  AND TABLE_NAME = 'chat_conversation'
  AND COLUMN_NAME IN ('Chat_ID', 'Chat_UUID');

-- ============================================================================
-- 修复 appointment 表
-- ============================================================================

-- 检查当前表结构
SHOW CREATE TABLE appointment;

-- 确保 Appointment_ID 有 AUTO_INCREMENT
ALTER TABLE appointment MODIFY COLUMN Appointment_ID INT AUTO_INCREMENT COMMENT '预约ID';

-- 验证修复
SELECT
    'appointment' AS table_name,
    COLUMN_NAME,
    COLUMN_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    EXTRA
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
  AND TABLE_NAME = 'appointment'
  AND COLUMN_NAME IN ('Appointment_ID', 'Appointment_UUID');

-- ============================================================================
-- 修复 chat_message 表 (如果需要)
-- ============================================================================

ALTER TABLE chat_message MODIFY COLUMN Message_ID INT AUTO_INCREMENT COMMENT '消息ID(唯一标识)';

-- ============================================================================
-- 测试插入 (验证修复成功)
-- ============================================================================

-- 测试患者对话创建 (不指定Chat_ID)
-- INSERT INTO chat_conversation (User_Type, Patient_ID, Patient_UUID, Title, Conversation_Type, Create_By, Version, Deleted)
-- SELECT 'patient', Patient_ID, Patient_UUID, '测试对话', 'test', 'system', 0, 0
-- FROM patient LIMIT 1;

-- SELECT '修复成功！可以不指定Chat_ID进行插入' AS result;

-- 回滚测试数据
-- DELETE FROM chat_conversation WHERE Title = '测试对话' AND Conversation_Type = 'test';

SET FOREIGN_KEY_CHECKS = 1;

SELECT '=== 修复完成 ===' AS message;
SELECT 'Chat_ID 和 Appointment_ID 已确保有 AUTO_INCREMENT' AS status;

/*
================================================================================
注意事项:
================================================================================

1. 这个脚本只是确保INT主键的AUTO_INCREMENT属性正确
2. UUID列和触发器保持不变,用于未来的UUID主键迁移
3. 当前系统同时支持INT ID 和 UUID (双主键过渡期)

4. 如果仍然报错,可能是因为:
   - 触发器逻辑有问题
   - Python代码显式传入了NULL值
   - 表约束冲突

================================================================================
*/
