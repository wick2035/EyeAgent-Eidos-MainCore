package org.example.eyeagentbackend.core.dao.entity.hospital;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

import java.time.LocalDateTime;

/**
 * <p>
 * 提醒任务管理表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("reminder")
@ApiModel(value = "Reminder对象", description = "提醒任务管理表")
public class Reminder extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("患者ID")
    @TableField("Patient_UUID")
    private String patientId;

    @ApiModelProperty("病历ID")
    @TableField("Medical_Record_UUID")
    private String medicalRecordId;

    @ApiModelProperty("预约ID")
    @TableField("Appointment_UUID")
    private String appointmentId;

    @ApiModelProperty("处方ID")
    @TableField("Prescription_UUID")
    private String prescriptionId;

    @ApiModelProperty("提醒类型")
    private String reminderType;

    @ApiModelProperty("提醒标题")
    private String reminderTitle;

    @ApiModelProperty("提醒内容")
    private String reminderContent;

    @ApiModelProperty("计划提醒时间")
    private LocalDateTime scheduledTime;

    @ApiModelProperty("提前天数")
    private Integer advanceDays;

    @ApiModelProperty("发送时间")
    private LocalDateTime sentTime;

    @ApiModelProperty("完成时间")
    private LocalDateTime completedTime;

    @ApiModelProperty("取消时间")
    private LocalDateTime cancelledTime;

    @ApiModelProperty("状态")
    private String status;

    @ApiModelProperty("优先级")
    private String priority;

    @ApiModelProperty("重复类型")
    private String repeatType;

    @ApiModelProperty("已重复次数")
    private Integer repeatCount;

    @ApiModelProperty("最大重复次数")
    private Integer maxRepeatCount;

    @ApiModelProperty("通知方式")
    private String notificationMethod;

    @ApiModelProperty("创建人")
    private String createdBy;

    @ApiModelProperty("备注")
    private String notes;
}
