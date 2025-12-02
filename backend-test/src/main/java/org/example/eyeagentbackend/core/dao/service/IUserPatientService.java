package org.example.eyeagentbackend.core.dao.service;

import org.example.eyeagentbackend.core.dao.entity.patient.UserPatient;
import com.baomidou.mybatisplus.extension.service.IService;

/**
 * <p>
 * 用户-患者关联表 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-12-01
 */
public interface IUserPatientService extends IService<UserPatient> {

    /**
     * 根据用户ID和患者ID查询绑定关系
     *
     * @param userId    用户ID（医生/护士等）
     * @param patientId 患者ID
     * @return 绑定关系，不存在返回null
     */
    UserPatient getByUserIdAndPatientId(String userId, String patientId);
}
