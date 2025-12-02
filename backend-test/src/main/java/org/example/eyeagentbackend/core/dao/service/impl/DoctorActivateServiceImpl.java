package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.activation.DoctorActivate;
import org.example.eyeagentbackend.core.dao.entity.rbac.Doctor;
import org.example.eyeagentbackend.core.dao.mapper.DoctorActivateMapper;
import org.example.eyeagentbackend.core.dao.service.IDoctorActivateService;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-26
 */
@Service
public class DoctorActivateServiceImpl extends ServiceImpl<DoctorActivateMapper, DoctorActivate>
        implements IDoctorActivateService {
    @Override
    public boolean checkCode(String code) {
        LambdaQueryWrapper<DoctorActivate> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(DoctorActivate::getOrganizationCode, code);

        return count(queryWrapper) == 0;
    }

    @Override
    public boolean checkDoctor(String doctorId) {
        LambdaQueryWrapper<DoctorActivate> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(DoctorActivate::getDoctorId, doctorId);

        return count(queryWrapper) != 0;
    }

    @Override
    public DoctorActivate getByDoctorId(String doctorId) {
        LambdaQueryWrapper<DoctorActivate> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(DoctorActivate::getDoctorId, doctorId);

        return getOne(queryWrapper);
    }

    @Override
    public List<Doctor> listDoctorByCode(String code) {
        return baseMapper.listDoctorByCode(code);
    }
}
