-- Cleanup script for partial demo data
-- Execute before re-running demo_data_seed.sql

USE medical_db;
SET FOREIGN_KEY_CHECKS = 0;

-- Clean up patients (ID >= 14)
DELETE FROM patient WHERE Patient_ID >= 14;

-- Clean up medical records (ID >= 4)
DELETE FROM medical_record WHERE Medical_Record_ID >= 4;

-- Clean up drugs (ID >= 6)
DELETE FROM drugs WHERE drug_id >= 6;

-- Clean up appointments (ID >= 7)
DELETE FROM appointment WHERE Appointment_ID >= 7;

-- Clean up prescriptions (ID >= 4)
DELETE FROM prescription WHERE prescription_id >= 4;
DELETE FROM prescription_detail WHERE prescription_id >= 4;

-- Clean up doctor schedules (ID >= 1 for demo data)
DELETE FROM doctor_time_slots WHERE Slot_ID >= 1;
DELETE FROM doctor_working_schedule WHERE Schedule_ID >= 1;

-- Clean up biomechanics scans (ID >= 1 for demo data)
DELETE FROM biomechanics_scan WHERE Scan_ID >= 1;

-- Clean up chat data (ID >= 1 for demo data)
DELETE FROM chat_message WHERE Chat_ID >= 1;
DELETE FROM chat_conversation WHERE Chat_ID >= 1;

-- Clean up reminders (ID >= 1 for demo data)
DELETE FROM reminder WHERE reminder_id >= 1;
DELETE FROM reminder_history WHERE history_id >= 1;

-- Clean up reminder_config entries that may have been auto-created
DELETE FROM reminder_config WHERE Patient_ID >= 14;

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'Cleanup completed successfully' AS Status;
