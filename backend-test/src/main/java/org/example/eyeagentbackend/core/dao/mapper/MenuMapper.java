package org.example.eyeagentbackend.core.dao.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.example.eyeagentbackend.core.dao.entity.rbac.Menu;

import java.util.List;

/**
 * <p>
 * Mapper 接口
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-07
 */
public interface MenuMapper extends BaseMapper<Menu> {
    @Select("select m.* from menu m " +
            "join role_menu rm on rm.menu_id=m.id " +
            "join roles r on r.id=rm.role_id " +
            "where r.role_name=#{role} " +
            "and m.deleted=0 " +
            "and rm.deleted=0 " +
            "and r.deleted=0 " +
            "and m.menu_status=1 " +
            "order by m.sort_order")
    List<Menu> getMenusByRole(@Param("role") String role);
}
