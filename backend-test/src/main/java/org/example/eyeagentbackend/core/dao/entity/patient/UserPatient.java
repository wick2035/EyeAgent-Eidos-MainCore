package org.example.eyeagentbackend.core.dao.entity.patient;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

/**
 * <p>
 * 用户-患者关联表
 * </p>
 *
 * @author qtcyy
 * @since 2025-12-01
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("user_patient")
@ApiModel(value = "UserPatient对象", description = "用户-患者关联表")
public class UserPatient extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("用户类型")
    @NotBlank(message = "用户类型不能为空")
    private String userType;

    @ApiModelProperty("用户ID")
    @NotBlank(message = "用户ID不能为空")
    private String userId;

    @ApiModelProperty("患者ID")
    @NotBlank(message = "患者ID不能为空")
    private String patientId;

    @ApiModelProperty("就诊号")
    @NotBlank(message = "就诊号不能为空")
    private String visitCardNumber;
}
