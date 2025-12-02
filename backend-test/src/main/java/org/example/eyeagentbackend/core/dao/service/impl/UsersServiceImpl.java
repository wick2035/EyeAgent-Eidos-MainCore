package org.example.eyeagentbackend.core.dao.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.example.eyeagentbackend.core.dao.entity.rbac.Users;
import org.example.eyeagentbackend.core.dao.mapper.UsersMapper;
import org.example.eyeagentbackend.core.dao.service.IUsersService;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
@Service
public class UsersServiceImpl extends ServiceImpl<UsersMapper, Users> implements IUsersService {
    @Override
    public Users getUserByUsername(String username) {
        LambdaQueryWrapper<Users> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Users::getUsername, username).last("limit 1");
        return getOne(queryWrapper);
    }

    @Override
    public Users getUserByEmail(String email) {
        LambdaQueryWrapper<Users> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Users::getEmail, email).last("limit 1");
        return getOne(queryWrapper);
    }

    @Override
    public Users getUserByPhone(String phone) {
        LambdaQueryWrapper<Users> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(Users::getPhone, phone).last("limit 1");
        return getOne(queryWrapper);
    }

    @Override
    public List<String> getUsernameByIdsOrdered(List<String> ids) {
        // 参数校验：如果输入为空，返回空列表
        if (ids == null || ids.isEmpty()) {
            return Collections.emptyList();
        }

        // 查询用户数据并构建 ID -> Username 映射
        List<Users> users = listByIds(ids);
        Map<String, String> idToUsername = users.stream()
                .collect(Collectors.toMap(Users::getId, Users::getUsername));

        // 按输入顺序返回用户名，不存在的 ID 对应位置返回 null
        return ids.stream()
                .map(idToUsername::get)
                .collect(Collectors.toList());
    }
}
