package org.example.eyeagentbackend.core.dto.response.agent;

import lombok.Data;
import org.example.eyeagentbackend.core.dao.entity.hospital.Prescription;
import org.example.eyeagentbackend.core.dao.entity.patient.Patient;

import java.util.List;

/**
 * @author chengyiyang
 */
@Data
public class PatientPrescriptionResponse {
    private Patient patient;

    private List<Prescription> prescriptions;
}
