package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.rbac.Doctor;

/**
 * <p>
 * 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-26
 */
public interface IDoctorService extends IService<Doctor> {

    Doctor getByPhone(String phone);

    boolean hasByPhone(String phone);
}
