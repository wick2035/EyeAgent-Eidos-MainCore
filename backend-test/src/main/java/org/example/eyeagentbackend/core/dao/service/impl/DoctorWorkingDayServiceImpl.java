package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.reserve.DoctorWorkingDay;
import org.example.eyeagentbackend.core.dao.mapper.DoctorWorkingDayMapper;
import org.example.eyeagentbackend.core.dao.service.IDoctorWorkingDayService;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * <p>
 * 医生工作日配置表 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
@Service
public class DoctorWorkingDayServiceImpl extends ServiceImpl<DoctorWorkingDayMapper, DoctorWorkingDay>
        implements IDoctorWorkingDayService {

    @Override
    public List<Byte> listByDoctorId(String doctorId) {
        return lambdaQuery()
                .eq(DoctorWorkingDay::getDoctorId, doctorId)
                .list()
                .stream()
                .map(DoctorWorkingDay::getWeekday)
                .sorted()
                .toList();
    }

    @Override
    public boolean removeByDoctorId(String doctorId) {
        return lambdaUpdate()
                .eq(DoctorWorkingDay::getDoctorId, doctorId)
                .remove();
    }

    @Override
    public Map<String, List<Byte>> mapByDoctorIds(List<String> doctorIds) {
        if (doctorIds == null || doctorIds.isEmpty()) {
            return Collections.emptyMap();
        }
        return lambdaQuery()
                .in(DoctorWorkingDay::getDoctorId, doctorIds)
                .list()
                .stream()
                .collect(Collectors.groupingBy(
                        DoctorWorkingDay::getDoctorId,
                        Collectors.mapping(
                                DoctorWorkingDay::getWeekday,
                                Collectors.toList())));
    }
}
