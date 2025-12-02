package org.example.eyeagentbackend.core.dto.request.agent;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import org.example.eyeagentbackend.core.dao.entity.hospital.MedicalRecord;

import java.time.LocalDateTime;

/**
 * @author chengyiyang
 */
@Data
public class ReserveDoctorRequest {
    @NotBlank(message = "patient ID不能为空")
    private String patientId;

    @NotNull
    private LocalDateTime reserveTime;

    @NotBlank(message = "医生ID不能为空")
    private String doctorId;

    @NotNull
    private MedicalRecord medicalRecord;
}
