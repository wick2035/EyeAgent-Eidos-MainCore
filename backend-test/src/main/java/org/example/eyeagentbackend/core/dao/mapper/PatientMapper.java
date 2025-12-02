package org.example.eyeagentbackend.core.dao.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.example.eyeagentbackend.core.dao.entity.patient.Patient;

/**
 * <p>
 * 患者信息 Mapper 接口
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-06
 */
@Mapper
public interface PatientMapper extends BaseMapper<Patient> {

}
