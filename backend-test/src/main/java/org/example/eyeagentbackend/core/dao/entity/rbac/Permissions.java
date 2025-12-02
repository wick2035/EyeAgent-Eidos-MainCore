package org.example.eyeagentbackend.core.dao.entity.rbac;

import io.swagger.annotations.ApiModel;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

/**
 * <p>
 * 权限表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
@Data
@EqualsAndHashCode(callSuper = true)
@ApiModel(value = "Permissions对象", description = "")
public class Permissions extends BaseModel {

    /**
     * 权限名称
     */
    private String permissionName;
}
