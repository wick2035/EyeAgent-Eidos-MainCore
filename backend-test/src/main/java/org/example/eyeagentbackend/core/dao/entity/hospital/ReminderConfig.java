package org.example.eyeagentbackend.core.dao.entity.hospital;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

import java.time.LocalTime;

/**
 * <p>
 * 患者提醒偏好配置表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("reminder_config")
@ApiModel(value = "ReminderConfig对象", description = "患者提醒偏好配置表")
public class ReminderConfig extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("患者ID")
    @TableField("Patient_UUID")
    private String patientId;

    @ApiModelProperty("启用复诊提醒（0-否，1-是）")
    private Boolean enableFollowUp;

    @ApiModelProperty("启用预约提醒（0-否，1-是）")
    private Boolean enableAppointment;

    @ApiModelProperty("启用用药提醒（0-否，1-是）")
    private Boolean enableMedication;

    @ApiModelProperty("默认提前天数")
    private Integer defaultAdvanceDays;

    @ApiModelProperty("首选通知方式")
    private String preferredNotificationMethod;

    @ApiModelProperty("免打扰开始时间")
    private LocalTime quietHoursStart;

    @ApiModelProperty("免打扰结束时间")
    private LocalTime quietHoursEnd;
}
