package org.example.eyeagentbackend.core.dto.response.agent;

import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalTime;

/**
 * 空闲时间段 DTO
 *
 * @author chengyiyang
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@ApiModel(value = "FreeTimeSlot", description = "空闲时间段")
public class FreeTimeSlot {

    @ApiModelProperty("开始时间")
    private LocalTime startTime;

    @ApiModelProperty("结束时间")
    private LocalTime endTime;

    @ApiModelProperty("可预约人数")
    private Integer capacity;
}

