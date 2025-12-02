package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.hospital.PrescriptionDetail;
import org.example.eyeagentbackend.core.dao.mapper.PrescriptionDetailMapper;
import org.example.eyeagentbackend.core.dao.service.IPrescriptionDetailService;
import org.springframework.stereotype.Service;
import org.springframework.util.CollectionUtils;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * <p>
 * 处方明细表 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Service
public class PrescriptionDetailServiceImpl extends ServiceImpl<PrescriptionDetailMapper, PrescriptionDetail> implements IPrescriptionDetailService {

    @Override
    public Map<String, List<PrescriptionDetail>> mapByPrescriptionIds(List<String> prescriptionIds) {
        if (CollectionUtils.isEmpty(prescriptionIds)) {
            return Collections.emptyMap();
        }

        LambdaQueryWrapper<PrescriptionDetail> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.in(PrescriptionDetail::getPrescriptionId, prescriptionIds);

        List<PrescriptionDetail> details = list(queryWrapper);

        return details.stream()
                .collect(Collectors.groupingBy(PrescriptionDetail::getPrescriptionId));
    }
}
