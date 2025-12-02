package org.example.eyeagentbackend.core.dao.entity.reserve;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

import java.time.LocalTime;

/**
 * <p>
 * 医生工作时间配置表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("doctor_working_time")
@ApiModel(value = "DoctorWorkingTime对象", description = "医生工作时间配置表")
public class DoctorWorkingTime extends BaseModel {

    @ApiModelProperty("医生ID")
    @NotBlank(message = "医生ID不能为空")
    private String doctorId;

    @ApiModelProperty("工作开始时间")
    @NotNull(message = "开始时间不能为空")
    private LocalTime startTime;

    @ApiModelProperty("工作结束时间")
    @NotNull(message = "结束时间不能为空")
    private LocalTime endTime;
}
