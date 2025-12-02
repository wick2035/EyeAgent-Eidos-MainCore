package org.example.eyeagentbackend.core.dto.response.agent;

import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 医生空闲时间响应 DTO
 *
 * @author chengyiyang
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@ApiModel(value = "DoctorFreeTimeResponse", description = "医生空闲时间响应")
public class DoctorFreeTimeResponse {

    @ApiModelProperty("医生ID")
    private String doctorId;

    @ApiModelProperty("空闲时间段列表")
    private List<FreeTimeSlot> freeSlots;
}

