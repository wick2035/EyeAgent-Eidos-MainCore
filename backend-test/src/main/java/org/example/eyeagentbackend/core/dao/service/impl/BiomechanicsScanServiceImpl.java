package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.hospital.BiomechanicsScan;
import org.example.eyeagentbackend.core.dao.mapper.BiomechanicsScanMapper;
import org.example.eyeagentbackend.core.dao.service.IBiomechanicsScanService;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 * 生物力学扫描数据表 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Service
public class BiomechanicsScanServiceImpl extends ServiceImpl<BiomechanicsScanMapper, BiomechanicsScan> implements IBiomechanicsScanService {

    @Override
    public List<BiomechanicsScan> listByPatientId(String patientId) {
        LambdaQueryWrapper<BiomechanicsScan> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(BiomechanicsScan::getPatientId, patientId)
                .orderByDesc(BiomechanicsScan::getScanDate);
        return list(queryWrapper);
    }

    @Override
    public BiomechanicsScan getByMedicalRecordId(String medicalRecordId) {
        LambdaQueryWrapper<BiomechanicsScan> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(BiomechanicsScan::getMedicalRecordId, medicalRecordId);
        return getOne(queryWrapper);
    }
}
