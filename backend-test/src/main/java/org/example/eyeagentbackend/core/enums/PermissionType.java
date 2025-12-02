package org.example.eyeagentbackend.core.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;

/**
 * 权限类型枚举
 * 数据库存储：权限标识字符串（如 "user:view", "user:create"）
 * API返回：相同的权限标识字符串
 *
 * @author chengyiyang
 * @since 2025-11-09
 */
@Getter
public enum PermissionType {

    // ========== 用户管理权限 ==========
    /**
     * 查看用户列表
     */
    USER_VIEW("user:view", "查看用户列表"),

    /**
     * 查看用户详情
     */
    USER_DETAIL("user:detail", "查看用户详情"),

    /**
     * 创建新用户
     */
    USER_CREATE("user:create", "创建新用户"),

    /**
     * 更新用户信息
     */
    USER_UPDATE("user:update", "更新用户信息"),

    /**
     * 删除用户
     */
    USER_DELETE("user:delete", "删除用户"),

    /**
     * 重置用户密码
     */
    USER_RESET_PASSWORD("user:reset-password", "重置用户密码"),

    /**
     * 查看自己的信息
     */
    USER_SELF_VIEW("user:self:view", "查看自己的信息"),

    /**
     * 修改自己的信息
     */
    USER_SELF_UPDATE("user:self:update", "修改自己的信息"),

    // ========== 角色管理权限 ==========
    /**
     * 查看角色列表
     */
    ROLE_VIEW("role:view", "查看角色列表"),

    /**
     * 管理角色（增删改）
     */
    ROLE_MANAGE("role:manage", "管理角色（增删改）"),

    /**
     * 分配角色给用户
     */
    ROLE_ASSIGN("role:assign", "分配角色给用户"),

    // ========== 权限管理权限 ==========
    /**
     * 查看权限列表
     */
    PERMISSION_VIEW("permission:view", "查看权限列表"),

    /**
     * 管理权限
     */
    PERMISSION_MANAGE("permission:manage", "管理权限"),

    /**
     * 分配权限给角色
     */
    PERMISSION_ASSIGN("permission:assign", "分配权限给角色"),

    // ========== 患者管理权限 ==========
    /**
     * 查看患者
     */
    PATIENT_VIEW("patient:view", "查看患者"),

    /**
     * 创建患者
     */
    PATIENT_CREATE("patient:create", "创建患者"),

    /**
     * 更新患者信息
     */
    PATIENT_UPDATE("patient:update", "更新患者"),

    /**
     * 删除患者
     */
    PATIENT_DELETE("patient:delete", "删除患者"),

    // ========== 通知管理权限 ==========
    /**
     * 创建系统公告
     */
    NOTIFICATION_CREATE("notification:create", "创建系统公告"),

    /**
     * 修改系统公告
     */
    NOTIFICATION_UPDATE("notification:update", "修改系统公告"),

    /**
     * 删除系统公告
     */
    NOTIFICATION_DELETE("notification:delete", "删除系统公告"),

    // ========== 激活码管理权限 ==========
    /**
     * 查看激活码
     */
    ACTIVATION_VIEW("activation:view", "查看激活码"),

    /**
     * 创建激活码
     */
    ACTIVATION_CREATE("activation:create", "创建激活码"),

    /**
     * 更新激活码
     */
    ACTIVATION_UPDATE("activation:update", "更新激活码"),

    /**
     * 删除激活码
     */
    ACTIVATION_DELETE("activation:delete", "删除激活码"),

    // ========== 药品管理权限 ==========
    /**
     * 查看药品列表
     */
    DRUG_VIEW("drug:view", "查看药品列表"),

    /**
     * 创建药品
     */
    DRUG_CREATE("drug:create", "创建药品"),

    /**
     * 修改药品信息
     */
    DRUG_UPDATE("drug:update", "修改药品信息"),

    /**
     * 删除药品
     */
    DRUG_DELETE("drug:delete", "删除药品");

    /**
     * 权限标识（数据库存储值 & API返回值）
     * 格式：模块:操作（如 "user:view", "user:create"）
     */
    @EnumValue
    @JsonValue
    private final String code;

    /**
     * 权限中文描述
     */
    private final String description;

    /**
     * 构造函数
     *
     * @param code        权限标识
     * @param description 权限中文描述
     */
    PermissionType(String code, String description) {
        this.code = code;
        this.description = description;
    }

    /**
     * 根据权限标识获取枚举
     *
     * @param code 权限标识（如 "user:view", "user:create"）
     * @return PermissionType 枚举，如果不存在则抛出异常
     */
    public static PermissionType fromCode(String code) {
        if (code == null || code.isEmpty()) {
            throw new IllegalArgumentException("权限标识不能为空");
        }
        for (PermissionType permission : PermissionType.values()) {
            if (permission.getCode().equals(code)) {
                return permission;
            }
        }
        throw new IllegalArgumentException("未知的权限标识: " + code);
    }

    /**
     * 根据权限标识获取枚举（安全版本，不抛异常）
     *
     * @param code 权限标识
     * @return PermissionType 枚举，如果不存在则返回 null
     */
    public static PermissionType fromCodeSafely(String code) {
        if (code == null || code.isEmpty()) {
            return null;
        }
        for (PermissionType permission : PermissionType.values()) {
            if (permission.getCode().equals(code)) {
                return permission;
            }
        }
        return null;
    }

    /**
     * 根据中文描述获取枚举
     *
     * @param description 中文描述
     * @return PermissionType 枚举，如果不存在则抛出异常
     */
    public static PermissionType fromDescription(String description) {
        if (description == null || description.isEmpty()) {
            throw new IllegalArgumentException("权限描述不能为空");
        }
        for (PermissionType permission : PermissionType.values()) {
            if (permission.getDescription().equals(description)) {
                return permission;
            }
        }
        throw new IllegalArgumentException("未知的权限描述: " + description);
    }

    /**
     * 判断权限标识是否有效
     *
     * @param code 权限标识
     * @return 是否有效
     */
    public static boolean isValid(String code) {
        return fromCodeSafely(code) != null;
    }

    /**
     * 判断是否为用户管理权限
     *
     * @return 是否为用户管理权限
     */
    public boolean isUserPermission() {
        return this.code.startsWith("user:");
    }

    /**
     * 判断是否为角色管理权限
     *
     * @return 是否为角色管理权限
     */
    public boolean isRolePermission() {
        return this.code.startsWith("role:");
    }

    /**
     * 判断是否为权限管理权限
     *
     * @return 是否为权限管理权限
     */
    public boolean isPermissionManagement() {
        return this.code.startsWith("permission:");
    }

    /**
     * 判断是否为患者管理权限
     *
     * @return 是否为患者管理权限
     */
    public boolean isPatientPermission() {
        return this.code.startsWith("patient:");
    }

    /**
     * 判断是否为通知管理权限
     *
     * @return 是否为通知管理权限
     */
    public boolean isNotificationPermission() {
        return this.code.startsWith("notification:");
    }

    /**
     * 判断是否为激活码管理权限
     *
     * @return 是否为激活码管理权限
     */
    public boolean isActivationPermission() {
        return this.code.startsWith("activation:");
    }

    /**
     * 判断是否为药品管理权限
     *
     * @return 是否为药品管理权限
     */
    public boolean isDrugPermission() {
        return this.code.startsWith("drug:");
    }

    /**
     * 获取权限所属模块
     *
     * @return 模块名称（如 "user", "role", "permission", "patient", "notification",
     *         "drug"）
     */
    public String getModule() {
        int colonIndex = this.code.indexOf(':');
        if (colonIndex > 0) {
            return this.code.substring(0, colonIndex);
        }
        return "";
    }

    /**
     * 获取权限操作
     *
     * @return 操作名称（如 "view", "create", "update"）
     */
    public String getAction() {
        int colonIndex = this.code.indexOf(':');
        if (colonIndex > 0 && colonIndex < this.code.length() - 1) {
            return this.code.substring(colonIndex + 1);
        }
        return "";
    }
}
