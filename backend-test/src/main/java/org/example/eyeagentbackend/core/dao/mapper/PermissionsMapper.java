package org.example.eyeagentbackend.core.dao.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.example.eyeagentbackend.core.dao.entity.rbac.Permissions;

import java.util.List;

/**
 * <p>
 * Mapper 接口
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
public interface PermissionsMapper extends BaseMapper<Permissions> {
    @Select("select p.permission_name from permissions p " +
            "join role_permission rp on rp.permission_id=p.id " +
            "join user_role ur on ur.role_id = rp.role_id " +
            "where ur.user_id=#{id} " +
            "and p.deleted=0 " +
            "and rp.deleted=0 " +
            "and ur.deleted=0")
    List<String> getPermissionListByUserId(@Param("id") String id);

    @Select("select p.* from permissions p " +
            "join role_permission rp on rp.permission_id=p.id " +
            "where rp.role_id=#{id}")
    List<Permissions> getPermissionListByRoleId(@Param("id") String id);
}
