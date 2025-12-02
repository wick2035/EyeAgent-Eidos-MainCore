package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.hospital.Reminder;

import java.util.List;

/**
 * <p>
 * 提醒任务管理表 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
public interface IReminderService extends IService<Reminder> {

    /**
     * 获取患者的提醒信息，按计划提醒时间倒序排列
     *
     * @param patientId 患者ID
     * @param limit     限制数量
     * @return 提醒列表
     */
    List<Reminder> listByPatientIdDesc(String patientId, Integer limit);
}
