package org.example.eyeagentbackend.core.dao.entity.activation;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.ToString;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;
import org.example.eyeagentbackend.core.enums.ActivationKeyStatus;

import java.time.LocalDateTime;

/**
 * <p>
 * 激活密钥表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-16
 */
@Data
@EqualsAndHashCode(callSuper = true)
@ToString(callSuper = true)
@TableName("activation")
@ApiModel(value = "Activation对象", description = "激活密钥表")
public class Activation extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("用户ID")
    private String userId;

    @ApiModelProperty("激活密钥状态（inactive=停用, active=启用, expired=过期）")
    @NotNull
    private ActivationKeyStatus keyStatus;

    @ApiModelProperty("过期时间")
    @NotNull
    private LocalDateTime expireTime;

    @ApiModelProperty("机构码")
    private String organizationCode;

    @ApiModelProperty("机构名称")
    private String organizationName;
}
