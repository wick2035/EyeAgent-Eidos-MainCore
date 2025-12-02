package org.example.eyeagentbackend.core.dto.response.agent;

import lombok.Data;
import org.example.eyeagentbackend.core.dao.entity.hospital.Prescription;
import org.example.eyeagentbackend.core.dao.entity.hospital.PrescriptionDetail;

import java.util.List;

/**
 * 处方及其详细信息
 *
 * @author chengyiyang
 */
@Data
public class PrescriptionWithDetail {
    /**
     * 处方信息
     */
    private Prescription prescription;

    /**
     * 处方明细（药品列表）
     */
    private List<PrescriptionDetail> details;
}
