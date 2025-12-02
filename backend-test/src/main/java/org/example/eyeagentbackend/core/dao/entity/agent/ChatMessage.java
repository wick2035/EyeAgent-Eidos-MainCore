package org.example.eyeagentbackend.core.dao.entity.agent;

import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.example.eyeagentbackend.core.dao.entity.base.BaseModel;

/**
 * <p>
 * 聊天消息表
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-26
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("chat_message")
@ApiModel(value = "ChatMessage对象", description = "聊天消息表")
public class ChatMessage extends BaseModel {

    private static final long serialVersionUID = 1L;

    @ApiModelProperty("会话ID")
    private String chatId;

    @ApiModelProperty("消息顺序")
    private Integer messageOrder;

    @ApiModelProperty("消息内容")
    private String messageContent;

    @ApiModelProperty("消息类型")
    private String messageType;

    @ApiModelProperty("发送者ID")
    private String senderId;

    @ApiModelProperty("上下文信息")
    private String context;

    @ApiModelProperty("消耗的Token数量")
    private Integer tokenUsed;
}
