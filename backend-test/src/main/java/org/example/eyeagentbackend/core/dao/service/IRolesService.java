package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.rbac.Roles;

import java.util.List;

/**
 * <p>
 * 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
public interface IRolesService extends IService<Roles> {

    List<String> getRoleListByUserId(String userId);

    Roles getRoleByName(String roleName);
}
