package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.reserve.DoctorWorkingTime;
import org.example.eyeagentbackend.core.dto.WorkingTimeSlot;

import java.util.List;
import java.util.Map;

/**
 * <p>
 * 医生工作时间配置表 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
public interface IDoctorWorkingTimeService extends IService<DoctorWorkingTime> {

    /**
     * 根据医生ID获取工作时间段列表
     *
     * @param doctorId 医生ID
     * @return 工作时间段列表
     */
    List<WorkingTimeSlot> listByDoctorId(String doctorId);

    /**
     * 根据医生ID删除工作时间配置
     *
     * @param doctorId 医生ID
     * @return 是否成功
     */
    boolean removeByDoctorId(String doctorId);

    /**
     * 批量获取医生工作时间配置
     *
     * @param doctorIds 医生ID列表
     * @return Map，key为医生ID，value为工作时间段列表
     */
    Map<String, List<WorkingTimeSlot>> mapByDoctorIds(List<String> doctorIds);
}
