ALTER TABLE langgraph_thread_mapping
    MODIFY COLUMN patient_id VARCHAR(64) NULL
    COMMENT '患者UUID；科研模式为空';
