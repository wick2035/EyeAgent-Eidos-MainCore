package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.reserve.OrganizationConfig;
import org.example.eyeagentbackend.core.dao.mapper.OrganizationConfigMapper;
import org.example.eyeagentbackend.core.dao.service.IOrganizationConfigService;
import org.springframework.stereotype.Service;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
@Service
public class OrganizationConfigServiceImpl extends ServiceImpl<OrganizationConfigMapper, OrganizationConfig> implements IOrganizationConfigService {

    @Override
    public OrganizationConfig getByOrganizationCode(String code) {
        LambdaQueryWrapper<OrganizationConfig> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(OrganizationConfig::getOrganizationCode, code);

        return getOne(queryWrapper);
    }
}
