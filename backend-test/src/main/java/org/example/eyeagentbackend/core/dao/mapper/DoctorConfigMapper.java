package org.example.eyeagentbackend.core.dao.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.example.eyeagentbackend.core.dao.entity.reserve.DoctorConfig;

/**
 * <p>
 * 医生预约配置表 Mapper 接口
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
@Mapper
public interface DoctorConfigMapper extends BaseMapper<DoctorConfig> {

}
