package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.hospital.ReminderConfig;
import org.example.eyeagentbackend.core.dao.mapper.ReminderConfigMapper;
import org.example.eyeagentbackend.core.dao.service.IReminderConfigService;
import org.springframework.stereotype.Service;

/**
 * <p>
 * 患者提醒偏好配置表 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Service
public class ReminderConfigServiceImpl extends ServiceImpl<ReminderConfigMapper, ReminderConfig> implements IReminderConfigService {

    @Override
    public ReminderConfig getByPatientId(String patientId) {
        LambdaQueryWrapper<ReminderConfig> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(ReminderConfig::getPatientId, patientId);
        return getOne(queryWrapper);
    }
}
