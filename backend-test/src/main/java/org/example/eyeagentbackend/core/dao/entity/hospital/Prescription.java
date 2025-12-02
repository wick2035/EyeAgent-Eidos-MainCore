package org.example.eyeagentbackend.core.dao.entity.hospital;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * <p>
 * 处方管理表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("prescription")
@ApiModel(value = "Prescription对象", description = "处方管理表")
public class Prescription extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("患者ID")
    @TableField("Patient_UUID")
    private String patientId;

    @ApiModelProperty("医生ID")
    @TableField("Doctor_UUID")
    private String doctorId;

    @ApiModelProperty("病历ID")
    @TableField("Medical_Record_UUID")
    private String medicalRecordId;

    @ApiModelProperty("处方编号")
    private String prescriptionNumber;

    @ApiModelProperty("处方日期")
    private LocalDateTime prescriptionDate;

    @ApiModelProperty("处方类型")
    private String prescriptionType;

    @ApiModelProperty("诊断描述")
    private String diagnosisDescription;

    @ApiModelProperty("用药指导")
    private String usageInstruction;

    @ApiModelProperty("处方状态")
    private String prescriptionStatus;

    @ApiModelProperty("总金额")
    private BigDecimal totalAmount;

    @ApiModelProperty("备注")
    private String notes;

    @ApiModelProperty("开处方医生姓名")
    private String prescriberName;

    @ApiModelProperty("开处方医生签名")
    private String prescriberSignature;

    @ApiModelProperty("药师姓名")
    private String pharmacistName;

    @ApiModelProperty("药师签名")
    private String pharmacistSignature;

    @ApiModelProperty("配药日期")
    private LocalDateTime dispensedDate;
}
