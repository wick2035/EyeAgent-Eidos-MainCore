package org.example.eyeagentbackend.core.exceptions;

import lombok.Getter;

/**
 * 业务异常基类
 *
 * <p>用于封装业务逻辑层抛出的异常信息。</p>
 *
 * <p>使用示例：
 * <pre>
 * {@code
 * // 抛出带错误码的业务异常
 * throw new BusinessException(ErrorCode.USER_NOT_FOUND, "用户不存在");
 *
 * // 抛出仅带消息的业务异常
 * throw new BusinessException("操作失败");
 *
 * // 抛出带原因的业务异常
 * throw new BusinessException("数据库连接失败", cause);
 * }
 * </pre>
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-02
 */
@Getter
public class BusinessException extends RuntimeException {

    /**
     * 错误码
     * <p>可用于前端识别具体的错误类型</p>
     */
    private String errorCode;

    /**
     * 默认构造函数
     */
    public BusinessException() {
        super();
    }

    /**
     * 构造函数 - 仅消息
     *
     * @param message 错误消息
     */
    public BusinessException(String message) {
        super(message);
    }

    /**
     * 构造函数 - 消息和原因
     *
     * @param message 错误消息
     * @param cause   原始异常
     */
    public BusinessException(String message, Throwable cause) {
        super(message, cause);
    }

    /**
     * 构造函数 - 错误码和消息
     *
     * @param errorCode 错误码
     * @param message   错误消息
     */
    public BusinessException(String errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }

    /**
     * 构造函数 - 错误码、消息和原因
     *
     * @param errorCode 错误码
     * @param message   错误消息
     * @param cause     原始异常
     */
    public BusinessException(String errorCode, String message, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
    }

    /**
     * 构造函数 - 仅原因
     *
     * @param cause 原始异常
     */
    public BusinessException(Throwable cause) {
        super(cause);
    }

    /**
     * 获取完整的错误信息
     *
     * @return 格式化的错误信息（包含错误码）
     */
    public String getFullMessage() {
        if (errorCode != null && !errorCode.isEmpty()) {
            return String.format("[%s] %s", errorCode, getMessage());
        }
        return getMessage();
    }

    @Override
    public String toString() {
        if (errorCode != null && !errorCode.isEmpty()) {
            return String.format("%s: [%s] %s", getClass().getName(), errorCode, getMessage());
        }
        return super.toString();
    }
}
