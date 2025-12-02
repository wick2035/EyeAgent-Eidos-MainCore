package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.reserve.DoctorWorkingTime;
import org.example.eyeagentbackend.core.dao.mapper.DoctorWorkingTimeMapper;
import org.example.eyeagentbackend.core.dao.service.IDoctorWorkingTimeService;
import org.example.eyeagentbackend.core.dto.WorkingTimeSlot;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * <p>
 * 医生工作时间配置表 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
@Service
public class DoctorWorkingTimeServiceImpl extends ServiceImpl<DoctorWorkingTimeMapper, DoctorWorkingTime>
        implements IDoctorWorkingTimeService {

    @Override
    public List<WorkingTimeSlot> listByDoctorId(String doctorId) {
        return lambdaQuery()
                .eq(DoctorWorkingTime::getDoctorId, doctorId)
                .orderByAsc(DoctorWorkingTime::getStartTime)
                .list()
                .stream()
                .map(wt -> new WorkingTimeSlot(wt.getStartTime(), wt.getEndTime()))
                .toList();
    }

    @Override
    public boolean removeByDoctorId(String doctorId) {
        return lambdaUpdate()
                .eq(DoctorWorkingTime::getDoctorId, doctorId)
                .remove();
    }

    @Override
    public Map<String, List<WorkingTimeSlot>> mapByDoctorIds(List<String> doctorIds) {
        if (doctorIds == null || doctorIds.isEmpty()) {
            return Collections.emptyMap();
        }
        return lambdaQuery()
                .in(DoctorWorkingTime::getDoctorId, doctorIds)
                .list()
                .stream()
                .collect(Collectors.groupingBy(
                        DoctorWorkingTime::getDoctorId,
                        Collectors.mapping(
                                wt -> new WorkingTimeSlot(wt.getStartTime(), wt.getEndTime()),
                                Collectors.toList())));
    }
}
