package org.example.eyeagentbackend.core.dto.response.agent;

import lombok.Data;
import org.example.eyeagentbackend.core.dao.entity.patient.Patient;

import java.util.List;

/**
 * 患者处方详细信息响应
 *
 * @author chengyiyang
 */
@Data
public class PatientPrescriptionDetailResponse {
    /**
     * 患者信息
     */
    private Patient patient;

    /**
     * 处方及详细信息列表
     */
    private List<PrescriptionWithDetail> prescriptions;
}

