package org.example.eyeagentbackend.core.dao.entity.rbac;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

/**
 * <p>
 * 用户-角色关联表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("user_role")
@ApiModel(value = "UserRole对象", description = "")
public class UserRole extends BaseModel {

    /**
     * 用户ID
     */
    private String userId;

    /**
     * 角色ID
     */
    private String roleId;
}
