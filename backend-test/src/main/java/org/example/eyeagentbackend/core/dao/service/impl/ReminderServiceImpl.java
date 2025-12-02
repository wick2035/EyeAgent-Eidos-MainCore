package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.hospital.Reminder;
import org.example.eyeagentbackend.core.dao.mapper.ReminderMapper;
import org.example.eyeagentbackend.core.dao.service.IReminderService;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 * 提醒任务管理表 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Service
public class ReminderServiceImpl extends ServiceImpl<ReminderMapper, Reminder> implements IReminderService {

    @Override
    public List<Reminder> listByPatientIdDesc(String patientId, Integer limit) {
        LambdaQueryWrapper<Reminder> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Reminder::getPatientId, patientId)
                .orderByDesc(Reminder::getScheduledTime)
                .last(limit != null && limit > 0 ? "LIMIT " + limit : "");

        return list(queryWrapper);
    }
}
