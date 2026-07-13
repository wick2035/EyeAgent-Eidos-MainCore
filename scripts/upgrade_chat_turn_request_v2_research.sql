DROP PROCEDURE IF EXISTS upgrade_chat_turn_request_v2_research;

DELIMITER $$

CREATE PROCEDURE upgrade_chat_turn_request_v2_research()
BEGIN
    ALTER TABLE chat_turn_request
        MODIFY COLUMN patient_id VARCHAR(36) NULL;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'chat_turn_request'
          AND column_name = 'protocol_version'
    ) THEN
        ALTER TABLE chat_turn_request
            ADD COLUMN protocol_version TINYINT UNSIGNED NOT NULL DEFAULT 1
            AFTER request_fingerprint;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'chat_turn_request'
          AND column_name = 'agent_type'
    ) THEN
        ALTER TABLE chat_turn_request
            ADD COLUMN agent_type VARCHAR(16) NOT NULL DEFAULT 'health'
            AFTER protocol_version;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'chat_turn_request'
          AND column_name = 'attachment_scope'
    ) THEN
        ALTER TABLE chat_turn_request
            ADD COLUMN attachment_scope VARCHAR(16) NOT NULL DEFAULT 'patient'
            AFTER agent_type;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'chat_turn_request'
          AND column_name = 'research_options_json'
    ) THEN
        ALTER TABLE chat_turn_request
            ADD COLUMN research_options_json JSON NULL
            AFTER attachment_scope;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'chat_turn_request'
          AND column_name = 'ingestion_ids_json'
    ) THEN
        ALTER TABLE chat_turn_request
            ADD COLUMN ingestion_ids_json JSON NULL
            AFTER research_options_json;
    END IF;
END$$

DELIMITER ;

CALL upgrade_chat_turn_request_v2_research();
DROP PROCEDURE upgrade_chat_turn_request_v2_research;
