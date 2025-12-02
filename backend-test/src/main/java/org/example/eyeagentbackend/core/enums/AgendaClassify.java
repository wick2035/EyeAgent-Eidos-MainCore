package org.example.eyeagentbackend.core.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;

/**
 * 日程分类枚举
 * 数据库存储：0=普通日程, 1=手术日程
 * API返回：normal, operation
 *
 * @author qtcyy
 * @since 2025-11-04
 */
@Getter
public enum AgendaClassify {

    /**
     * 普通日程
     */
    NORMAL((byte) 0, "normal", "普通"),

    /**
     * 手术日程
     */
    OPERATION((byte) 1, "operation", "手术");

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

    AgendaClassify(Byte value, String code, String description) {
        this.value = value;
        this.code = code;
        this.description = description;
    }

    /**
     * 根据 Byte 值获取枚举
     * @param value Byte 值（0=普通, 1=手术）
     * @return AgendaClassify 枚举
     */
    public static AgendaClassify fromValue(Byte value) {
        if (value == null) {
            return null;
        }
        for (AgendaClassify classify : AgendaClassify.values()) {
            if (classify.getValue().equals(value)) {
                return classify;
            }
        }
        throw new IllegalArgumentException("未知的日程分类值: " + value);
    }

    /**
     * 根据英文代码获取枚举
     * @param code 英文代码（"normal" 或 "operation"）
     * @return AgendaClassify 枚举
     */
    public static AgendaClassify fromCode(String code) {
        if (code == null) {
            return null;
        }
        for (AgendaClassify classify : AgendaClassify.values()) {
            if (classify.getCode().equals(code)) {
                return classify;
            }
        }
        throw new IllegalArgumentException("未知的日程分类代码: " + code);
    }

    /**
     * 根据中文描述获取枚举
     * @param description 中文描述（"普通" 或 "手术"）
     * @return AgendaClassify 枚举
     */
    public static AgendaClassify fromDescription(String description) {
        if (description == null) {
            return null;
        }
        for (AgendaClassify classify : AgendaClassify.values()) {
            if (classify.getDescription().equals(description)) {
                return classify;
            }
        }
        throw new IllegalArgumentException("未知的日程分类描述: " + description);
    }
}
