package org.example.eyeagentbackend.core.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;

import java.util.Arrays;

/**
 * 用户状态枚举
 *
 * @author chengyiyang
 */
@Getter
public enum UserStatus {
    /**
     * 正常状态
     */
    NORMAL((byte) 0, "正常"),

    /**
     * 锁定状态
     */
    LOCKED((byte) 1, "锁定");

    /**
     * 状态值（存储到数据库的数值）
     */
    @EnumValue
    private final Byte value;

    /**
     * 状态码（返回给前端的小写枚举名称）
     */
    @JsonValue
    private final String code;

    /**
     * 状态描述（中文说明）
     */
    private final String description;

    /**
     * 构造函数
     *
     * @param value       状态值
     * @param description 状态描述
     */
    UserStatus(Byte value, String description) {
        this.value = value;
        this.code = this.name().toLowerCase();
        this.description = description;
    }

    /**
     * 根据状态值（数据库值）获取枚举
     *
     * @param value 状态值
     * @return 对应的枚举值，如果不存在则返回 null
     */
    public static UserStatus getByValue(Byte value) {
        if (value == null) {
            return null;
        }
        return Arrays.stream(values())
                .filter(status -> status.getValue().equals(value))
                .findFirst()
                .orElse(null);
    }

    /**
     * 根据状态码（小写枚举名）获取枚举
     *
     * @param code 状态码（如 "normal", "locked"）
     * @return 对应的枚举值，如果不存在则返回 null
     */
    public static UserStatus getByCode(String code) {
        if (code == null || code.isEmpty()) {
            return null;
        }
        return Arrays.stream(values())
                .filter(status -> status.getCode().equals(code))
                .findFirst()
                .orElse(null);
    }

    /**
     * 根据描述获取枚举值
     *
     * @param description 状态描述
     * @return 对应的枚举值，如果不存在则返回 null
     */
    public static UserStatus getByDescription(String description) {
        if (description == null || description.isEmpty()) {
            return null;
        }
        return Arrays.stream(values())
                .filter(status -> status.getDescription().equals(description))
                .findFirst()
                .orElse(null);
    }

    /**
     * 判断状态值是否有效
     *
     * @param value 状态值
     * @return 是否有效
     */
    public static boolean isValidValue(Byte value) {
        return getByValue(value) != null;
    }

    /**
     * 判断状态码是否有效
     *
     * @param code 状态码
     * @return 是否有效
     */
    public static boolean isValidCode(String code) {
        return getByCode(code) != null;
    }

    /**
     * 判断是否为正常状态
     *
     * @return 是否为正常状态
     */
    public boolean isNormal() {
        return this == NORMAL;
    }

    /**
     * 判断是否为锁定状态
     *
     * @return 是否为锁定状态
     */
    public boolean isLocked() {
        return this == LOCKED;
    }
}
