package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.reserve.Agenda;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * <p>
 * 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-03
 */
public interface IAgendaService extends IService<Agenda> {

    List<Agenda> getAgendasByTimeRange(String userId, LocalDateTime startTime, LocalDateTime endTime);

    /**
     * 根据resolved状态和时间范围查询日程
     *
     * @param userId    用户ID
     * @param resolved  是否已解决（null表示查询所有）
     * @param startTime 开始时间
     * @param endTime   结束时间
     * @return 日程列表
     */
    List<Agenda> getResolvedAgendas(String userId, Boolean resolved, LocalDateTime startTime, LocalDateTime endTime);

    /**
     * 统计用户未解决的日程数量
     *
     * @param userId 用户ID
     * @return 未解决日程数量
     */
    Long countUnresolvedAgendas(String userId);

    List<Agenda> listByUserIds(List<String> userIds);

    /**
     * 根据用户ID列表查询日程，按userId分组，每组按startTime升序排序
     *
     * @param userIds 用户ID列表
     * @return Map，key为userId，value为该用户的日程列表（按startTime升序）
     */
    Map<String, List<Agenda>> mapByUserIds(List<String> userIds);

    /**
     * 根据用户ID列表和日期查询日程，按userId分组
     *
     * @param userIds 用户ID列表
     * @param date    日期
     * @return Map，key为userId，value为该用户在指定日期的日程列表
     */
    Map<String, List<Agenda>> mapByUserIdsAndDate(List<String> userIds, LocalDate date);
}
