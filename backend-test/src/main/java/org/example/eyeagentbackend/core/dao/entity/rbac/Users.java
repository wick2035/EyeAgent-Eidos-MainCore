package org.example.eyeagentbackend.core.dao.entity.rbac;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;
import org.example.eyeagentbackend.core.enums.Gender;
import org.example.eyeagentbackend.core.enums.UserStatus;

import java.time.LocalDateTime;

/**
 * 用户实体类
 * <p>
 * 用于存储系统用户的基本信息，包括账号、个人资料、状态等
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
@Data
@EqualsAndHashCode(callSuper = true)
@ApiModel(value = "Users对象", description = "用户实体，包含用户基本信息和状态")
public class Users extends BaseModel {

    /**
     * 用户名（登录账号）
     */
    @NotBlank(message = "用户名不能为空")
    @ApiModelProperty(value = "用户名", required = true, example = "user123")
    private String username;

    /**
     * 用户姓名（真实姓名）
     */
    @NotBlank(message = "用户姓名不能为空")
    @ApiModelProperty(value = "用户姓名", example = "张三")
    @JsonProperty("name")
    private String uname;

    /**
     * 密码（加密存储）
     */
    @JsonIgnore
    @ApiModelProperty(value = "密码", required = true, hidden = true, notes = "密码字段不会在JSON中序列化")
    private String password;

    /**
     * 邮箱地址
     */
    @NotBlank(message = "邮箱不能为空")
    @ApiModelProperty(value = "邮箱", example = "zhangsan@example.com")
    private String email;

    /**
     * 手机号码
     */
    @NotBlank(message = "手机号不能为空")
    @ApiModelProperty(value = "手机号", example = "13800138000")
    private String phone;

    /**
     * 性别
     */
    @ApiModelProperty(value = "性别", notes = "MALE=男, FEMALE=女", example = "MALE")
    private Gender gender;

    /**
     * 所属科室
     */
    @NotBlank(message = "科室不能为空")
    @ApiModelProperty(value = "科室", example = "眼科")
    private String department;

    /**
     * 用户状态
     */
    @ApiModelProperty(value = "用户状态", notes = "NORMAL=正常, LOCKED=锁定", example = "NORMAL")
    @JsonProperty("status")
    private UserStatus userStatus = UserStatus.NORMAL;

    /**
     * 最后登录时间
     */
    @ApiModelProperty(value = "最后登录时间", example = "2025-11-08T10:30:00")
    private LocalDateTime lastLogin;
}
