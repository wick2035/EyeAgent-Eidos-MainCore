package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.rbac.Permissions;

import java.util.List;

/**
 * <p>
 * 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
public interface IPermissionsService extends IService<Permissions> {

    List<String> getPermissionListByUserId(String userId);

    List<Permissions> getPermissionListByRoleId(String roleId);
}
