package org.example.eyeagentbackend.core.dao.service.impl;

import org.example.eyeagentbackend.core.dao.entity.patient.UserPatient;
import org.example.eyeagentbackend.core.dao.mapper.UserPatientMapper;
import org.example.eyeagentbackend.core.dao.service.IUserPatientService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

/**
 * <p>
 * 用户-患者关联表 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-12-01
 */
@Service
public class UserPatientServiceImpl extends ServiceImpl<UserPatientMapper, UserPatient> implements IUserPatientService {

    @Override
    public UserPatient getByUserIdAndPatientId(String userId, String patientId) {
        return lambdaQuery()
                .eq(UserPatient::getUserId, userId)
                .eq(UserPatient::getPatientId, patientId)
                .one();
    }
}
