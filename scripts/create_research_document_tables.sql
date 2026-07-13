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

CREATE TABLE IF NOT EXISTS research_dataset (
    id CHAR(36) NOT NULL,
    ingestion_id CHAR(36) NOT NULL,
    file_type VARCHAR(16) NOT NULL,
    sheet_count SMALLINT UNSIGNED NOT NULL,
    total_data_row_count INT UNSIGNED NOT NULL,
    total_column_count SMALLINT UNSIGNED NOT NULL,
    total_non_empty_cell_count BIGINT UNSIGNED NOT NULL,
    total_formula_like_cell_count BIGINT UNSIGNED NOT NULL,
    descriptor_sha256 CHAR(64) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_research_dataset_ingestion (ingestion_id),
    CONSTRAINT fk_research_dataset_ingestion
        FOREIGN KEY (ingestion_id)
        REFERENCES research_document_ingestion (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS research_dataset_sheet (
    id CHAR(36) NOT NULL,
    dataset_id CHAR(36) NOT NULL,
    ordinal SMALLINT UNSIGNED NOT NULL,
    name VARCHAR(128) NOT NULL,
    header_json JSON NOT NULL,
    header_row_start INT UNSIGNED NOT NULL,
    header_row_end INT UNSIGNED NOT NULL,
    physical_line_count INT UNSIGNED NOT NULL,
    record_count INT UNSIGNED NOT NULL,
    data_row_count INT UNSIGNED NOT NULL,
    column_count SMALLINT UNSIGNED NOT NULL,
    missing_value_counts_json JSON NOT NULL,
    non_empty_cell_count BIGINT UNSIGNED NOT NULL,
    formula_like_cell_count BIGINT UNSIGNED NOT NULL,
    descriptor_sha256 CHAR(64) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_research_dataset_sheet_ordinal (dataset_id, ordinal),
    UNIQUE KEY uk_research_dataset_sheet_name (dataset_id, name),
    CONSTRAINT fk_research_dataset_sheet_dataset
        FOREIGN KEY (dataset_id)
        REFERENCES research_dataset (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS research_dataset_row_chunk (
    id CHAR(36) NOT NULL,
    sheet_id CHAR(36) NOT NULL,
    ordinal INT UNSIGNED NOT NULL,
    physical_row_start INT UNSIGNED NOT NULL,
    physical_row_end INT UNSIGNED NOT NULL,
    logical_row_start INT UNSIGNED NOT NULL,
    logical_row_end INT UNSIGNED NOT NULL,
    row_count INT UNSIGNED NOT NULL,
    non_empty_cell_count BIGINT UNSIGNED NOT NULL,
    formula_like_cell_count BIGINT UNSIGNED NOT NULL,
    rows_json JSON NOT NULL,
    payload_sha256 CHAR(64) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_research_dataset_row_chunk_ordinal (sheet_id, ordinal),
    CONSTRAINT fk_research_dataset_row_chunk_sheet
        FOREIGN KEY (sheet_id)
        REFERENCES research_dataset_sheet (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
