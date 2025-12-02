package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.rbac.Roles;
import org.example.eyeagentbackend.core.dao.mapper.RolesMapper;
import org.example.eyeagentbackend.core.dao.service.IRolesService;
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
public class RolesServiceImpl extends ServiceImpl<RolesMapper, Roles> implements IRolesService {
    @Override
    public List<String> getRoleListByUserId(String userId) {
        return baseMapper.getRoleListByUserId(userId);
    }

    @Override
    public Roles getRoleByName(String roleName) {
        LambdaQueryWrapper<Roles> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Roles::getRoleName, roleName).last("limit 1");
        return getOne(queryWrapper);
    }
}
