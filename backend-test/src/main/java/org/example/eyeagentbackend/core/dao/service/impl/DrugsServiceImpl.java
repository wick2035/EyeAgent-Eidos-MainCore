package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.hospital.Drugs;
import org.example.eyeagentbackend.core.dao.mapper.DrugsMapper;
import org.example.eyeagentbackend.core.dao.service.IDrugsService;
import org.springframework.stereotype.Service;

/**
 * <p>
 * 眼科药品管理表 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-20
 */
@Service
public class DrugsServiceImpl extends ServiceImpl<DrugsMapper, Drugs> implements IDrugsService {

}
