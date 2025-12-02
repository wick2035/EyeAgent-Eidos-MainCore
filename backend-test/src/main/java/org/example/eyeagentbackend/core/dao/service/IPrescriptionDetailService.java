package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.hospital.PrescriptionDetail;

import java.util.List;
import java.util.Map;

/**
 * <p>
 * 处方明细表 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
public interface IPrescriptionDetailService extends IService<PrescriptionDetail> {

    /**
     * 根据处方ID列表获取处方明细，按处方ID分组
     *
     * @param prescriptionIds 处方ID列表
     * @return Map<处方ID, 处方明细列表>
     */
    Map<String, List<PrescriptionDetail>> mapByPrescriptionIds(List<String> prescriptionIds);
}
