package org.example.eyeagentbackend.core.dao.entity.reserve;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

/**
 * <p>
 * 机构工作日配置表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("organization_working_day")
@ApiModel(value = "OrganizationWorkingDay对象", description = "机构工作日配置表")
public class OrganizationWorkingDay extends BaseModel {

    @ApiModelProperty("机构配置ID")
    private String organizationConfigId;

    @ApiModelProperty("工作日（0-6，0=周日，6=周六）")
    private Byte weekday;
}
