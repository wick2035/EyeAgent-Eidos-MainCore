package org.example.eyeagentbackend.core.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;

/**
 * 激活密钥状态枚举
 * 数据库存储：0=停用, 1=启用, 2=过期, 3=未激活
 * API返回：inactive, active, expired, unactivated
 *
 * @author qtcyy
 * @since 2025-11-16
 */
@Getter
public enum ActivationKeyStatus {

    /**
     * 停用
     */
    INACTIVE((byte) 0, "inactive", "停用"),

    /**
     * 启用
     */
    ACTIVE((byte) 1, "active", "启用"),

    /**
     * 过期
     */
    EXPIRED((byte) 2, "expired", "过期"),

    /**
     * 未激活（激活码未被使用）
     */
    UNACTIVATED((byte) 3, "unactivated", "未激活");

    /**
     * 数据库存储值（Byte类型）
     */
    @EnumValue
    private final Byte value;

    /**
     * 英文代码（用于API返回）
     */
    @JsonValue
    private final String code;

    /**
     * 中文描述（用于日志、管理后台等）
     */
    private final String description;

    ActivationKeyStatus(Byte value, String code, String description) {
        this.value = value;
        this.code = code;
        this.description = description;
    }

    /**
     * 根据 Byte 值获取枚举
     *
     * @param value Byte 值（0=停用, 1=启用, 2=过期, 3=未激活）
     * @return ActivationKeyStatus 枚举
     */
    public static ActivationKeyStatus fromValue(Byte value) {
        if (value == null) {
            return null;
        }
        for (ActivationKeyStatus status : ActivationKeyStatus.values()) {
            if (status.getValue().equals(value)) {
                return status;
            }
        }
        throw new IllegalArgumentException("未知的激活密钥状态值: " + value);
    }

    /**
     * 根据英文代码获取枚举
     *
     * @param code 英文代码（"inactive"、"active"、"expired" 或 "unactivated"）
     * @return ActivationKeyStatus 枚举
     */
    public static ActivationKeyStatus fromCode(String code) {
        if (code == null) {
            return null;
        }
        for (ActivationKeyStatus status : ActivationKeyStatus.values()) {
            if (status.getCode().equals(code)) {
                return status;
            }
        }
        throw new IllegalArgumentException("未知的激活密钥状态代码: " + code);
    }

    /**
     * 根据中文描述获取枚举
     *
     * @param description 中文描述（"停用"、"启用"、"过期" 或 "未激活"）
     * @return ActivationKeyStatus 枚举
     */
    public static ActivationKeyStatus fromDescription(String description) {
        if (description == null) {
            return null;
        }
        for (ActivationKeyStatus status : ActivationKeyStatus.values()) {
            if (status.getDescription().equals(description)) {
                return status;
            }
        }
        throw new IllegalArgumentException("未知的激活密钥状态描述: " + description);
    }

    /**
     * 判断是否为启用状态
     *
     * @return 是否为启用状态
     */
    public boolean isActive() {
        return this == ACTIVE;
    }

    /**
     * 判断是否为停用状态
     *
     * @return 是否为停用状态
     */
    public boolean isInactive() {
        return this == INACTIVE;
    }

    /**
     * 判断是否为过期状态
     *
     * @return 是否为过期状态
     */
    public boolean isExpired() {
        return this == EXPIRED;
    }

    /**
     * 判断是否为未激活状态
     *
     * @return 是否为未激活状态
     */
    public boolean isUnactivated() {
        return this == UNACTIVATED;
    }
}
