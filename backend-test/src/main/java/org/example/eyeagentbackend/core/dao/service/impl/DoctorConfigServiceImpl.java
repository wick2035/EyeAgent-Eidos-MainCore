package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.reserve.DoctorConfig;
import org.example.eyeagentbackend.core.dao.mapper.DoctorConfigMapper;
import org.example.eyeagentbackend.core.dao.service.IDoctorConfigService;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 * 医生预约配置表 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
@Service
public class DoctorConfigServiceImpl extends ServiceImpl<DoctorConfigMapper, DoctorConfig>
        implements IDoctorConfigService {

    @Override
    public DoctorConfig getByDoctorId(String doctorId) {
        return lambdaQuery()
                .eq(DoctorConfig::getDoctorId, doctorId)
                .one();
    }

    @Override
    public List<DoctorConfig> listByDoctorIds(List<String> doctorIds) {
        LambdaQueryWrapper<DoctorConfig> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.in(DoctorConfig::getDoctorId, doctorIds);

        return list(queryWrapper);
    }
}
