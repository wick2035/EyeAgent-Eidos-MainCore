package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.reserve.Agenda;
import org.example.eyeagentbackend.core.dao.mapper.AgendaMapper;
import org.example.eyeagentbackend.core.dao.service.IAgendaService;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-03
 */
@Service
public class AgendaServiceImpl extends ServiceImpl<AgendaMapper, Agenda> implements IAgendaService {
    @Override
    public List<Agenda> getAgendasByTimeRange(String userId, LocalDateTime startTime, LocalDateTime endTime) {
        LambdaQueryWrapper<Agenda> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Agenda::getUserId, userId)
                .ge(Agenda::getEndTime, startTime)
                .le(Agenda::getStartTime, endTime);
        return list(queryWrapper);
    }

    @Override
    public List<Agenda> getResolvedAgendas(String userId, Boolean resolved, LocalDateTime startTime,
            LocalDateTime endTime) {
        LambdaQueryWrapper<Agenda> queryWrapper = new LambdaQueryWrapper<>();

        // 用户ID过滤
        queryWrapper.eq(Agenda::getUserId, userId);

        // resolved状态过滤（如果不为null）
        if (resolved != null) {
            queryWrapper.eq(Agenda::getResolved, resolved);
        }

        // 时间范围过滤
        queryWrapper.ge(Agenda::getEndTime, startTime)
                .le(Agenda::getStartTime, endTime);

        // 按开始时间排序
        queryWrapper.orderByAsc(Agenda::getStartTime);

        return list(queryWrapper);
    }

    @Override
    public Long countUnresolvedAgendas(String userId) {
        LambdaQueryWrapper<Agenda> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Agenda::getUserId, userId)
                .eq(Agenda::getResolved, false);
        return count(queryWrapper);
    }

    @Override
    public List<Agenda> listByUserIds(List<String> userIds) {
        LambdaQueryWrapper<Agenda> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.in(Agenda::getUserId, userIds);

        return list(queryWrapper);
    }

    @Override
    public Map<String, List<Agenda>> mapByUserIds(List<String> userIds) {
        LambdaQueryWrapper<Agenda> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.in(Agenda::getUserId, userIds)
                .orderByAsc(Agenda::getStartTime);

        return list(queryWrapper).stream()
                .collect(Collectors.groupingBy(Agenda::getUserId));
    }

    @Override
    public Map<String, List<Agenda>> mapByUserIdsAndDate(List<String> userIds, LocalDate date) {
        if (userIds == null || userIds.isEmpty() || date == null) {
            return Collections.emptyMap();
        }

        LocalDateTime dayStart = date.atStartOfDay();
        LocalDateTime dayEnd = date.atTime(LocalTime.MAX);

        // TODO: 当前只查询 startTime 在当天的日程，会漏掉跨天日程（前一天开始、当天结束）
        //       如需支持跨天日程，应改为重叠检测：.ge(endTime, dayStart).le(startTime, dayEnd)
        LambdaQueryWrapper<Agenda> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.in(Agenda::getUserId, userIds)
                .ge(Agenda::getStartTime, dayStart)
                .le(Agenda::getStartTime, dayEnd)
                .orderByAsc(Agenda::getStartTime);

        return list(queryWrapper).stream()
                .collect(Collectors.groupingBy(Agenda::getUserId));
    }
}
