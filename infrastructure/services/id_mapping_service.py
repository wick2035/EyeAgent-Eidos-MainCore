"""
ID映射服务模块
负责处理患者数字ID到UUID的映射

Created: 2025-12-02
Author: Claude Code
"""

import re
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)


class IDMappingService:
    """
    ID映射服务

    功能：
    1. 兼容模式：如果输入已经是UUID格式，直接返回
    2. 映射模式：如果输入是数字/其他格式，查找对应的UUID
    3. 缓存机制：内存缓存映射关系，TTL 60分钟
    4. Fallback：缓存未命中时实时查询
    """

    # UUID格式正则表达式（支持带连字符和不带连字符）
    UUID_PATTERN = re.compile(
        r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',
        re.IGNORECASE
    )

    def __init__(self):
        """初始化ID映射服务"""
        # 映射缓存：数字ID -> UUID
        self._numeric_to_uuid: Dict[int, str] = {}
        # 反向映射：UUID -> 数字ID（如果需要）
        self._uuid_to_numeric: Dict[str, int] = {}
        # 最后刷新时间
        self._last_refresh: Optional[datetime] = None
        # 缓存TTL
        self._ttl = timedelta(minutes=60)
        # 线程锁
        self._lock = Lock()

        logger.info("[IDMapping] ID映射服务初始化完成")

    def is_uuid(self, value: str) -> bool:
        """
        判断字符串是否为UUID格式

        Args:
            value: 待判断的字符串

        Returns:
            是否为UUID格式
        """
        return bool(self.UUID_PATTERN.match(value))

    def get_uuid(self, patient_id: str | int) -> Optional[str]:
        """
        获取患者UUID

        策略：
        1. 如果输入已经是UUID格式字符串，直接返回
        2. 如果输入是数字或其他格式，尝试从缓存查找映射
        3. 缓存未命中，尝试实时查询
        4. 都失败，返回None

        Args:
            patient_id: 患者ID（可以是UUID字符串、数字ID等）

        Returns:
            患者UUID，如果找不到返回None
        """
        # 转换为字符串
        patient_id_str = str(patient_id).strip()

        # 策略1：已经是UUID格式，直接返回
        if self.is_uuid(patient_id_str):
            logger.debug(f"[IDMapping] 输入已经是UUID格式: {patient_id_str}")
            return patient_id_str

        # 策略2：尝试作为数字ID处理
        try:
            numeric_id = int(patient_id_str)
        except ValueError:
            # 不是数字也不是UUID，无法处理
            logger.warning(f"[IDMapping] 无法识别的ID格式: {patient_id_str}")
            return None

        # 检查缓存
        with self._lock:
            # 检查缓存是否过期
            if self._is_cache_expired():
                logger.info("[IDMapping] 缓存已过期，需要刷新")
                self.refresh_mappings()

            # 从缓存查找
            uuid = self._numeric_to_uuid.get(numeric_id)
            if uuid:
                logger.debug(f"[IDMapping] 缓存命中: {numeric_id} → {uuid}")
                return uuid

        # 策略3：缓存未命中，尝试实时查询
        logger.warning(f"[IDMapping] 缓存未命中: {numeric_id}，尝试实时查询")
        uuid = self._query_uuid_by_numeric_id(numeric_id)

        if uuid:
            # 更新缓存
            with self._lock:
                self._numeric_to_uuid[numeric_id] = uuid
                self._uuid_to_numeric[uuid] = numeric_id
            logger.info(f"[IDMapping] 实时查询成功并缓存: {numeric_id} → {uuid}")
            return uuid

        # 都失败了
        logger.error(f"[IDMapping] 无法找到数字ID {numeric_id} 对应的UUID")
        return None

    def get_numeric_id(self, uuid: str) -> Optional[int]:
        """
        UUID反查数字ID（如果需要）

        Args:
            uuid: 患者UUID

        Returns:
            数字ID，如果找不到返回None
        """
        with self._lock:
            return self._uuid_to_numeric.get(uuid)

    def refresh_mappings(self):
        """
        从后端刷新映射缓存

        调用Java后端 /agent/api/get-all-patient 获取所有患者
        然后建立ID映射关系

        注意：目前Java后端已经使用UUID作为主键，所以映射表可能为空
        这个方法主要用于兼容性和未来扩展
        """
        try:
            from infrastructure.api.backend_client import get_api_client

            logger.info("[IDMapping] 开始刷新ID映射缓存")

            client = get_api_client()
            patients = client.get_all_patients()

            new_mappings = {}
            new_reverse_mappings = {}

            for patient in patients:
                patient_id = patient.get("id")
                if not patient_id:
                    continue

                # 如果患者有额外的数字ID字段，建立映射
                # 注意：当前Java后端只有UUID格式的id字段
                # 这里预留扩展：如果未来有numeric_id或patient_number字段
                numeric_id_field = patient.get("patient_number") or patient.get("numeric_id")

                if numeric_id_field:
                    try:
                        numeric_id = int(numeric_id_field)
                        new_mappings[numeric_id] = patient_id
                        new_reverse_mappings[patient_id] = numeric_id
                    except (ValueError, TypeError):
                        pass

            # 更新缓存
            with self._lock:
                self._numeric_to_uuid = new_mappings
                self._uuid_to_numeric = new_reverse_mappings
                self._last_refresh = datetime.now()

            logger.info(
                f"[IDMapping] 刷新完成: 加载了 {len(new_mappings)} 个映射关系，"
                f"总患者数: {len(patients)}"
            )

        except Exception as e:
            logger.error(f"[IDMapping] 刷新映射缓存失败: {e}", exc_info=True)

    def _is_cache_expired(self) -> bool:
        """检查缓存是否过期"""
        if self._last_refresh is None:
            return True
        return datetime.now() - self._last_refresh > self._ttl

    def _query_uuid_by_numeric_id(self, numeric_id: int) -> Optional[str]:
        """
        实时查询UUID（fallback方法）

        Args:
            numeric_id: 数字ID

        Returns:
            UUID字符串，如果找不到返回None
        """
        try:
            from infrastructure.api.backend_client import get_api_client

            client = get_api_client()
            patients = client.get_all_patients()

            for patient in patients:
                # 检查是否有匹配的数字ID字段
                numeric_field = patient.get("patient_number") or patient.get("numeric_id")
                if numeric_field:
                    try:
                        if int(numeric_field) == numeric_id:
                            return patient.get("id")
                    except (ValueError, TypeError):
                        continue

            return None

        except Exception as e:
            logger.error(f"[IDMapping] 实时查询失败: {e}", exc_info=True)
            return None


# ========== 全局单例 ==========

_id_mapping_service: Optional[IDMappingService] = None
_service_lock = Lock()


def get_id_mapping_service() -> IDMappingService:
    """
    获取全局ID映射服务实例（单例模式）

    Returns:
        IDMappingService实例
    """
    global _id_mapping_service

    if _id_mapping_service is None:
        with _service_lock:
            # 双重检查锁定
            if _id_mapping_service is None:
                _id_mapping_service = IDMappingService()
                # 首次初始化时尝试加载映射
                try:
                    _id_mapping_service.refresh_mappings()
                except Exception as e:
                    logger.warning(f"[IDMapping] 首次加载映射失败: {e}")

    return _id_mapping_service
