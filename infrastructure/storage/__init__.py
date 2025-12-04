"""
Storage Infrastructure Module
文件存储基础设施模块
"""

from infrastructure.storage.minio_client import MinioClient, get_minio_client

__all__ = ["MinioClient", "get_minio_client"]
