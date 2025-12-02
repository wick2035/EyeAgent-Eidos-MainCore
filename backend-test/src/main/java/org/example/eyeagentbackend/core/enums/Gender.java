package org.example.eyeagentbackend.core.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;

/**
 * 性别枚举
 * 数据库存储：true=男性, false=女性
 * API返回：male, female
 *
 * @author qtcyy
 * @since 2025-11-04
 */
@Getter
public enum Gender {

    /**
     * 男性
     */
    MALE(true, "male", "男"),

    /**
     * 女性
     */
    FEMALE(false, "female", "女");

    /**
     * 数据库存储值（Boolean类型）
     */
    @EnumValue
    private final Boolean value;

    /**
     * 英文代码（用于API返回）
     */
    @JsonValue
    private final String code;

    /**
     * 中文描述（用于日志、管理后台等）
     */
    private final String description;

    Gender(Boolean value, String code, String description) {
        this.value = value;
        this.code = code;
        this.description = description;
    }

    /**
     * 根据 Boolean 值获取枚举
     * @param value Boolean 值（true=男, false=女）
     * @return Gender 枚举
     */
    public static Gender fromValue(Boolean value) {
        if (value == null) {
            return null;
        }
        for (Gender gender : Gender.values()) {
            if (gender.getValue().equals(value)) {
                return gender;
            }
        }
        throw new IllegalArgumentException("未知的性别值: " + value);
    }

    /**
     * 根据英文代码获取枚举
     * @param code 英文代码（"male" 或 "female"）
     * @return Gender 枚举
     */
    public static Gender fromCode(String code) {
        if (code == null) {
            return null;
        }
        for (Gender gender : Gender.values()) {
            if (gender.getCode().equals(code)) {
                return gender;
            }
        }
        throw new IllegalArgumentException("未知的性别代码: " + code);
    }

    /**
     * 根据中文描述获取枚举
     * @param description 中文描述（"男" 或 "女"）
     * @return Gender 枚举
     */
    public static Gender fromDescription(String description) {
        if (description == null) {
            return null;
        }
        for (Gender gender : Gender.values()) {
            if (gender.getDescription().equals(description)) {
                return gender;
            }
        }
        throw new IllegalArgumentException("未知的性别描述: " + description);
    }
}
