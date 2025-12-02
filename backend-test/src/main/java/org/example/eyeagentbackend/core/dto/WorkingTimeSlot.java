package org.example.eyeagentbackend.core.dto;

import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalTime;

/**
 * 工作时间段 DTO
 *
 * @author chengyiyang
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@ApiModel(value = "WorkingTimeSlot", description = "工作时间段")
public class WorkingTimeSlot {

    @ApiModelProperty("工作开始时间")
    @NotNull(message = "开始时间不能为空")
    private LocalTime startTime;

    @ApiModelProperty("工作结束时间")
    @NotNull(message = "结束时间不能为空")
    private LocalTime endTime;
}
