package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.activation.Activation;
import org.example.eyeagentbackend.core.enums.ActivationKeyStatus;

import java.time.LocalDateTime;
import java.util.List;

/**
 * <p>
 * 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-16
 */
public interface IActivationService extends IService<Activation> {

    IPage<Activation> listPage(Page<Activation> page, ActivationKeyStatus status, LocalDateTime startTime, LocalDateTime endTime);

    List<Activation> getByUserId(String userId);

    Activation getByOrganizationCode(String code);

    /**
     * 根据机构码获取所有激活记录
     *
     * @param code 机构码
     * @return 激活记录列表
     */
    List<Activation> listByOrganizationCode(String code);

    Activation getByHospital(String hospital);

    List<Activation> listByHospitalKey(String hospitalKey, int limit);
}
