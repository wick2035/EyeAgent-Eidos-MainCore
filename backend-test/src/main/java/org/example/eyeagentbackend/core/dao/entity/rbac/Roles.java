package org.example.eyeagentbackend.core.dao.entity.rbac;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.annotations.ApiModel;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

/**
 * <p>
 * 角色表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
@Data
@EqualsAndHashCode(callSuper = true)
@ApiModel(value = "Roles对象", description = "")
public class Roles extends BaseModel {

    /**
     * 角色名称
     */
    @JsonProperty("role")
    private String roleName;

    /**
     * 角色级别
     * 级别越高权限越大，预留间隔方便扩展
     * GUEST=10, USER=20, ADMIN=30, SUPER_ADMIN=40
     */
    private Integer level;
}
