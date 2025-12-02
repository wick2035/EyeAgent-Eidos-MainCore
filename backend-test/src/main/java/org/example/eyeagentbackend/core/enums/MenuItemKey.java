package org.example.eyeagentbackend.core.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;

/**
 * 菜单唯一标识枚举
 * 数据库存储：英文 key（如 dashboard, reserve）
 * API返回：英文 key
 *
 * @author qtcyy
 * @since 2025-11-07
 */
@Getter
public enum MenuItemKey {

    /**
     * 数据看板
     */
    DASHBOARD("dashboard", "数据看板"),

    /**
     * 预约检查
     */
    RESERVE("reserve", "预约检查"),

    /**
     * 智能诊断
     */
    DIAGNOSIS("diagnosis", "智能诊断"),

    /**
     * 患者管理
     */
    PATIENT("patient", "患者管理"),

    /**
     * 用户管理
     */
    USER("user", "用户管理"),

    /**
     * 数据上传
     */
    UPLOAD("upload", "数据上传"),

    AIDIAGNOSIS("ai-diagnosis", "AI智诊"),

    /**
     * 密钥管理
     */
    ACTIVATION_KEY("activation-key", "密钥管理"),

    /**
     * 处方药管理
     */
    DRUGS("drugs", "处方药管理"),

    /**
     * 机构管理
     */
    ORGANIZATION_MANAGE("organization-manage", "机构管理");

    /**
     * 数据库存储值 & API返回值（英文 key）
     */
    @EnumValue
    @JsonValue
    private final String code;

    /**
     * 中文描述（用于日志、管理后台等）
     */
    private final String description;

    MenuItemKey(String code, String description) {
        this.code = code;
        this.description = description;
    }

    /**
     * 根据英文代码获取枚举
     *
     * @param code 英文代码（如 "dashboard", "reserve"）
     * @return MenuItemKey 枚举
     */
    public static MenuItemKey fromCode(String code) {
        if (code == null) {
            return null;
        }
        for (MenuItemKey key : MenuItemKey.values()) {
            if (key.getCode().equals(code)) {
                return key;
            }
        }
        throw new IllegalArgumentException("未知的菜单标识代码: " + code);
    }

    /**
     * 根据中文描述获取枚举
     *
     * @param description 中文描述
     * @return MenuItemKey 枚举
     */
    public static MenuItemKey fromDescription(String description) {
        if (description == null) {
            return null;
        }
        for (MenuItemKey key : MenuItemKey.values()) {
            if (key.getDescription().equals(description)) {
                return key;
            }
        }
        throw new IllegalArgumentException("未知的菜单标识描述: " + description);
    }
}
