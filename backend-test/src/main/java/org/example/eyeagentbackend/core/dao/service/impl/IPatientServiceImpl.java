package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.patient.Patient;
import org.example.eyeagentbackend.core.dao.mapper.PatientMapper;
import org.example.eyeagentbackend.core.dao.service.IPatientService;
import org.springframework.stereotype.Service;

/**
 * <p>
 * 患者信息服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-06
 */
@Service
public class IPatientServiceImpl extends ServiceImpl<PatientMapper, Patient> implements IPatientService {

    @Override
    public boolean hasPatient(String id) {
        LambdaQueryWrapper<Patient> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Patient::getId, id);

        return count(queryWrapper) > 0;
    }
}
