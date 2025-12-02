package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.hospital.BiomechanicsScan;

import java.util.List;

/**
 * <p>
 * 生物力学扫描数据表 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
public interface IBiomechanicsScanService extends IService<BiomechanicsScan> {

    /**
     * 根据患者ID获取生物力学扫描数据列表
     *
     * @param patientId 患者ID
     * @return 扫描数据列表
     */
    List<BiomechanicsScan> listByPatientId(String patientId);

    /**
     * 根据病历ID获取生物力学扫描数据
     *
     * @param medicalRecordId 病历ID
     * @return 扫描数据
     */
    BiomechanicsScan getByMedicalRecordId(String medicalRecordId);
}
