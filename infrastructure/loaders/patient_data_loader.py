"""
患者数据加载器模块
负责并发加载患者的完整数据

Created: 2025-12-02
Author: Claude Code
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from infrastructure.api.backend_client import BackendAPIClient
from domain.models.patient import Patient

logger = logging.getLogger(__name__)


@dataclass
class PatientFullData:
    """
    患者完整数据

    包含：
    - 基础信息：姓名、年龄、性别、电话等
    - 病历记录：既往史、过敏史、家族史
    - 历史预约
    - 历史处方
    - 扫描数据
    - 提醒历史
    """
    basic_info: Optional[Patient] = None
    medical_records: List[Dict[str, Any]] = field(default_factory=list)
    appointments: List[Dict[str, Any]] = field(default_factory=list)
    prescriptions: List[Dict[str, Any]] = field(default_factory=list)
    scan_data: List[Dict[str, Any]] = field(default_factory=list)
    reminders: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        """确保所有列表字段不为None"""
        if self.medical_records is None:
            self.medical_records = []
        if self.appointments is None:
            self.appointments = []
        if self.prescriptions is None:
            self.prescriptions = []
        if self.scan_data is None:
            self.scan_data = []
        if self.reminders is None:
            self.reminders = []


class PatientDataLoader:
    """
    患者数据加载器

    使用ThreadPoolExecutor并发加载5个数据源：
    1. 基础信息（从PatientRepository获取）
    2. 历史预约（从backend API获取）
    3. 历史处方（从backend API获取）
    4. 扫描数据（从backend API获取）
    5. 提醒历史（从backend API获取）

    特性：
    - 并发加载，性能优化
    - 单个数据源超时控制（10秒）
    - 优雅降级（单个失败不影响其他）
    """

    # 单个任务超时时间（秒）
    TASK_TIMEOUT = 10

    def __init__(self, api_client: BackendAPIClient):
        """
        初始化数据加载器

        Args:
            api_client: Backend API客户端实例
        """
        self.api_client = api_client

    def load_all_patient_data(self, patient_id: str) -> PatientFullData:
        """
        并发加载患者所有数据

        Args:
            patient_id: 患者UUID

        Returns:
            PatientFullData对象，包含所有加载的数据
        """
        logger.info(f"[DataLoader] 开始加载患者数据: {patient_id}")

        # 创建结果容器
        result = PatientFullData()

        # 使用线程池并发执行5个加载任务
        with ThreadPoolExecutor(max_workers=5, thread_name_prefix="PatientDataLoader") as executor:
            # 提交所有任务
            futures = {
                executor.submit(self._load_basic_info, patient_id): "basic_info",
                executor.submit(self._load_appointments, patient_id): "appointments",
                executor.submit(self._load_prescriptions, patient_id): "prescriptions",
                executor.submit(self._load_scan_data, patient_id): "scan_data",
                executor.submit(self._load_reminders, patient_id): "reminders"
            }

            # 等待所有任务完成（带超时）
            for future in as_completed(futures, timeout=self.TASK_TIMEOUT + 5):
                task_name = futures[future]
                try:
                    data = future.result(timeout=self.TASK_TIMEOUT)
                    self._set_result_field(result, task_name, data)
                    logger.debug(f"[DataLoader] 加载{task_name}成功")
                except TimeoutError:
                    logger.warning(f"[DataLoader] 加载{task_name}超时")
                except Exception as e:
                    logger.warning(f"[DataLoader] 加载{task_name}失败: {e}")

        # 统计加载结果
        self._log_summary(result, patient_id)

        return result

    def _load_basic_info(self, patient_id: str) -> Optional[Patient]:
        """
        加载患者基础信息

        使用PatientRepository获取基础信息和最新病历

        Args:
            patient_id: 患者UUID

        Returns:
            Patient对象，如果失败返回None
        """
        try:
            from infrastructure.repositories.patient_repository_impl import PatientRepositoryImpl

            patient_repo = PatientRepositoryImpl()
            patient = patient_repo.get_by_id(patient_id)

            if patient:
                logger.debug(
                    f"[DataLoader] 基础信息加载成功: "
                    f"name={patient.name}, age={patient.age}"
                )
            else:
                logger.warning(f"[DataLoader] 未找到患者基础信息: {patient_id}")

            return patient

        except Exception as e:
            logger.error(f"[DataLoader] 加载基础信息失败: {e}", exc_info=True)
            return None

    def _load_appointments(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        加载患者历史预约

        Args:
            patient_id: 患者UUID

        Returns:
            预约记录列表
        """
        try:
            appointments = self.api_client.get_patient_appointments(patient_id)
            logger.debug(f"[DataLoader] 预约历史加载成功: {len(appointments)}条")
            return appointments if appointments else []
        except Exception as e:
            logger.warning(f"[DataLoader] 加载预约历史失败: {e}")
            return []

    def _load_prescriptions(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        加载患者历史处方

        Args:
            patient_id: 患者UUID

        Returns:
            处方记录列表
        """
        try:
            result = self.api_client.get_patient_prescription(patient_id)
            # 处方接口返回的是字典，包含prescriptions字段
            prescriptions = result.get("prescriptions", []) if isinstance(result, dict) else []
            logger.debug(f"[DataLoader] 处方历史加载成功: {len(prescriptions)}条")
            return prescriptions
        except Exception as e:
            logger.warning(f"[DataLoader] 加载处方历史失败: {e}")
            return []

    def _load_scan_data(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        加载患者扫描数据

        Args:
            patient_id: 患者UUID

        Returns:
            扫描数据列表
        """
        try:
            scan_data = self.api_client.get_patient_all_scan_data(patient_id)
            logger.debug(f"[DataLoader] 扫描数据加载成功: {len(scan_data)}条")
            return scan_data if scan_data else []
        except Exception as e:
            logger.warning(f"[DataLoader] 加载扫描数据失败: {e}")
            return []

    def _load_reminders(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        加载患者提醒历史

        Args:
            patient_id: 患者UUID

        Returns:
            提醒记录列表
        """
        try:
            result = self.api_client.get_patient_reminder(patient_id)
            # 提醒接口返回的是字典，包含reminders字段
            reminders = result.get("reminders", []) if isinstance(result, dict) else []
            logger.debug(f"[DataLoader] 提醒历史加载成功: {len(reminders)}条")
            return reminders
        except Exception as e:
            logger.warning(f"[DataLoader] 加载提醒历史失败: {e}")
            return []

    def _set_result_field(self, result: PatientFullData, field_name: str, data: Any):
        """
        设置结果对象的字段

        Args:
            result: PatientFullData对象
            field_name: 字段名
            data: 数据
        """
        if field_name == "basic_info":
            result.basic_info = data
            # 同时提取medical_records
            if data:
                try:
                    # 从get_medical_records获取病历列表
                    medical_result = self.api_client.get_medical_records(data.patient_id)
                    # 注意：接口返回的是列表，不是字典
                    if isinstance(medical_result, list):
                        result.medical_records = medical_result
                    else:
                        result.medical_records = medical_result.get("medicalRecords", [])
                except Exception as e:
                    logger.warning(f"[DataLoader] 提取病历记录失败: {e}")
        elif field_name == "appointments":
            result.appointments = data or []
        elif field_name == "prescriptions":
            result.prescriptions = data or []
        elif field_name == "scan_data":
            result.scan_data = data or []
        elif field_name == "reminders":
            result.reminders = data or []

    def _log_summary(self, result: PatientFullData, patient_id: str):
        """
        记录加载结果摘要

        Args:
            result: PatientFullData对象
            patient_id: 患者ID
        """
        summary_parts = []

        if result.basic_info:
            summary_parts.append("基础✓")
        else:
            summary_parts.append("基础✗")

        summary_parts.append(f"病历{len(result.medical_records)}条")
        summary_parts.append(f"预约{len(result.appointments)}条")
        summary_parts.append(f"处方{len(result.prescriptions)}条")
        summary_parts.append(f"扫描{len(result.scan_data)}条")
        summary_parts.append(f"提醒{len(result.reminders)}条")

        logger.info(
            f"[DataLoader] 患者 {patient_id} 数据加载完成: "
            + " ".join(summary_parts)
        )
