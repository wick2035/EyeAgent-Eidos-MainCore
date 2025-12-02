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
 * 医生预约配置表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("doctor_config")
@ApiModel(value = "DoctorConfig对象", description = "医生预约配置表")
public class DoctorConfig extends BaseModel {

    @ApiModelProperty("医生ID")
    @NotBlank(message = "医生ID不能为空")
    private String doctorId;

    @ApiModelProperty("是否允许预约")
    @NotNull(message = "是否允许预约不能为空")
    private Boolean canReserve;

    @ApiModelProperty("每小时允许预约人数")
    @NotNull(message = "每小时预约人数不能为空")
    private Integer reservePerHour;
}
