package org.example.eyeagentbackend.core.dao.entity.base;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.Version;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 实体类基类，包含所有实体类的公共字段
 *
 * @author qtcyy
 * @since 2025-11-01
 */
@Data
@EqualsAndHashCode(callSuper = false)
public abstract class BaseModel implements Serializable {

    private static final long serialVersionUID = 1L;

    /**
     * 主键ID（自动生成UUID）
     */
    @TableId(type = IdType.ASSIGN_UUID)
    @NotBlank(message = "主键ID不能为空")
    private String id;

    /**
     * 创建时间
     */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    /**
     * 创建人
     */
    @TableField(fill = FieldFill.INSERT)
    private String createBy;

    /**
     * 更新时间
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    /**
     * 更新人
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private String updateBy;

    /**
     * 逻辑删除标识（0-未删除，1-已删除）
     */
    private Boolean deleted;

    /**
     * 乐观锁版本号
     */
    @Version
    private Integer version;
}
