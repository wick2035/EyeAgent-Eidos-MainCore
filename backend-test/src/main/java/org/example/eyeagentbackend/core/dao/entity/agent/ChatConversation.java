package org.example.eyeagentbackend.core.dao.entity.agent;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

/**
 * <p>
 * 聊天会话表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-26
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("chat_conversation")
@ApiModel(value = "ChatConversation对象", description = "聊天会话表")
public class ChatConversation extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("用户类型")
    private String userType;

    @ApiModelProperty("会话主体ID（患者/医生）")
    private String hostId;

    @ApiModelProperty("会话标题")
    private String title;

    @ApiModelProperty("会话摘要")
    private String summary;

    @ApiModelProperty("消息总数")
    private Integer totalMessages;
}
