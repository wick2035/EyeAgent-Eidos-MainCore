package org.example.eyeagentbackend.core.dao.entity.rbac;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;
import org.example.eyeagentbackend.core.enums.MenuIcon;
import org.example.eyeagentbackend.core.enums.MenuItemKey;

/**
 * <p>
 * 菜单表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-07
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("menu")
@ApiModel(value = "Menu对象", description = "菜单表")
public class Menu extends BaseModel {

    private static final long serialVersionUID = 1L;

    /**
     * 菜单唯一标识（用于前端路由key）
     */
    @ApiModelProperty("菜单唯一标识")
    @JsonProperty("key")
    private MenuItemKey itemKey;

    /**
     * 菜单名称
     */
    @ApiModelProperty("菜单名称")
    @JsonProperty("label")
    private String menuName;

    /**
     * 菜单路由地址（href/path）
     */
    @ApiModelProperty("菜单路由地址")
    private String href;

    /**
     * 菜单图标
     */
    @ApiModelProperty("菜单图标")
    @JsonProperty("iconStr")
    private MenuIcon icon;

    /**
     * 排序号（数字越小越靠前）
     */
    @ApiModelProperty("排序号")
    private Integer sortOrder;

    /**
     * 菜单状态（0=禁用，1=启用）
     */
    @ApiModelProperty("菜单状态（0=禁用，1=启用）")
    private Integer menuStatus;
}
