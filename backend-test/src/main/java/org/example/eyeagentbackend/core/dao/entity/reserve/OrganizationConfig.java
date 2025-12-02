package org.example.eyeagentbackend.core.dao.entity.reserve;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

import java.time.LocalTime;

/**
 * <p>
 * 机构预约配置表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("organization_config")
@ApiModel(value = "OrganizationConfig对象", description = "机构预约配置表")
public class OrganizationConfig extends BaseModel {

    @ApiModelProperty("机构编码")
    @NotBlank(message = "机构码不能为空")
    private String organizationCode;

    @ApiModelProperty("是否允许预约")
    @NotNull
    private Boolean canReserve;

    @ApiModelProperty("工作开始时间")
    @NotNull
    private LocalTime workingTimeStart;

    @ApiModelProperty("工作结束时间")
    @NotNull
    private LocalTime workingTimeEnd;

    @ApiModelProperty("每小时允许预约人数")
    @NotNull
    @Min(1)
    @Max(50)
    private Integer reservePerHour;
}
