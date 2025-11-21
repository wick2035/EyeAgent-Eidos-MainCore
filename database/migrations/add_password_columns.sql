-- Migration: Add password column to doctor and patient tables
-- Date: 2025-11-21
-- Description: Add NOT NULL password column with default initial value

USE medical_db;

-- Add password column to doctor table
ALTER TABLE doctor
ADD COLUMN password VARCHAR(255) NOT NULL DEFAULT 'Doctor@123'
COMMENT 'Doctor login password, encrypted in production';

-- Add password column to patient table
ALTER TABLE patient
ADD COLUMN password VARCHAR(255) NOT NULL DEFAULT 'Patient@123'
COMMENT 'Patient login password, encrypted in production';

-- Display confirmation
SELECT 'Password columns added successfully to doctor and patient tables' AS Status;

-- Show updated table structures
DESCRIBE doctor;
DESCRIBE patient;
