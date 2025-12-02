package org.example.eyeagentbackend.core.dao.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.SelectProvider;
import org.example.eyeagentbackend.core.dao.entity.rbac.Users;
import org.example.eyeagentbackend.core.dto.response.user.GetUserResponse;

/**
 * <p>
 * 用户 Mapper 接口
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
public interface UsersMapper extends BaseMapper<Users> {

    /**
     * 分页查询用户列表（包含角色信息）
     *
     * @param page 分页对象，MyBatis-Plus 自动处理分页
     * @param keyword 搜索关键词（可选），用于模糊查询用户名、姓名、手机号、邮箱
     * @return 分页结果，包含用户信息和角色名称
     */
    @SelectProvider(type = UserSqlProvider.class, method = "getUserPageSql")
    IPage<GetUserResponse> getUserPage(IPage<GetUserResponse> page, @Param("keyword") String keyword);

    /**
     * 用户查询 SQL 提供者
     * <p>
     * 用于生成动态 SQL，支持可选的关键词搜索
     * </p>
     */
    class UserSqlProvider {
        /**
         * 生成用户分页查询的动态 SQL
         *
         * @param keyword 搜索关键词
         * @return SQL 字符串
         */
        public String getUserPageSql(@Param("keyword") String keyword) {
            StringBuilder sql = new StringBuilder();
            sql.append("SELECT u.*, r.role_name ");
            sql.append("FROM users u ");
            sql.append("JOIN user_role ur ON ur.user_id = u.id ");
            sql.append("JOIN roles r ON r.id = ur.role_id ");
            sql.append("WHERE u.deleted = 0 ");
            sql.append("AND ur.deleted = 0 ");
            sql.append("AND r.deleted = 0 ");

            // 动态添加关键词搜索条件
            if (keyword != null && !keyword.trim().isEmpty()) {
                sql.append("AND (");
                sql.append("u.username LIKE CONCAT('%', #{keyword}, '%') ");
                sql.append("OR u.uname LIKE CONCAT('%', #{keyword}, '%') ");
                sql.append("OR u.phone LIKE CONCAT('%', #{keyword}, '%') ");
                sql.append("OR u.email LIKE CONCAT('%', #{keyword}, '%')");
                sql.append(") ");
            }

            // 按创建时间降序排列
            sql.append("ORDER BY u.create_time DESC");

            return sql.toString();
        }
    }
}
