"""
Minio 客户端
用于科研数据可视化图片存储

Created: 2025-12-04
"""
import os
import io
import uuid
import logging
from typing import Optional, BinaryIO
from datetime import timedelta

logger = logging.getLogger(__name__)

# 尝试导入minio，如果不可用则提供模拟实现
try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    logger.warning("[MinioClient] minio 库未安装，文件存储功能不可用")


class MinioClient:
    """
    Minio 客户端封装

    用于上传和管理科研可视化图片文件
    """

    _instance: Optional["MinioClient"] = None

    def __init__(
        self,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        bucket_name: str = None,
        secure: bool = False
    ):
        """
        初始化 Minio 客户端

        Args:
            endpoint: Minio 服务端点
            access_key: 访问密钥
            secret_key: 秘密密钥
            bucket_name: 存储桶名称
            secure: 是否使用HTTPS
        """
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "")
        self.bucket_name = bucket_name or os.getenv("MINIO_BUCKET", "research-files")
        self.secure = secure

        self._client: Optional["Minio"] = None
        self._initialized = False

        # 尝试初始化
        if self.is_configured():
            self._init_client()

    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.endpoint and self.access_key and self.secret_key)

    def is_available(self) -> bool:
        """检查服务是否可用"""
        return MINIO_AVAILABLE and self._initialized and self._client is not None

    def _init_client(self):
        """初始化客户端连接"""
        if not MINIO_AVAILABLE:
            logger.warning("[MinioClient] minio 库未安装")
            return

        if not self.is_configured():
            logger.warning("[MinioClient] Minio 未配置，请设置环境变量")
            return

        try:
            self._client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )

            # 检查/创建存储桶
            if not self._client.bucket_exists(self.bucket_name):
                self._client.make_bucket(self.bucket_name)
                logger.info(f"[MinioClient] 创建存储桶: {self.bucket_name}")

            self._initialized = True
            logger.info(f"[MinioClient] 初始化成功: {self.endpoint}/{self.bucket_name}")

        except Exception as e:
            logger.error(f"[MinioClient] 初始化失败: {e}")
            self._client = None
            self._initialized = False

    def upload_bytes(
        self,
        data: bytes,
        object_name: str = None,
        content_type: str = "image/png",
        folder: str = "visualizations"
    ) -> Optional[str]:
        """
        上传字节数据

        Args:
            data: 文件字节数据
            object_name: 对象名称（不提供则自动生成）
            content_type: 内容类型
            folder: 文件夹路径

        Returns:
            文件URL，失败返回None
        """
        if not self.is_available():
            logger.warning("[MinioClient] 服务不可用，无法上传")
            return None

        try:
            # 生成对象名
            if not object_name:
                ext = content_type.split("/")[-1]
                object_name = f"{folder}/{uuid.uuid4().hex}.{ext}"
            elif not object_name.startswith(folder):
                object_name = f"{folder}/{object_name}"

            # 上传
            data_stream = io.BytesIO(data)
            self._client.put_object(
                self.bucket_name,
                object_name,
                data_stream,
                length=len(data),
                content_type=content_type
            )

            # 生成访问URL
            url = self.get_presigned_url(object_name)
            logger.info(f"[MinioClient] 上传成功: {object_name}")
            return url

        except Exception as e:
            logger.error(f"[MinioClient] 上传失败: {e}")
            return None

    def upload_file(
        self,
        file_path: str,
        object_name: str = None,
        content_type: str = None,
        folder: str = "visualizations"
    ) -> Optional[str]:
        """
        上传本地文件

        Args:
            file_path: 本地文件路径
            object_name: 对象名称
            content_type: 内容类型
            folder: 文件夹路径

        Returns:
            文件URL，失败返回None
        """
        if not self.is_available():
            logger.warning("[MinioClient] 服务不可用，无法上传")
            return None

        try:
            # 读取文件
            with open(file_path, "rb") as f:
                data = f.read()

            # 推断content_type
            if not content_type:
                if file_path.endswith(".png"):
                    content_type = "image/png"
                elif file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
                    content_type = "image/jpeg"
                elif file_path.endswith(".svg"):
                    content_type = "image/svg+xml"
                elif file_path.endswith(".pdf"):
                    content_type = "application/pdf"
                else:
                    content_type = "application/octet-stream"

            # 生成对象名
            if not object_name:
                object_name = os.path.basename(file_path)

            return self.upload_bytes(data, object_name, content_type, folder)

        except Exception as e:
            logger.error(f"[MinioClient] 上传文件失败: {e}")
            return None

    def get_presigned_url(
        self,
        object_name: str,
        expires: timedelta = timedelta(hours=24)
    ) -> Optional[str]:
        """
        获取预签名URL

        Args:
            object_name: 对象名称
            expires: 过期时间

        Returns:
            预签名URL
        """
        if not self.is_available():
            return None

        try:
            url = self._client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=expires
            )
            return url
        except Exception as e:
            logger.error(f"[MinioClient] 获取URL失败: {e}")
            return None

    def delete_object(self, object_name: str) -> bool:
        """
        删除对象

        Args:
            object_name: 对象名称

        Returns:
            是否成功
        """
        if not self.is_available():
            return False

        try:
            self._client.remove_object(self.bucket_name, object_name)
            logger.info(f"[MinioClient] 删除成功: {object_name}")
            return True
        except Exception as e:
            logger.error(f"[MinioClient] 删除失败: {e}")
            return False

    def list_objects(self, prefix: str = "", recursive: bool = True) -> list:
        """
        列出对象

        Args:
            prefix: 前缀过滤
            recursive: 是否递归

        Returns:
            对象列表
        """
        if not self.is_available():
            return []

        try:
            objects = self._client.list_objects(
                self.bucket_name,
                prefix=prefix,
                recursive=recursive
            )
            return [obj.object_name for obj in objects]
        except Exception as e:
            logger.error(f"[MinioClient] 列出对象失败: {e}")
            return []


# 单例实例
_minio_client: Optional[MinioClient] = None


def get_minio_client() -> MinioClient:
    """获取 Minio 客户端单例"""
    global _minio_client
    if _minio_client is None:
        _minio_client = MinioClient()
    return _minio_client


# 模块测试
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    client = get_minio_client()
    print(f"Minio 库可用: {MINIO_AVAILABLE}")
    print(f"已配置: {client.is_configured()}")
    print(f"服务可用: {client.is_available()}")
