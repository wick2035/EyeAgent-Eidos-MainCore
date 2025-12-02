package org.example.eyeagentbackend.core.enums;

import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;

/**
 * 角色类型枚举
 * <p>
 * 定义系统中的角色类型，用于权限控制和功能访问
 * </p>
 *
 * @author chengyiyang
 * @since 2025-11-08
 */
@Getter
public enum RoleType {

    /**
     * 访客 - 最低权限级别
     */
    GUEST("访客"),

    /**
     * 普通用户 - 基础功能权限
     */
    USER("普通用户"),

    /**
     * 管理员 - 高级管理权限
     */
    ADMIN("管理员"),

    /**
     * 超级管理员 - 最高权限级别
     */
    SUPER_ADMIN("超级管理员");

    /**
     * 角色名称（与数据库 roles 表中的 role_name 字段对应）
     * 使用 @JsonValue 表示序列化时返回枚举名称
     */
    @JsonValue
    private final String name;

    /**
     * 中文描述
     */
    private final String description;

    /**
     * 构造函数
     *
     * @param description 角色中文描述
     */
    RoleType(String description) {
        this.name = this.name();
        this.description = description;
    }

    /**
     * 根据角色名称字符串获取枚举
     *
     * @param name 角色名称（如 "GUEST", "USER", "ADMIN", "SUPER_ADMIN"）
     * @return 对应的枚举值，如果不存在则返回 null
     */
    public static RoleType fromName(String name) {
        if (name == null || name.isEmpty()) {
            return null;
        }
        for (RoleType roleType : RoleType.values()) {
            if (roleType.name().equals(name)) {
                return roleType;
            }
        }
        return null;
    }

    /**
     * 判断角色名称是否有效
     *
     * @param name 角色名称
     * @return 是否有效
     */
    public static boolean isValid(String name) {
        return fromName(name) != null;
    }

    /**
     * 判断是否为超级管理员
     *
     * @return 是否为超级管理员
     */
    public boolean isSuperAdmin() {
        return this == SUPER_ADMIN;
    }

    /**
     * 判断是否为管理员（包括超级管理员）
     *
     * @return 是否为管理员
     */
    public boolean isAdmin() {
        return this == ADMIN || this == SUPER_ADMIN;
    }
}
