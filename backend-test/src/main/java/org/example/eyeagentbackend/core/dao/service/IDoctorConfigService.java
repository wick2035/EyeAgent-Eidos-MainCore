package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.reserve.DoctorConfig;

import java.util.List;

/**
 * <p>
 * 医生预约配置表 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
public interface IDoctorConfigService extends IService<DoctorConfig> {

    /**
     * 根据医生ID获取配置
     *
     * @param doctorId 医生ID
     * @return 医生配置
     */
    DoctorConfig getByDoctorId(String doctorId);

    List<DoctorConfig> listByDoctorIds(List<String> doctorIds);
}
