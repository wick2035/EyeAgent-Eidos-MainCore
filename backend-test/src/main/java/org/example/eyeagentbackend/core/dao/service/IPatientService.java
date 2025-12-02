package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.patient.Patient;

/**
 * <p>
 * 患者信息服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-06
 */
public interface IPatientService extends IService<Patient> {

    boolean hasPatient(String id);
}
