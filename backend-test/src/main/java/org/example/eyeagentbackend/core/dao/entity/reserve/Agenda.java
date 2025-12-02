package org.example.eyeagentbackend.core.dao.entity.reserve;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;
import org.example.eyeagentbackend.core.enums.AgendaClassify;

import java.time.LocalDateTime;

/**
 * <p>
 * 日程表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-03
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("agenda")
@ApiModel(value = "Agenda对象", description = "日程表")
public class Agenda extends BaseModel {

    @ApiModelProperty("用户ID")
    //todo: update to doctorId
    private String userId;

    //todo: patient id

    @ApiModelProperty("日程标题")
    private String title;

    @ApiModelProperty("分类（normal/operation）")
    private AgendaClassify classify;

    @ApiModelProperty("备注")
    @JsonProperty("description")
    private String remark;

    @ApiModelProperty("是否已经解决（默认为false）")
    private Boolean resolved = false;

    @ApiModelProperty("开始时间")
    private LocalDateTime startTime;

    @ApiModelProperty("结束时间")
    private LocalDateTime endTime;

    @ApiModelProperty("颜色")
    private String color;

    @ApiModelProperty("病历号")
    private String medicalRecordId;

    @ApiModelProperty("患者ID")
    private String patientId;

    @ApiModelProperty("患者姓名")
    private String patientName;

    @ApiModelProperty("严重程度")
    private String severityLevel;

    @ApiModelProperty("日程状态")
    private String status;

    @ApiModelProperty("时间变更记录")
    private String timeChangeRecord;

    @ApiModelProperty("日程类别")
    private String category;
}
