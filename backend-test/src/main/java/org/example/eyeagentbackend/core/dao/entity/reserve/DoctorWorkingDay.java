package org.example.eyeagentbackend.core.dao.entity.reserve;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

/**
 * <p>
 * 医生工作日配置表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("doctor_working_day")
@ApiModel(value = "DoctorWorkingDay对象", description = "医生工作日配置表")
public class DoctorWorkingDay extends BaseModel {

    @ApiModelProperty("医生ID")
    @NotBlank(message = "医生ID不能为空")
    private String doctorId;

    @ApiModelProperty("工作日（0-6, 0=周日 6=周六）")
    @NotNull(message = "工作日不能为空")
    private Byte weekday;
}
