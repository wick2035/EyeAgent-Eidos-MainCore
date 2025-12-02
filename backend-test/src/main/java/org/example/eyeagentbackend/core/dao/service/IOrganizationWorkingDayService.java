package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.reserve.OrganizationWorkingDay;

import java.util.List;

/**
 * <p>
 * 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
public interface IOrganizationWorkingDayService extends IService<OrganizationWorkingDay> {

    boolean removeByOrganizationCode(String code);

    List<Byte> listWorkingDaysByConfigId(String configId);
}
