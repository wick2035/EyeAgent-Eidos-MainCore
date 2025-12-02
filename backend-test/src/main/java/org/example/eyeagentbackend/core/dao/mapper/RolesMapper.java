package org.example.eyeagentbackend.core.dao.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.example.eyeagentbackend.core.dao.entity.rbac.Roles;

import java.util.List;

/**
 * <p>
 * Mapper 接口
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
public interface RolesMapper extends BaseMapper<Roles> {
    @Select("select r.role_name from roles r " +
            "join user_role ur on ur.role_id=r.id " +
            "where ur.user_id=#{id} " +
            "and r.deleted=0 " +
            "and ur.deleted=0")
    List<String> getRoleListByUserId(@Param("id") String userId);
}
