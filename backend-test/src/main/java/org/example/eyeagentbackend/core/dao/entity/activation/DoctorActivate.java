package org.example.eyeagentbackend.core.dao.entity.activation;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.ToString;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;
import org.example.eyeagentbackend.core.enums.DoctorActivateStatus;

/**
 * <p>
 * 医生激活表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-26
 */
@Data
@EqualsAndHashCode(callSuper = true)
@ToString(callSuper = true)
@TableName("doctor_activate")
@ApiModel(value = "DoctorActivate对象", description = "医生激活表")
public class DoctorActivate extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("医生ID")
    private String doctorId;

    @ApiModelProperty("机构码")
    private String organizationCode;

    @ApiModelProperty("激活状态")
    private DoctorActivateStatus activateStatus;
}
