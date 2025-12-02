package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.hospital.ReminderConfig;

/**
 * <p>
 * 患者提醒偏好配置表 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
public interface IReminderConfigService extends IService<ReminderConfig> {

    /**
     * 根据患者ID获取提醒配置
     *
     * @param patientId 患者ID
     * @return 提醒配置
     */
    ReminderConfig getByPatientId(String patientId);
}
