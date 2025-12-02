package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.activation.DoctorActivate;
import org.example.eyeagentbackend.core.dao.entity.rbac.Doctor;

import java.util.List;

/**
 * <p>
 * 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-26
 */
public interface IDoctorActivateService extends IService<DoctorActivate> {

    boolean checkCode(String code);

    boolean checkDoctor(String doctorId);

    /**
     * 根据医生ID获取激活绑定记录
     *
     * @param doctorId 医生ID
     * @return DoctorActivate 绑定记录，如果不存在返回 null
     */
    DoctorActivate getByDoctorId(String doctorId);

    List<Doctor> listDoctorByCode(String code);
}
