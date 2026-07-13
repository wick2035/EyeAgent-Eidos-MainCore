DROP PROCEDURE IF EXISTS upgrade_research_dataset_c3_2;

DELIMITER $$

CREATE PROCEDURE upgrade_research_dataset_c3_2()
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'research_dataset'
          AND column_name = 'date_system'
    ) THEN
        ALTER TABLE research_dataset
            ADD COLUMN date_system VARCHAR(4) NULL
            AFTER file_type;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'research_dataset'
          AND column_name = 'workbook_sheet_count'
    ) THEN
        ALTER TABLE research_dataset
            ADD COLUMN workbook_sheet_count SMALLINT UNSIGNED NULL
            AFTER date_system;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'research_dataset'
          AND column_name = 'empty_sheet_count'
    ) THEN
        ALTER TABLE research_dataset
            ADD COLUMN empty_sheet_count SMALLINT UNSIGNED NULL
            AFTER workbook_sheet_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'research_dataset'
          AND column_name = 'total_record_count'
    ) THEN
        ALTER TABLE research_dataset
            ADD COLUMN total_record_count INT UNSIGNED NULL
            AFTER empty_sheet_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'research_dataset'
          AND column_name = 'total_formula_cell_count'
    ) THEN
        ALTER TABLE research_dataset
            ADD COLUMN total_formula_cell_count BIGINT UNSIGNED NOT NULL DEFAULT 0
            AFTER total_formula_like_cell_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'research_dataset'
          AND column_name = 'total_merged_range_count'
    ) THEN
        ALTER TABLE research_dataset
            ADD COLUMN total_merged_range_count BIGINT UNSIGNED NOT NULL DEFAULT 0
            AFTER total_formula_cell_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'research_dataset_sheet'
          AND column_name = 'visibility'
    ) THEN
        ALTER TABLE research_dataset_sheet
            ADD COLUMN visibility VARCHAR(16) NOT NULL DEFAULT 'visible'
            AFTER name;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'research_dataset_sheet'
          AND column_name = 'formula_cell_count'
    ) THEN
        ALTER TABLE research_dataset_sheet
            ADD COLUMN formula_cell_count BIGINT UNSIGNED NOT NULL DEFAULT 0
            AFTER formula_like_cell_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'research_dataset_sheet'
          AND column_name = 'merged_range_count'
    ) THEN
        ALTER TABLE research_dataset_sheet
            ADD COLUMN merged_range_count BIGINT UNSIGNED NOT NULL DEFAULT 0
            AFTER formula_cell_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'research_dataset_row_chunk'
          AND column_name = 'formula_cell_count'
    ) THEN
        ALTER TABLE research_dataset_row_chunk
            ADD COLUMN formula_cell_count BIGINT UNSIGNED NOT NULL DEFAULT 0
            AFTER formula_like_cell_count;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'research_dataset_sheet'
          AND column_name = 'name'
          AND (
              character_set_name <> 'utf8mb4'
              OR collation_name <> 'utf8mb4_bin'
          )
    ) THEN
        ALTER TABLE research_dataset_sheet
            MODIFY COLUMN name VARCHAR(128)
            CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL;
    END IF;
END$$

DELIMITER ;

CALL upgrade_research_dataset_c3_2();
DROP PROCEDURE upgrade_research_dataset_c3_2;
