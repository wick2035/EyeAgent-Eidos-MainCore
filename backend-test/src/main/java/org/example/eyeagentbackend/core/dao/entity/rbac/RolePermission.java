package org.example.eyeagentbackend.core.dao.entity.rbac;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

/**
 * <p>
 * 角色-权限关联表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("role_permission")
@ApiModel(value = "RolePermission对象", description = "")
public class RolePermission extends BaseModel {

    /**
     * 角色ID
     */
    private String roleId;

    /**
     * 权限ID
     */
    private String permissionId;
}
