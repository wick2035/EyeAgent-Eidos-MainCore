package org.example.eyeagentbackend.core.dao.entity.rbac;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;
import org.example.eyeagentbackend.core.enums.Gender;

/**
 * <p>
 * 医生信息表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-26
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("doctor")
@ApiModel(value = "Doctor对象", description = "医生信息表")
public class Doctor extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("医生姓名")
    @NotBlank(message = "姓名不能为空")
    private String name;

    @ApiModelProperty("医院/科室")
    private String hospitalArea;

    @ApiModelProperty("职称")
    private String title;

    @ApiModelProperty("性别（true-男，false-女）")
    @NotNull
    private Gender gender;

    @ApiModelProperty("年龄")
    private Integer age;

    @ApiModelProperty("联系电话")
    @NotBlank(message = "电话不能为空")
    private String phoneNumber;

    @JsonProperty(access = JsonProperty.Access.WRITE_ONLY)
    @ApiModelProperty("登录密码")
    @NotBlank(message = "密码不能为空")
    private String password;

    @ApiModelProperty("专长")
    private String specialty;
}
