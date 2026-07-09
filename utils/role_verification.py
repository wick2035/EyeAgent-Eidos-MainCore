"""
服务端角色校验模块

替代客户端提交的 role 字段，通过服务端逻辑验证用户角色。
验证失败时 fail-closed：降级为 patient。
"""
import re
import time
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# 缓存已验证的 doctor_id，避免重复校验
_verified_doctors: dict = {}  # {doctor_id: (is_valid, timestamp)}
CACHE_TTL = 300  # 5 分钟

UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',
    re.IGNORECASE,
)


def verify_role(
    role: str,
    patient_id: str,
    doctor_id: Optional[str] = None,
    allow_same_identity: bool = False,
) -> Tuple[str, bool]:
    """
    服务端角色校验。

    校验规则：
    1. 若 role != "doctor"，直接返回 "patient"
    2. 若 role == "doctor" 但未提供 doctor_id → 降级
    3. 若 doctor_id 格式不合法 → 降级
    4. 若 doctor_id == patient_id 且未显式允许 doctor-scoped 会话 → 降级（防止自我提权）
    5. 校验通过 → 返回 "doctor"

    验证失败时 fail-closed（降级为 patient）。

    Args:
        role: 客户端提交的角色
        patient_id: 患者 UUID
        doctor_id: 医生 UUID（医生角色必须提供）

    Returns:
        (verified_role, was_downgraded)
        - verified_role: "patient" 或 "doctor"
        - was_downgraded: 是否被降级
    """
    # 非医生角色直接返回 patient
    if role != "doctor":
        return ("patient", False)

    # 医生角色必须提供 doctor_id
    if not doctor_id:
        logger.warning(
            f"[RoleVerification] 角色声明为医生但未提供 doctor_id，"
            f"降级为 patient, patient_id={patient_id}"
        )
        return ("patient", True)

    # 检查缓存
    cache_key = f"{doctor_id}|same:{allow_same_identity}"
    cached = _verified_doctors.get(cache_key)
    if cached:
        is_valid, timestamp = cached
        if time.time() - timestamp < CACHE_TTL:
            if is_valid:
                return ("doctor", False)
            else:
                logger.warning(
                    f"[RoleVerification] 缓存命中: doctor_id={doctor_id} 无效，降级"
                )
                return ("patient", True)

    # 验证逻辑
    is_valid = _validate_doctor_id(doctor_id, patient_id, allow_same_identity)

    # 写入缓存
    _verified_doctors[cache_key] = (is_valid, time.time())

    if not is_valid:
        logger.warning(
            f"[RoleVerification] doctor_id 验证失败: {doctor_id}，降级为 patient"
        )
        return ("patient", True)

    return ("doctor", False)


def _validate_doctor_id(
    doctor_id: str,
    patient_id: str,
    allow_same_identity: bool = False,
) -> bool:
    """
    验证 doctor_id 的有效性。

    当前验证逻辑：
    1. UUID 格式校验
    2. doctor_id 不能等于 patient_id（防自我提权）

    TODO: 待后端实现 /agent/api/verify-doctor 接口后，
    增加对后端 API 的实际身份验证调用。
    """
    # UUID 格式校验
    if not UUID_PATTERN.match(doctor_id):
        return False

    # 防止 doctor_id == patient_id 的自我提权
    if doctor_id == patient_id and not allow_same_identity:
        logger.warning(
            f"[RoleVerification] doctor_id 与 patient_id 相同，疑似提权: {doctor_id}"
        )
        return False

    # TODO: 后端 API 验证
    # try:
    #     from infrastructure.api.backend_client import get_api_client
    #     client = get_api_client()
    #     result = client._request('GET', '/agent/api/verify-doctor',
    #                              params={'doctorId': doctor_id})
    #     return result.get('data', {}).get('isDoctor', False)
    # except Exception as e:
    #     logger.error(f"[RoleVerification] 后端验证异常: {e}")
    #     return False  # fail-closed

    return True


def clear_cache():
    """清理验证缓存（用于测试）"""
    global _verified_doctors
    _verified_doctors.clear()
