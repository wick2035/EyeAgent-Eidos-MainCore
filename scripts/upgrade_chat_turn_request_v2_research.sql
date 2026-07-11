ALTER TABLE chat_turn_request
    MODIFY COLUMN patient_id VARCHAR(36) NULL,
    ADD COLUMN protocol_version TINYINT UNSIGNED NOT NULL DEFAULT 1
        AFTER request_fingerprint,
    ADD COLUMN agent_type VARCHAR(16) NOT NULL DEFAULT 'health'
        AFTER protocol_version,
    ADD COLUMN attachment_scope VARCHAR(16) NOT NULL DEFAULT 'patient'
        AFTER agent_type,
    ADD COLUMN research_options_json JSON NULL
        AFTER attachment_scope;
