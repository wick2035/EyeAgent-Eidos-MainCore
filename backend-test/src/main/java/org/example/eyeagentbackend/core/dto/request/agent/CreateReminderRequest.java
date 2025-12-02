package org.example.eyeagentbackend.core.dto.request.agent;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import org.example.eyeagentbackend.core.dao.entity.hospital.Reminder;

/**
 * @author chengyiyang
 */
@Data
public class CreateReminderRequest {
    @NotBlank(message = "患者ID不能为空")
    private String patientId;

    @NotNull(message = "提醒信息不能为空")
    private Reminder reminder;
}
