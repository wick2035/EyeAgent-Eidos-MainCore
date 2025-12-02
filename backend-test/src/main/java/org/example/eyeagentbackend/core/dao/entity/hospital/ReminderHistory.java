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
 * 提醒操作历史记录表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("reminder_history")
@ApiModel(value = "ReminderHistory对象", description = "提醒操作历史记录表")
public class ReminderHistory extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("提醒ID")
    @TableField("Reminder_UUID")
    private String reminderId;

    @ApiModelProperty("操作类型")
    private String actionType;

    @ApiModelProperty("操作时间")
    private LocalDateTime actionTime;

    @ApiModelProperty("操作人")
    private String actionBy;

    @ApiModelProperty("操作详情")
    private String actionDetails;
}
