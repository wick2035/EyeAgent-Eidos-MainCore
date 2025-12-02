package org.example.eyeagentbackend.core.dto.response.agent;

import lombok.Data;
import org.example.eyeagentbackend.core.dao.entity.hospital.MedicalRecord;
import org.example.eyeagentbackend.core.dao.entity.patient.Patient;

import java.util.List;

/**
 * 患者病历响应（包含患者基本信息和病历列表）
 *
 * @author Claude Code
 */
@Data
public class PatientMedicalRecordsResponse {
    private Patient patient;

    private List<MedicalRecord> medicalRecords;
}
