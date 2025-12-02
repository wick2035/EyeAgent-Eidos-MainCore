package org.example.eyeagentbackend.core.dao.entity.hospital;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

import java.math.BigDecimal;

/**
 * <p>
 * 处方明细表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("prescription_detail")
@ApiModel(value = "PrescriptionDetail对象", description = "处方明细表")
public class PrescriptionDetail extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("处方ID")
    @TableField("Prescription_UUID")
    private String prescriptionId;

    @ApiModelProperty("药品编号")
    private String drugId;

    @ApiModelProperty("药品名称")
    private String drugName;

    @ApiModelProperty("药品规格")
    private String drugSpecification;

    @ApiModelProperty("数量")
    private Integer quantity;

    @ApiModelProperty("单位")
    private String unit;

    @ApiModelProperty("用量")
    private String dosage;

    @ApiModelProperty("频次")
    private String frequency;

    @ApiModelProperty("疗程")
    private String duration;

    @ApiModelProperty("给药途径")
    private String administrationRoute;

    @ApiModelProperty("单价")
    private BigDecimal unitPrice;

    @ApiModelProperty("小计")
    private BigDecimal subtotal;

    @ApiModelProperty("特殊说明")
    private String specialInstructions;
}
