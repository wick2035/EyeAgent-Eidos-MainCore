package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.reserve.OrganizationWorkingDay;
import org.example.eyeagentbackend.core.dao.mapper.OrganizationWorkingDayMapper;
import org.example.eyeagentbackend.core.dao.service.IOrganizationWorkingDayService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
@Service
public class OrganizationWorkingDayServiceImpl extends ServiceImpl<OrganizationWorkingDayMapper, OrganizationWorkingDay>
        implements IOrganizationWorkingDayService {

    @Transactional
    @Override
    public boolean removeByOrganizationCode(String code) {
        LambdaQueryWrapper<OrganizationWorkingDay> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(OrganizationWorkingDay::getOrganizationConfigId, code);

        return remove(queryWrapper);
    }

    @Override
    public List<Byte> listWorkingDaysByConfigId(String configId) {
        LambdaQueryWrapper<OrganizationWorkingDay> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(OrganizationWorkingDay::getOrganizationConfigId, configId)
                .orderByAsc(OrganizationWorkingDay::getWeekday);

        return list(queryWrapper).stream()
                .map(OrganizationWorkingDay::getWeekday).toList();
    }
}
