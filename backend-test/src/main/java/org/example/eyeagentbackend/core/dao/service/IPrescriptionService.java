package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.hospital.Prescription;

import java.util.List;

/**
 * <p>
 * 处方管理表 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
public interface IPrescriptionService extends IService<Prescription> {

    List<Prescription> listByPatientIdAsc(String patientId);

    /**
     * 获取患者最近的N份处方，按时间倒序排列
     *
     * @param patientId 患者ID
     * @param limit     限制数量
     * @return 处方列表
     */
    List<Prescription> listByPatientIdDesc(String patientId, Integer limit);
}
