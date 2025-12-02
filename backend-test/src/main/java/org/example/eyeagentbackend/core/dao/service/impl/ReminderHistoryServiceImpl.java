package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.hospital.ReminderHistory;
import org.example.eyeagentbackend.core.dao.mapper.ReminderHistoryMapper;
import org.example.eyeagentbackend.core.dao.service.IReminderHistoryService;
import org.springframework.stereotype.Service;

/**
 * <p>
 * 提醒操作历史记录表 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Service
public class ReminderHistoryServiceImpl extends ServiceImpl<ReminderHistoryMapper, ReminderHistory> implements IReminderHistoryService {

}
