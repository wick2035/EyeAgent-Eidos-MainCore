"""
UUID工具基类 - 为数据库服务提供UUID生成和验证功能

Author: System Migration
Date: 2025-11-20
Purpose: 支持INT到UUID的数据库迁移
"""

import uuid
import re
from typing import Optional, Union


class UUIDService:
    """UUID生成和验证工具类"""

    @staticmethod
    def generate_uuid() -> str:
        """
        生成标准UUID v4字符串

        Returns:
            str: UUID格式: "550e8400-e29b-41d4-a716-446655440000"
        """
        return str(uuid.uuid4())

    @staticmethod
    def is_valid_uuid(value: str) -> bool:
        """
        验证字符串是否为有效的UUID格式

        Args:
            value: 待验证的字符串

        Returns:
            bool: True如果是有效UUID,否则False
        """
        if not isinstance(value, str):
            return False

        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(value))

    @staticmethod
    def normalize_id(value: Union[str, int, None]) -> Optional[str]:
        """
        规范化ID - 兼容INT和UUID两种格式

        在迁移期间,支持同时接受INT和UUID格式的ID

        Args:
            value: INT类型的旧ID 或 UUID字符串

        Returns:
            str: 规范化后的ID字符串
            None: 如果输入为None

        Raises:
            ValueError: 如果输入格式无效
        """
        if value is None:
            return None

        # 如果是整数,转换为字符串(迁移期间兼容旧INT ID)
        if isinstance(value, int):
            return str(value)

        # 如果是字符串
        if isinstance(value, str):
            value = value.strip()

            # 检查是否为UUID格式
            if UUIDService.is_valid_uuid(value):
                return value.lower()  # 统一转小写

            # 检查是否为数字字符串(旧INT ID)
            if value.isdigit():
                return value

            raise ValueError(f"无效的ID格式: {value}")

        raise ValueError(f"不支持的ID类型: {type(value)}")

    @staticmethod
    def convert_to_uuid_if_needed(value: Union[str, int, None]) -> Optional[str]:
        """
        如果输入是INT,则生成新的UUID;如果已是UUID,则返回原值

        用于数据迁移场景

        Args:
            value: 原始ID值

        Returns:
            str: UUID字符串
            None: 如果输入为None
        """
        if value is None:
            return None

        normalized = UUIDService.normalize_id(value)

        # 如果是纯数字(旧INT ID),生成新UUID
        if normalized and normalized.isdigit():
            return UUIDService.generate_uuid()

        # 否则返回原UUID
        return normalized


class BaseServiceWithUUID:
    """
    带UUID支持的数据库服务基类

    所有数据库服务类都应继承此类以获得UUID功能
    """

    def __init__(self):
        self.uuid_service = UUIDService()

    def generate_uuid(self) -> str:
        """生成新UUID"""
        return self.uuid_service.generate_uuid()

    def validate_uuid(self, value: str) -> bool:
        """验证UUID格式"""
        return self.uuid_service.is_valid_uuid(value)

    def normalize_id(self, value: Union[str, int, None]) -> Optional[str]:
        """规范化ID(兼容INT和UUID)"""
        return self.uuid_service.normalize_id(value)


# 便捷函数 - 可直接导入使用
def generate_uuid() -> str:
    """生成UUID v4字符串"""
    return UUIDService.generate_uuid()


def is_valid_uuid(value: str) -> bool:
    """验证UUID格式"""
    return UUIDService.is_valid_uuid(value)


def normalize_id(value: Union[str, int, None]) -> Optional[str]:
    """规范化ID(兼容INT和UUID)"""
    return UUIDService.normalize_id(value)


if __name__ == "__main__":
    # 测试代码
    print("=== UUID工具类测试 ===\n")

    # 测试UUID生成
    print("1. 生成UUID:")
    uuid1 = generate_uuid()
    uuid2 = generate_uuid()
    print(f"   UUID 1: {uuid1}")
    print(f"   UUID 2: {uuid2}")
    print(f"   是否不同: {uuid1 != uuid2}\n")

    # 测试UUID验证
    print("2. UUID验证:")
    valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
    invalid_uuid = "not-a-uuid"
    print(f"   {valid_uuid} -> {is_valid_uuid(valid_uuid)}")
    print(f"   {invalid_uuid} -> {is_valid_uuid(invalid_uuid)}\n")

    # 测试ID规范化
    print("3. ID规范化测试:")
    test_cases = [
        123,  # 旧INT ID
        "456",  # 数字字符串
        "550e8400-e29b-41d4-a716-446655440000",  # UUID
        "550E8400-E29B-41D4-A716-446655440000",  # 大写UUID
        None,  # 空值
    ]

    for case in test_cases:
        try:
            result = normalize_id(case)
            print(f"   {case} ({type(case).__name__}) -> {result}")
        except ValueError as e:
            print(f"   {case} -> 错误: {e}")

    print("\n=== 测试完成 ===")
