package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.hospital.MedicalRecord;
import org.example.eyeagentbackend.core.dao.mapper.MedicalRecordMapper;
import org.example.eyeagentbackend.core.dao.service.IMedicalRecordService;
import org.springframework.stereotype.Service;

/**
 * <p>
 * 患者病历管理表 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Service
public class MedicalRecordServiceImpl extends ServiceImpl<MedicalRecordMapper, MedicalRecord> implements IMedicalRecordService {

}
