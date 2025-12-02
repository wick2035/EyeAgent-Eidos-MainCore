package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.rbac.Permissions;
import org.example.eyeagentbackend.core.dao.mapper.PermissionsMapper;
import org.example.eyeagentbackend.core.dao.service.IPermissionsService;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
@Service
public class PermissionsServiceImpl extends ServiceImpl<PermissionsMapper, Permissions> implements IPermissionsService {
    @Override
    public List<String> getPermissionListByUserId(String userId) {
        return baseMapper.getPermissionListByUserId(userId);
    }

    @Override
    public List<Permissions> getPermissionListByRoleId(String roleId) {
        return baseMapper.getPermissionListByRoleId(roleId);
    }
}
