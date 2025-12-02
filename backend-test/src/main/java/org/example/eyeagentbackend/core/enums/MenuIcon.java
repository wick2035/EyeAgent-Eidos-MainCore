package org.example.eyeagentbackend.core.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;

/**
 * 菜单图标枚举
 * 数据库存储：英文 key（如 dashboard, reserve）
 * API返回：英文 key
 *
 * @author qtcyy
 * @since 2025-11-07
 */
@Getter
public enum MenuIcon {

    /**
     * 数据看板图标
     */
    DASHBOARD("dashboard", "数据看板图标"),

    /**
     * 预约检查图标
     */
    RESERVE("reserve", "预约检查图标"),

    /**
     * 智能诊断图标
     */
    DIAGNOSIS("diagnosis", "智能诊断图标"),

    /**
     * 患者管理图标
     */
    PATIENT("patient", "患者管理图标"),

    /**
     * 联系人图标
     */
    CONTACT("contact", "联系人图标"),

    /**
     * 数据上传图标
     */
    UPLOAD("upload", "数据上传图标"),

    CHATBOT("chatbot", "AI智能诊断图标"),

    /**
     * 密钥管理图标
     */
    KEY("key", "密钥管理图标"),

    /**
     * 药瓶图标（处方药管理）
     */
    PILL_BOTTLE("pill-bottle", "药瓶图标"),

    /**
     * 用户组图标（机构管理）
     */
    USERS("users", "用户组图标");

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

    MenuIcon(String code, String description) {
        this.code = code;
        this.description = description;
    }

    /**
     * 根据英文代码获取枚举
     *
     * @param code 英文代码（如 "dashboard", "reserve"）
     * @return MenuIcon 枚举
     */
    public static MenuIcon fromCode(String code) {
        if (code == null) {
            return null;
        }
        for (MenuIcon icon : MenuIcon.values()) {
            if (icon.getCode().equals(code)) {
                return icon;
            }
        }
        throw new IllegalArgumentException("未知的菜单图标代码: " + code);
    }

    /**
     * 根据中文描述获取枚举
     *
     * @param description 中文描述
     * @return MenuIcon 枚举
     */
    public static MenuIcon fromDescription(String description) {
        if (description == null) {
            return null;
        }
        for (MenuIcon icon : MenuIcon.values()) {
            if (icon.getDescription().equals(description)) {
                return icon;
            }
        }
        throw new IllegalArgumentException("未知的菜单图标描述: " + description);
    }
}
