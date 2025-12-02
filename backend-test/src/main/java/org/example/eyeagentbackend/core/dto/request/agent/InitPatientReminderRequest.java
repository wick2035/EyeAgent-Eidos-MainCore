package org.example.eyeagentbackend.core.dto.request.agent;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import org.example.eyeagentbackend.core.dao.entity.hospital.ReminderConfig;

/**
 * @author chengyiyang
 */
@Data
public class InitPatientReminderRequest {
    @NotBlank(message = "患者ID不能为空")
    private String patientId;

    @NotNull(message = "配置不能为空")
    private ReminderConfig config;
}
