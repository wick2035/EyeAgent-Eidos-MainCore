package org.example.eyeagentbackend.core.dao.config;

import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import lombok.extern.slf4j.Slf4j;
import org.apache.ibatis.reflection.MetaObject;
import org.example.eyeagentbackend.commen.BaseContext;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

/**
 * MyBatis-Plus 自动填充处理器
 * 用于自动填充创建时间、更新时间、创建人、更新人等字段
 *
 * @author chengyiyang
 * @since 2025-11-02
 */
@Component
@Slf4j
public class MyMetaObjectHandler implements MetaObjectHandler {

    /**
     * 插入时自动填充
     *
     * @param metaObject 元对象
     */
    @Override
    public void insertFill(MetaObject metaObject) {
        log.debug("开始插入填充...");

        // 自动填充创建时间和更新时间
        this.strictInsertFill(metaObject, "createTime", LocalDateTime.class, LocalDateTime.now());
        this.strictInsertFill(metaObject, "updateTime", LocalDateTime.class, LocalDateTime.now());

        // 从 BaseContext 获取当前用户ID
        String currentId = BaseContext.getCurrentId();
        if (currentId != null) {
            log.debug("插入时自动填充用户ID: {}", currentId);
            this.strictInsertFill(metaObject, "createBy", String.class, currentId);
            this.strictInsertFill(metaObject, "updateBy", String.class, currentId);
        } else {
            log.warn("插入时未能获取到当前用户ID，createBy 和 updateBy 将不会被自动填充");
        }
    }

    /**
     * 更新时自动填充
     * <p>使用 setFieldValByName 强制更新，确保即使字段已有值也会被覆盖</p>
     *
     * @param metaObject 元对象
     */
    @Override
    public void updateFill(MetaObject metaObject) {
        log.debug("开始更新填充...");

        // 强制填充更新时间（即使字段已有值也会覆盖）
        this.setFieldValByName("updateTime", LocalDateTime.now(), metaObject);

        // 从 BaseContext 获取当前用户ID
        String currentId = BaseContext.getCurrentId();
        if (currentId != null) {
            log.debug("更新时自动填充用户ID: {}", currentId);
            // 强制填充更新人（即使字段已有值也会覆盖）
            this.setFieldValByName("updateBy", currentId, metaObject);
        } else {
            log.warn("更新时未能获取到当前用户ID，updateBy 将不会被自动填充");
        }
    }
}
