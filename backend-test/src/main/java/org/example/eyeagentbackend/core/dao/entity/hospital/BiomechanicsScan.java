package org.example.eyeagentbackend.core.dao.entity.hospital;

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
 * 生物力学扫描数据表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("biomechanics_scan")
@ApiModel(value = "BiomechanicsScan对象", description = "生物力学扫描数据表")
public class BiomechanicsScan extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("患者ID")
    private String patientId;

    @ApiModelProperty("病历号")
    private String medicalRecordId;

    @ApiModelProperty("患者姓名")
    private String patientName;

    @ApiModelProperty("性别")
    private Boolean gender;

    @ApiModelProperty("出生日期")
    private LocalDateTime birthDate;

    @ApiModelProperty("年龄")
    private Integer age;

    @ApiModelProperty("扫描日期")
    private LocalDateTime scanDate;

    @ApiModelProperty("扫描时间")
    private LocalDateTime scanTime;

    @ApiModelProperty("操作员")
    private String operator;

    @ApiModelProperty("右眼眼轴长度")
    private BigDecimal axlR;

    @ApiModelProperty("左眼眼轴长度")
    private BigDecimal axlL;

    @ApiModelProperty("右眼角膜中央厚度")
    private BigDecimal cctR;

    @ApiModelProperty("左眼角膜中央厚度")
    private BigDecimal cctL;

    @ApiModelProperty("右眼前房深度")
    private BigDecimal acdR;

    @ApiModelProperty("左眼前房深度")
    private BigDecimal acdL;

    @ApiModelProperty("右眼晶状体厚度")
    private BigDecimal ltR;

    @ApiModelProperty("左眼晶状体厚度")
    private BigDecimal ltL;

    @ApiModelProperty("右眼玻璃体厚度")
    private BigDecimal vtR;

    @ApiModelProperty("左眼玻璃体厚度")
    private BigDecimal vtL;

    @ApiModelProperty("右眼K1屈光度")
    private BigDecimal k1DR;

    @ApiModelProperty("右眼K1曲率半径")
    private BigDecimal k1MmR;

    @ApiModelProperty("右眼K1轴位")
    private BigDecimal k1AxisR;

    @ApiModelProperty("左眼K1屈光度")
    private BigDecimal k1DL;

    @ApiModelProperty("左眼K1曲率半径")
    private BigDecimal k1MmL;

    @ApiModelProperty("左眼K1轴位")
    private BigDecimal k1AxisL;

    @ApiModelProperty("右眼K2屈光度")
    private BigDecimal k2DR;

    @ApiModelProperty("右眼K2曲率半径")
    private BigDecimal k2MmR;

    @ApiModelProperty("右眼K2轴位")
    private BigDecimal k2AxisR;

    @ApiModelProperty("左眼K2屈光度")
    private BigDecimal k2DL;

    @ApiModelProperty("左眼K2曲率半径")
    private BigDecimal k2MmL;

    @ApiModelProperty("左眼K2轴位")
    private BigDecimal k2AxisL;

    @ApiModelProperty("右眼散光")
    private BigDecimal astigmatismR;

    @ApiModelProperty("左眼散光")
    private BigDecimal astigmatismL;

    @ApiModelProperty("右眼白到白距离")
    private BigDecimal wtwR;

    @ApiModelProperty("左眼白到白距离")
    private BigDecimal wtwL;

    @ApiModelProperty("右眼瞳孔直径")
    private BigDecimal pupilDiameterR;

    @ApiModelProperty("左眼瞳孔直径")
    private BigDecimal pupilDiameterL;

    @ApiModelProperty("右眼TR参数")
    private BigDecimal trR;

    @ApiModelProperty("左眼TR参数")
    private BigDecimal trL;

    @ApiModelProperty("Ac测量点T1")
    private BigDecimal acT1;

    @ApiModelProperty("Ac测量点T2")
    private BigDecimal acT2;

    @ApiModelProperty("Ac测量点T3")
    private BigDecimal acT3;

    @ApiModelProperty("Ac测量点T4")
    private BigDecimal acT4;

    @ApiModelProperty("Ac测量点T5")
    private BigDecimal acT5;

    @ApiModelProperty("Ac测量点T6")
    private BigDecimal acT6;

    @ApiModelProperty("Ac测量点T7")
    private BigDecimal acT7;

    @ApiModelProperty("Ac测量点T8")
    private BigDecimal acT8;

    @ApiModelProperty("P测量点T1")
    private BigDecimal pT1;

    @ApiModelProperty("P测量点T2")
    private BigDecimal pT2;

    @ApiModelProperty("P测量点T3")
    private BigDecimal pT3;

    @ApiModelProperty("P测量点T4")
    private BigDecimal pT4;

    @ApiModelProperty("P测量点T5")
    private BigDecimal pT5;

    @ApiModelProperty("P测量点T6")
    private BigDecimal pT6;

    @ApiModelProperty("P测量点T7")
    private BigDecimal pT7;

    @ApiModelProperty("P测量点T8")
    private BigDecimal pT8;

    @ApiModelProperty("I1测量点T1")
    private BigDecimal i1T1;

    @ApiModelProperty("I1测量点T2")
    private BigDecimal i1T2;

    @ApiModelProperty("I1测量点T3")
    private BigDecimal i1T3;

    @ApiModelProperty("I1测量点T4")
    private BigDecimal i1T4;

    @ApiModelProperty("I1测量点T5")
    private BigDecimal i1T5;

    @ApiModelProperty("I1测量点T6")
    private BigDecimal i1T6;

    @ApiModelProperty("I1测量点T7")
    private BigDecimal i1T7;

    @ApiModelProperty("I1测量点T8")
    private BigDecimal i1T8;

    @ApiModelProperty("I2测量点T1")
    private BigDecimal i2T1;

    @ApiModelProperty("I2测量点T2")
    private BigDecimal i2T2;

    @ApiModelProperty("I2测量点T3")
    private BigDecimal i2T3;

    @ApiModelProperty("I2测量点T4")
    private BigDecimal i2T4;

    @ApiModelProperty("I2测量点T5")
    private BigDecimal i2T5;

    @ApiModelProperty("I2测量点T6")
    private BigDecimal i2T6;

    @ApiModelProperty("I2测量点T7")
    private BigDecimal i2T7;

    @ApiModelProperty("I2测量点T8")
    private BigDecimal i2T8;

    @ApiModelProperty("I3测量点T1")
    private BigDecimal i3T1;

    @ApiModelProperty("I3测量点T2")
    private BigDecimal i3T2;

    @ApiModelProperty("I3测量点T3")
    private BigDecimal i3T3;

    @ApiModelProperty("I3测量点T4")
    private BigDecimal i3T4;

    @ApiModelProperty("I3测量点T5")
    private BigDecimal i3T5;

    @ApiModelProperty("I3测量点T6")
    private BigDecimal i3T6;

    @ApiModelProperty("I3测量点T7")
    private BigDecimal i3T7;

    @ApiModelProperty("I3测量点T8")
    private BigDecimal i3T8;

    @ApiModelProperty("I4测量点T1")
    private BigDecimal i4T1;

    @ApiModelProperty("I4测量点T2")
    private BigDecimal i4T2;

    @ApiModelProperty("I4测量点T3")
    private BigDecimal i4T3;

    @ApiModelProperty("I4测量点T4")
    private BigDecimal i4T4;

    @ApiModelProperty("I4测量点T5")
    private BigDecimal i4T5;

    @ApiModelProperty("I4测量点T6")
    private BigDecimal i4T6;

    @ApiModelProperty("I4测量点T7")
    private BigDecimal i4T7;

    @ApiModelProperty("I4测量点T8")
    private BigDecimal i4T8;

    @ApiModelProperty("I5测量点T1")
    private BigDecimal i5T1;

    @ApiModelProperty("I5测量点T2")
    private BigDecimal i5T2;

    @ApiModelProperty("I5测量点T3")
    private BigDecimal i5T3;

    @ApiModelProperty("I5测量点T4")
    private BigDecimal i5T4;

    @ApiModelProperty("I5测量点T5")
    private BigDecimal i5T5;

    @ApiModelProperty("I5测量点T6")
    private BigDecimal i5T6;

    @ApiModelProperty("I5测量点T7")
    private BigDecimal i5T7;

    @ApiModelProperty("I5测量点T8")
    private BigDecimal i5T8;

    @ApiModelProperty("R1测量点T1")
    private BigDecimal r1T1;

    @ApiModelProperty("R1测量点T2")
    private BigDecimal r1T2;

    @ApiModelProperty("R1测量点T3")
    private BigDecimal r1T3;

    @ApiModelProperty("R1测量点T4")
    private BigDecimal r1T4;

    @ApiModelProperty("R1测量点T5")
    private BigDecimal r1T5;

    @ApiModelProperty("R1测量点T6")
    private BigDecimal r1T6;

    @ApiModelProperty("R1测量点T7")
    private BigDecimal r1T7;

    @ApiModelProperty("R1测量点T8")
    private BigDecimal r1T8;

    @ApiModelProperty("R2测量点T1")
    private BigDecimal r2T1;

    @ApiModelProperty("R2测量点T2")
    private BigDecimal r2T2;

    @ApiModelProperty("R2测量点T3")
    private BigDecimal r2T3;

    @ApiModelProperty("R2测量点T4")
    private BigDecimal r2T4;

    @ApiModelProperty("R2测量点T5")
    private BigDecimal r2T5;

    @ApiModelProperty("R2测量点T6")
    private BigDecimal r2T6;

    @ApiModelProperty("R2测量点T7")
    private BigDecimal r2T7;

    @ApiModelProperty("R2测量点T8")
    private BigDecimal r2T8;

    @ApiModelProperty("R3测量点T1")
    private BigDecimal r3T1;

    @ApiModelProperty("R3测量点T2")
    private BigDecimal r3T2;

    @ApiModelProperty("R3测量点T3")
    private BigDecimal r3T3;

    @ApiModelProperty("R3测量点T4")
    private BigDecimal r3T4;

    @ApiModelProperty("R3测量点T5")
    private BigDecimal r3T5;

    @ApiModelProperty("R3测量点T6")
    private BigDecimal r3T6;

    @ApiModelProperty("R3测量点T7")
    private BigDecimal r3T7;

    @ApiModelProperty("R3测量点T8")
    private BigDecimal r3T8;

    @ApiModelProperty("R4测量点T1")
    private BigDecimal r4T1;

    @ApiModelProperty("R4测量点T2")
    private BigDecimal r4T2;

    @ApiModelProperty("R4测量点T3")
    private BigDecimal r4T3;

    @ApiModelProperty("R4测量点T4")
    private BigDecimal r4T4;

    @ApiModelProperty("R4测量点T5")
    private BigDecimal r4T5;

    @ApiModelProperty("R4测量点T6")
    private BigDecimal r4T6;

    @ApiModelProperty("R4测量点T7")
    private BigDecimal r4T7;

    @ApiModelProperty("R4测量点T8")
    private BigDecimal r4T8;

    @ApiModelProperty("R5测量点T1")
    private BigDecimal r5T1;

    @ApiModelProperty("R5测量点T2")
    private BigDecimal r5T2;

    @ApiModelProperty("R5测量点T3")
    private BigDecimal r5T3;

    @ApiModelProperty("R5测量点T4")
    private BigDecimal r5T4;

    @ApiModelProperty("R5测量点T5")
    private BigDecimal r5T5;

    @ApiModelProperty("R5测量点T6")
    private BigDecimal r5T6;

    @ApiModelProperty("R5测量点T7")
    private BigDecimal r5T7;

    @ApiModelProperty("R5测量点T8")
    private BigDecimal r5T8;

    @ApiModelProperty("备注信息")
    private String notes;

    @ApiModelProperty("报告状态")
    private String reportStatus;

    @ApiModelProperty("报告类型")
    private String reportType;

    @ApiModelProperty("报告文件路径")
    private String reportPath;

    @ApiModelProperty("审核人")
    private String reviewedBy;

    @ApiModelProperty("审核时间")
    private LocalDateTime reviewedAt;
}
