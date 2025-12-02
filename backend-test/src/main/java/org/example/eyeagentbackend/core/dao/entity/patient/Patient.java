package org.example.eyeagentbackend.core.dao.entity.patient;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;
import org.example.eyeagentbackend.core.enums.Gender;

/**
 * <p>
 * 患者信息表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-06
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("patient")
@ApiModel(value = "Patient对象", description = "患者信息表")
public class Patient extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("患者姓名")
    @TableField("Name")
    private String patientName;

    @ApiModelProperty("性别（true-男，false-女）")
    private Gender gender;

    @ApiModelProperty("年龄")
    private Integer age;

    @ApiModelProperty("联系电话")
    @TableField("Phone_Number")
    private String phone;

    @ApiModelProperty("身份证号")
    private String idNumber;

    @ApiModelProperty("联系地址")
    private String address;

    @ApiModelProperty("出生日期")
    private java.time.LocalDateTime dateOfBirth;

    @ApiModelProperty("邮箱")
    private String email;

    @ApiModelProperty("紧急联系人")
    private String emergencyContact;

    @ApiModelProperty("紧急联系人电话")
    private String emergencyContactPhone;

    @ApiModelProperty("医保状态")
    private String insuranceStatus;

    @ApiModelProperty("医保卡号")
    private String insuranceCardNumber;

    @ApiModelProperty("患者密码")
    private String password;
}
