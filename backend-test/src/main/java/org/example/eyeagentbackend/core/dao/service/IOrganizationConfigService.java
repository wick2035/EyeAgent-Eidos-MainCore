package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.reserve.OrganizationConfig;

/**
 * <p>
 * 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-29
 */
public interface IOrganizationConfigService extends IService<OrganizationConfig> {

    OrganizationConfig getByOrganizationCode(String code);
}
