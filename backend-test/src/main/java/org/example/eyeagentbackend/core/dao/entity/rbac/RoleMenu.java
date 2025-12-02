package org.example.eyeagentbackend.core.dao.entity.rbac;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

/**
 * <p>
 * 角色-菜单关联表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-07
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("role_menu")
@ApiModel(value = "RoleMenu对象", description = "角色-菜单关联表")
public class RoleMenu extends BaseModel {

    private static final long serialVersionUID = 1L;

    /**
     * 角色ID
     */
    @ApiModelProperty("角色ID")
    private String roleId;

    /**
     * 菜单ID
     */
    @ApiModelProperty("菜单ID")
    private String menuId;
}
