/*
修复剩余的5个INT ID列
解决check约束和唯一键冲突问题
*/

USE medical_db;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- 1. 修复 chat_conversation 表 (删除check约束后再删除列)
-- ============================================================================

SELECT '=== 修复 chat_conversation 表 ===' AS message;

-- 删除check约束
ALTER TABLE chat_conversation DROP CHECK chat_conversation_chk_1;

-- 删除 Patient_ID 列
ALTER TABLE chat_conversation DROP COLUMN IF EXISTS Patient_ID;

-- 删除 Doctor_ID 列
ALTER TABLE chat_conversation DROP COLUMN IF EXISTS Doctor_ID;

SELECT '[OK] chat_conversation 的INT ID列已删除' AS result;

-- ============================================================================
-- 2. 修复 chat_message 表 (删除唯一键后再删除列)
-- ============================================================================

SELECT '=== 修复 chat_message 表 ===' AS message;

-- 删除唯一键约束
ALTER TABLE chat_message DROP INDEX IF EXISTS unique_chat_order;

-- 删除 Chat_ID 列
ALTER TABLE chat_message DROP COLUMN IF EXISTS Chat_ID;

-- 重新创建唯一键(使用UUID)
ALTER TABLE chat_message ADD UNIQUE KEY unique_chat_uuid_order (Chat_UUID, Message_Order);

SELECT '[OK] chat_message 的INT ID列已删除' AS result;

-- ============================================================================
-- 3. 修复 doctor_time_slots 表 (删除唯一键后再删除列)
-- ============================================================================

SELECT '=== 修复 doctor_time_slots 表 ===' AS message;

-- 删除唯一键约束
ALTER TABLE doctor_time_slots DROP INDEX IF EXISTS unique_doctor_slot_time;

-- 删除 Doctor_ID 列
ALTER TABLE doctor_time_slots DROP COLUMN IF EXISTS Doctor_ID;

-- 重新创建唯一键(使用UUID)
ALTER TABLE doctor_time_slots ADD UNIQUE KEY unique_doctor_uuid_slot_time (Doctor_UUID, Slot_Date, Slot_Start_Time);

SELECT '[OK] doctor_time_slots 的INT ID列已删除' AS result;

-- ============================================================================
-- 4. 修复 doctor_working_schedule 表 (删除唯一键后再删除列)
-- ============================================================================

SELECT '=== 修复 doctor_working_schedule 表 ===' AS message;

-- 删除唯一键约束
ALTER TABLE doctor_working_schedule DROP INDEX IF EXISTS unique_doctor_day_shift;

-- 删除 Doctor_ID 列
ALTER TABLE doctor_working_schedule DROP COLUMN IF EXISTS Doctor_ID;

-- 重新创建唯一键(使用UUID)
ALTER TABLE doctor_working_schedule ADD UNIQUE KEY unique_doctor_uuid_day_shift (Doctor_UUID, Day_Of_Week, Shift_Type);

SELECT '[OK] doctor_working_schedule 的INT ID列已删除' AS result;

-- ============================================================================
-- 验证结果
-- ============================================================================

SELECT '=== 验证剩余INT ID列 ===' AS message;

SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'medical_db'
  AND COLUMN_NAME IN ('Patient_ID', 'Doctor_ID', 'Chat_ID')
  AND TABLE_NAME IN ('chat_conversation', 'chat_message', 'doctor_time_slots', 'doctor_working_schedule');

SET FOREIGN_KEY_CHECKS = 1;

SELECT '[SUCCESS] 所有剩余INT ID列修复完成!' AS result;
