package org.example.eyeagentbackend.core.dao.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.example.eyeagentbackend.core.dao.entity.rbac.Users;

import java.util.List;

/**
 * <p>
 * 服务类
 * </p>
 *
 * @author qtcyy
 * @since 2025-11-01
 */
public interface IUsersService extends IService<Users> {

    Users getUserByUsername(String username);

    Users getUserByEmail(String email);

    Users getUserByPhone(String phone);

    List<String> getUsernameByIdsOrdered(List<String> ids);
}
