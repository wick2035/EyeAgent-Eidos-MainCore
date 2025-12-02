package org.example.eyeagentbackend.core.dao.entity.hospital;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import jakarta.validation.constraints.*;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * <p>
 * 眼科药品管理表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("drugs")
@ApiModel(value = "Drugs对象", description = "眼科药品管理表")
public class Drugs extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("药品编号（业务ID）")
    @NotBlank(message = "药品编号不能为空")
    @Size(min = 1, max = 50, message = "药品编号长度应在1-50个字符之间")
    private String drugId;

    @ApiModelProperty("药品名称")
    @NotBlank(message = "药品名称不能为空")
    @Size(min = 2, max = 100, message = "药品名称长度应在2-100个字符之间")
    private String drugName;

    @ApiModelProperty("药品分类")
    @NotBlank(message = "药品分类不能为空")
    @Size(max = 50, message = "药品分类长度不能超过50个字符")
    private String drugCategory;

    @ApiModelProperty("药品规格")
    @Size(max = 50, message = "药品规格长度不能超过50个字符")
    private String drugSpecification;

    @ApiModelProperty("剂型")
    @Size(max = 30, message = "剂型长度不能超过30个字符")
    private String drugDosageForm;

    @ApiModelProperty("生产厂家")
    @Size(max = 100, message = "生产厂家长度不能超过100个字符")
    private String manufacturer;

    @ApiModelProperty("批号")
    @Size(max = 50, message = "批号长度不能超过50个字符")
    private String batchNumber;

    @ApiModelProperty("过期日期")
    @Future(message = "过期日期必须在未来")
    private LocalDateTime expiryDate;

    @ApiModelProperty("价格")
    @NotNull(message = "价格不能为空")
    @DecimalMin(value = "0.0", inclusive = false, message = "价格必须大于0")
    @DecimalMax(value = "999999.99", message = "价格不能超过999999.99")
    private BigDecimal price;

    @ApiModelProperty("库存数量")
    @NotNull(message = "库存数量不能为空")
    @PositiveOrZero(message = "库存数量不能为负数")
    private Integer stockQuantity;

    @ApiModelProperty("是否处方药（0-否，1-是）")
    private Boolean isPrescriptionDrug;

    @ApiModelProperty("药品状态")
    @Size(max = 20, message = "药品状态长度不能超过20个字符")
    private String drugStatus;

    @ApiModelProperty("医保类别")
    @Size(max = 50, message = "医保类别长度不能超过50个字符")
    private String insuranceCategory;

    @ApiModelProperty("警告信息")
    @Size(max = 500, message = "警告信息长度不能超过500个字符")
    private String warningInfo;

    @ApiModelProperty("药品描述")
    @Size(max = 1000, message = "药品描述长度不能超过1000个字符")
    private String drugDescription;
}
