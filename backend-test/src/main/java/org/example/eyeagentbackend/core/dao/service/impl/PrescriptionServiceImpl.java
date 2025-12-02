package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.hospital.Prescription;
import org.example.eyeagentbackend.core.dao.mapper.PrescriptionMapper;
import org.example.eyeagentbackend.core.dao.service.IPrescriptionService;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 * 处方管理表 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Service
public class PrescriptionServiceImpl extends ServiceImpl<PrescriptionMapper, Prescription> implements IPrescriptionService {

    @Override
    public List<Prescription> listByPatientIdAsc(String patientId) {
        LambdaQueryWrapper<Prescription> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Prescription::getPatientId, patientId)
                .orderByAsc(Prescription::getCreateTime);

        return list(queryWrapper);
    }

    @Override
    public List<Prescription> listByPatientIdDesc(String patientId, Integer limit) {
        LambdaQueryWrapper<Prescription> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Prescription::getPatientId, patientId)
                .orderByDesc(Prescription::getPrescriptionDate)
                .last(limit != null && limit > 0 ? "LIMIT " + limit : "");

        return list(queryWrapper);
    }
}
