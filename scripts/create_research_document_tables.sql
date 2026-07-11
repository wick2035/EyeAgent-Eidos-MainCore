CREATE TABLE IF NOT EXISTS research_document_ingestion (
    id CHAR(36) NOT NULL,
    doctor_id VARCHAR(36) NOT NULL,
    attachment_id VARCHAR(64) NOT NULL,
    document_version INT UNSIGNED NOT NULL,
    content_sha256 CHAR(64) NOT NULL,
    processor_type VARCHAR(32) NOT NULL,
    extractor_version VARCHAR(32) NOT NULL,
    segment_schema_version VARCHAR(32) NOT NULL,
    status VARCHAR(16) NOT NULL,
    attempt_count INT UNSIGNED NOT NULL DEFAULT 0,
    lease_expires_at DATETIME(6) NULL,
    page_count SMALLINT UNSIGNED NULL,
    error_code VARCHAR(64) NULL,
    started_at DATETIME(6) NULL,
    completed_at DATETIME(6) NULL,
    create_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uk_research_document_ingestion_identity (
        doctor_id,
        attachment_id,
        document_version,
        content_sha256,
        processor_type,
        extractor_version,
        segment_schema_version
    ),
    KEY idx_research_document_ingestion_attachment (doctor_id, attachment_id),
    KEY idx_research_document_ingestion_lease (status, lease_expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS research_document_segment (
    id CHAR(36) NOT NULL,
    ingestion_id CHAR(36) NOT NULL,
    ordinal INT UNSIGNED NOT NULL,
    content TEXT NOT NULL,
    content_sha256 CHAR(64) NOT NULL,
    page_start SMALLINT UNSIGNED NULL,
    page_end SMALLINT UNSIGNED NULL,
    sheet_name VARCHAR(128) NULL,
    row_start INT UNSIGNED NULL,
    row_end INT UNSIGNED NULL,
    token_count INT UNSIGNED NOT NULL,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_research_document_segment_ordinal (ingestion_id, ordinal),
    CONSTRAINT fk_research_document_segment_ingestion
        FOREIGN KEY (ingestion_id)
        REFERENCES research_document_ingestion (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
