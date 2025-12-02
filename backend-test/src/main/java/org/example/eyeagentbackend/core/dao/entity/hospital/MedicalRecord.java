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
 * 患者病历管理表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("medical_record")
@ApiModel(value = "MedicalRecord对象", description = "患者病历管理表")
public class MedicalRecord extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("患者ID")
    @TableField("Patient_UUID")
    private String patientId;

    @ApiModelProperty("就诊卡号")
    private String visitCardNumber;

    @ApiModelProperty("报告ID")
    private String reportId;

    @ApiModelProperty("就诊日期")
    private LocalDateTime visitDate;

    @ApiModelProperty("就诊时间")
    private LocalDateTime visitTime;

    @ApiModelProperty("科室")
    private String department;

    @ApiModelProperty("主诉")
    private String chiefComplaint;

    @ApiModelProperty("现病史")
    private String presentIllness;

    @ApiModelProperty("既往史")
    private String medicalHistory;

    @ApiModelProperty("过敏史")
    private String allergyHistory;

    @ApiModelProperty("家族史")
    private String familyHistory;

    @ApiModelProperty("用药史")
    private String medicationHistory;

    @ApiModelProperty("体格检查")
    private String physicalExamination;

    @ApiModelProperty("眼部检查结果")
    private String eyeExamResults;

    @ApiModelProperty("特殊检查")
    private String specialExams;

    @ApiModelProperty("辅助检查")
    private String auxiliaryExams;

    @ApiModelProperty("诊断")
    private String diagnosis;

    @ApiModelProperty("AI诊断")
    private String aiDiagnosis;

    @ApiModelProperty("治疗方案")
    private String treatmentPlan;

    @ApiModelProperty("用药")
    private String medication;

    @ApiModelProperty("手术史")
    private String surgicalHistory;

    @ApiModelProperty("住院信息")
    private String hospitalizationInfo;

    @ApiModelProperty("复诊日期")
    private LocalDateTime followUpDate;

    @ApiModelProperty("医生姓名")
    private String physicianName;

    @ApiModelProperty("医生签名")
    private String doctorSignature;

    @ApiModelProperty("打印时间")
    private LocalDateTime printTime;
}
