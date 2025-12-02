package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.agent.ChatConversation;
import org.example.eyeagentbackend.core.dao.mapper.ChatConversationMapper;
import org.example.eyeagentbackend.core.dao.service.IChatConversationService;
import org.springframework.stereotype.Service;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-26
 */
@Service
public class ChatConversationServiceImpl extends ServiceImpl<ChatConversationMapper, ChatConversation> implements IChatConversationService {

}
