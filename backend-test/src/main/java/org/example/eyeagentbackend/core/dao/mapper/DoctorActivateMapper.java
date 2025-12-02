package org.example.eyeagentbackend.core.dao.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.SelectProvider;
import org.example.eyeagentbackend.core.dao.entity.activation.DoctorActivate;
import org.example.eyeagentbackend.core.dao.entity.rbac.Doctor;
import org.example.eyeagentbackend.core.dto.response.doctor.OrganizationDoctorResponse;
import org.example.eyeagentbackend.core.enums.DoctorActivateStatus;

import java.util.List;

/**
 * <p>
 * Mapper 接口
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-26
 */
public interface DoctorActivateMapper extends BaseMapper<DoctorActivate> {

    /**
     * 分页查询机构下的医生列表（包含激活状态）
     *
     * @param page             分页对象
     * @param organizationCode 机构码
     * @param searchKey        搜索关键词（可选，模糊查询姓名或手机号）
     * @param status           激活状态筛选（可选）
     * @return 分页结果
     */
    @SelectProvider(type = DoctorActivateSqlProvider.class, method = "getOrganizationDoctorPageSql")
    IPage<OrganizationDoctorResponse> getOrganizationDoctorPage(
            IPage<OrganizationDoctorResponse> page,
            @Param("organizationCode") String organizationCode,
            @Param("searchKey") String searchKey,
            @Param("status") DoctorActivateStatus status);

    @Select("select d.* from doctor d " +
            "join doctor_activate da on d.id=da.doctor_id " +
            "where da.organization_code=#{code}")
    List<Doctor> listDoctorByCode(@Param("code") String code);

    /**
     * SQL 提供者
     */
    class DoctorActivateSqlProvider {
        /**
         * 生成机构医生分页查询的动态 SQL
         */
        public String getOrganizationDoctorPageSql(
                @Param("organizationCode") String organizationCode,
                @Param("searchKey") String searchKey,
                @Param("status") DoctorActivateStatus status) {
            StringBuilder sql = new StringBuilder();
            sql.append("SELECT d.*, da.activate_status ");
            sql.append("FROM doctor d ");
            sql.append("JOIN doctor_activate da ON da.doctor_id = d.id ");
            sql.append("WHERE d.deleted = 0 ");
            sql.append("AND da.deleted = 0 ");
            sql.append("AND da.organization_code = #{organizationCode} ");

            // 动态添加关键词搜索条件
            if (searchKey != null && !searchKey.trim().isEmpty()) {
                sql.append("AND (");
                sql.append("d.name LIKE CONCAT('%', #{searchKey}, '%') ");
                sql.append("OR d.phone_number LIKE CONCAT('%', #{searchKey}, '%')");
                sql.append(") ");
            }

            // 动态添加激活状态筛选条件
            if (status != null) {
                sql.append("AND da.activate_status = #{status.value} ");
            }

            // 按创建时间降序排列
            sql.append("ORDER BY da.create_time DESC");

            return sql.toString();
        }
    }
}
