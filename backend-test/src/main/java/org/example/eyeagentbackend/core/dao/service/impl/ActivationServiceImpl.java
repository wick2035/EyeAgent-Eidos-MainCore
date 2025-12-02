package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.activation.Activation;
import org.example.eyeagentbackend.core.dao.mapper.ActivationMapper;
import org.example.eyeagentbackend.core.dao.service.IActivationService;
import org.example.eyeagentbackend.core.enums.ActivationKeyStatus;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-16
 */
@Service
public class ActivationServiceImpl extends ServiceImpl<ActivationMapper, Activation> implements IActivationService {
    @Override
    public IPage<Activation> listPage(Page<Activation> page, ActivationKeyStatus status, LocalDateTime startTime, LocalDateTime endTime) {
        LambdaQueryWrapper<Activation> queryWrapper = new LambdaQueryWrapper<>();

        // 条件查询：status 不为 null 时添加筛选条件
        if (status != null) {
            queryWrapper.eq(Activation::getKeyStatus, status);
        }

        // 条件查询：时间范围筛选
        if (startTime != null) {
            queryWrapper.ge(Activation::getCreateTime, startTime);  // createTime >= startTime
        }
        if (endTime != null) {
            queryWrapper.le(Activation::getCreateTime, endTime);    // createTime <= endTime
        }

        queryWrapper.orderByDesc(Activation::getCreateTime);

        return page(page, queryWrapper);
    }

    @Override
    public List<Activation> getByUserId(String userId) {
        LambdaQueryWrapper<Activation> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Activation::getUserId, userId);

        return list(queryWrapper);
    }

    @Override
    public Activation getByOrganizationCode(String code) {
        LambdaQueryWrapper<Activation> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Activation::getOrganizationCode, code);

        return getOne(queryWrapper);
    }

    @Override
    public List<Activation> listByOrganizationCode(String code) {
        LambdaQueryWrapper<Activation> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Activation::getOrganizationCode, code);
        queryWrapper.orderByDesc(Activation::getCreateTime);

        return list(queryWrapper);
    }

    @Override
    public Activation getByHospital(String hospital) {
        LambdaQueryWrapper<Activation> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Activation::getOrganizationName, hospital);

        return getOne(queryWrapper);
    }

    @Override
    public List<Activation> listByHospitalKey(String hospitalKey, int limit) {
        LambdaQueryWrapper<Activation> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.like(Activation::getOrganizationName, hospitalKey)
                .last("limit " + limit);

        return list(queryWrapper);
    }
}
