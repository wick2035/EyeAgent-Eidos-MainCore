package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.rbac.Doctor;
import org.example.eyeagentbackend.core.dao.mapper.DoctorMapper;
import org.example.eyeagentbackend.core.dao.service.IDoctorService;
import org.springframework.stereotype.Service;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-26
 */
@Service
public class DoctorServiceImpl extends ServiceImpl<DoctorMapper, Doctor> implements IDoctorService {
    @Override
    public Doctor getByPhone(String phone) {
        LambdaQueryWrapper<Doctor> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Doctor::getPhoneNumber, phone);

        return getOne(queryWrapper);
    }

    @Override
    public boolean hasByPhone(String phone) {
        LambdaQueryWrapper<Doctor> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Doctor::getPhoneNumber, phone);

        return count(queryWrapper) != 0;
    }
}
