"""
后端 API 客户端模块
统一处理所有与 Java 后端的 HTTP 通信

Created: 2025-12-01
Author: Claude Code
"""

import os
import requests
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class APIError(Exception):
    """API 返回错误（code != 200）"""
    pass


class NetworkError(Exception):
    """网络请求错误"""
    pass


class BackendAPIClient:
    """后端 API 统一客户端"""

    BASE_URL = os.getenv('BACKEND_API_URL', 'http://127.0.0.1:8081')
    HEADERS = {
        "Agent-Token": os.getenv('BACKEND_API_TOKEN', 'REMOVED_CONFIGURE_BACKEND_API_TOKEN'),
        "Content-Type": "application/json"
    }
    TIMEOUT = 30  # 30秒超时

    def __init__(self):
        """初始化 API 客户端"""
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        统一请求方法，自动解析 SaResult 响应格式

        Args:
            method: HTTP方法 (GET, POST, etc.)
            endpoint: API端点路径
            **kwargs: 传递给 requests 的其他参数

        Returns:
            解析后的 data 字段内容

        Raises:
            APIError: 后端返回错误（code != 200）
            NetworkError: 网络请求失败
        """
        url = f"{self.BASE_URL}{endpoint}"

        try:
            logger.info(f"[API请求] {method} {endpoint}, params={kwargs.get('params')}, json={kwargs.get('json') is not None}")

            response = self.session.request(
                method, url,
                timeout=self.TIMEOUT,
                **kwargs
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"[API响应] code={result.get('code')}, msg={result.get('msg')}")

            # 检查 SaResult 的 code 字段
            if result.get('code') != 200:
                error_msg = result.get('msg', 'Unknown error')
                logger.error(f"[API错误] {error_msg}")
                raise APIError(error_msg)

            return result.get('data')

        except requests.exceptions.Timeout:
            logger.error(f"[网络超时] {endpoint}")
            raise NetworkError(f"请求超时: {endpoint}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[网络错误] {endpoint}: {str(e)}")
            raise NetworkError(f"网络错误: {str(e)}")

    # ========== Agent 1 预约相关方法 ==========

    def get_patient_prescription(self, patient_id: str) -> Dict[str, Any]:
        """
        获取患者所有处方信息

        Args:
            patient_id: 患者UUID

        Returns:
            处方信息字典
        """
        return self._request('GET', '/agent/api/patient-prescription',
                            params={'patientId': patient_id})

    def get_doctor_free_time(self, patient_id: str, date: str,
                            hospital_key: str) -> Dict[str, Any]:
        """
        获取指定日期医生的空闲时间段

        Args:
            patient_id: 患者UUID
            date: 查询日期 yyyy-MM-dd（如 "2025-12-15"）
            hospital_key: 医院关键字

        Returns:
            空闲时间段和医生信息
        """
        return self._request('GET', '/agent/api/doctor-free-time',
                            params={
                                'patientId': patient_id,
                                'date': date,
                                'hospitalKey': hospital_key
                            })

    def reserve_doctor(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        预约医生

        Args:
            request_data: 预约请求数据，格式：
                {
                    "patientId": "uuid",
                    "doctorId": "uuid",
                    "reserveTime": "2025-12-15T09:00:00",
                    "medicalRecord": {
                        "department": "眼科",
                        "chiefComplaint": "主诉",
                        "presentIllness": "现病史",
                        "medicalHistory": "既往史",
                        "allergyHistory": "过敏史",
                        "familyHistory": "家族史",
                        "medicationHistory": "用药史",
                        "physicalExamination": "",
                        "eyeExamResults": "",
                        "specialExams": "",
                        "auxiliaryExams": "",
                        "diagnosis": "",
                        "treatmentPlan": ""
                    }
                }

        Returns:
            Agenda对象（包含预约ID、病历ID等）
        """
        return self._request('POST', '/agent/api/reserve-doctor',
                            json=request_data)

    def get_all_hospitals(self) -> list:
        """
        获取所有医院信息列表

        Returns:
            医院列表 List[HospitalSimpleResponse]，每个元素包含:
                - id: 医院UUID
                - hospitalName: 医院名称
                - province: 省份
                - city: 城市
                - address: 详细地址
                - hospitalType: 医院类型 (GENERAL/SPECIALIZED等)
                - hospitalLevel: 医院等级 (TERTIARY_A/TERTIARY_B等)
                - star: 评分 (0-5)
        """
        return self._request('GET', '/agent/api/all-hospitals')

    # ========== Agent 2 报告/处方相关方法 ==========

    def get_patient_prescription_limit(self, patient_id: str,
                                      limit: int) -> Dict[str, Any]:
        """
        获取患者最近N份处方摘要

        Args:
            patient_id: 患者UUID
            limit: 限制数量

        Returns:
            处方摘要列表
        """
        return self._request('GET', '/agent/api/patient-prescription-limit',
                            params={'patientId': patient_id, 'limit': limit})

    def get_patient_prescription_detail(self, patient_id: str,
                                       limit: int) -> Dict[str, Any]:
        """
        获取患者最近N份处方及详细药品信息

        Args:
            patient_id: 患者UUID
            limit: 限制数量

        Returns:
            处方详情列表（含药品明细）
        """
        return self._request('GET', '/agent/api/patient-prescription-detail',
                            params={'patientId': patient_id, 'limit': limit})

    def get_patient_scan_data(self, medical_record_id: str) -> Dict[str, Any]:
        """
        获取患者生物力学扫描数据

        Args:
            medical_record_id: 病历UUID

        Returns:
            生物力学扫描数据
        """
        return self._request('GET', '/agent/api/patient-scan-data',
                            params={'medicalRecordId': medical_record_id})

    def generate_medical_record_pdf(self, medical_record_id: str) -> str:
        """
        生成病历PDF报告

        Args:
            medical_record_id: 病历UUID

        Returns:
            PDF文件URL字符串
        """
        result = self._request('POST', '/agent/api/generate-medical-record-pdf',
                              params={'medicalRecordId': medical_record_id})
        # 后端直接返回URL字符串（不是对象）
        return result if isinstance(result, str) else str(result)

    def generate_prescription_pdf(self, medical_record_id: str) -> str:
        """
        生成处方PDF报告

        Args:
            medical_record_id: 病历UUID

        Returns:
            PDF文件URL字符串
        """
        result = self._request('POST', '/agent/api/generate-prescription-pdf',
                              params={'medicalRecordId': medical_record_id})
        # 后端直接返回URL字符串（不是对象）
        return result if isinstance(result, str) else str(result)

    # ========== Agent 3 提醒相关方法 ==========

    def get_patient_reminder(self, patient_id: str, limit: int = 5) -> Dict[str, Any]:
        """
        获取患者最近的提醒信息

        Args:
            patient_id: 患者UUID
            limit: 限制数量（默认5）

        Returns:
            包含患者信息和提醒列表的字典
        """
        return self._request('GET', '/agent/api/patient-reminder',
                            params={'patientId': patient_id, 'limit': limit})

    def get_patient_reminder_config(self, patient_id: str) -> Dict[str, Any]:
        """
        获取患者的提醒配置

        Args:
            patient_id: 患者UUID

        Returns:
            包含患者信息和提醒配置的字典
        """
        return self._request('GET', '/agent/api/patient-reminder-config',
                            params={'patientId': patient_id})

    def init_patient_reminder_config(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        初始化患者提醒配置（仅限首次创建）

        Args:
            request_data: 初始化请求数据

        Returns:
            ReminderConfig对象
        """
        return self._request('POST', '/agent/api/init-patient-reminder-config',
                            json=request_data)

    def modify_patient_reminder_config(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        修改患者提醒配置

        Args:
            request_data: 修改请求数据

        Returns:
            更新后的ReminderConfig对象
        """
        return self._request('POST', '/agent/api/modify-patient-reminder-config',
                            json=request_data)

    def create_reminder(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建患者提醒

        Args:
            request_data: 创建提醒请求数据

        Returns:
            创建的Reminder对象
        """
        return self._request('POST', '/agent/api/create-reminder',
                            json=request_data)

    def create_medical_reminder(self, request_data: Dict[str, Any]) -> Any:
        """
        批量创建用药提醒（含关联日程）

        根据指定的用药时间和持续天数，自动生成多天的 Reminder 和对应的 Agenda。

        Args:
            request_data: 创建请求数据，格式：
                {
                    "patientId": "患者UUID",
                    "title": "药品名称",
                    "content": "用药说明",
                    "medicalType": "DROP/PILL/CAPSULE/INJECT",
                    "time": "HH:mm:ss",
                    "duration": 7
                }

        Returns:
            None（此API的data为null，成功信息在msg中，
            _request返回data字段即None，不抛异常即表示成功）
        """
        return self._request('POST', '/agent/api/create-medical-reminder',
                            json=request_data)

    # ========== 患者管理相关方法 ==========

    def get_all_patients(self) -> list:
        """
        获取所有患者列表

        Returns:
            患者列表（List<Patient>）
        """
        return self._request('GET', '/agent/api/get-all-patient')

    def get_medical_records(self, patient_id: str) -> Dict[str, Any]:
        """
        获取患者病历列表（包含患者基本信息）

        Args:
            patient_id: 患者UUID

        Returns:
            包含患者信息和病历列表的字典:
            {
                "patient": {
                    "id": "患者UUID",
                    "patientName": "姓名",
                    "gender": "male/female",
                    "age": 年龄,
                    "phone": "手机号",
                    ...
                },
                "medicalRecords": [
                    {
                        "id": "病历UUID",
                        "medicalHistory": "既往史",
                        "allergyHistory": "过敏史",
                        "familyHistory": "家族史",
                        ...
                    }
                ]
            }

        Raises:
            APIError: 患者不存在或后端返回错误
            NetworkError: 网络请求失败
        """
        return self._request('GET', '/agent/api/get-medical-record',
                            params={'patientId': patient_id})

    def get_patient_appointments(self, patient_id: str) -> list:
        """
        获取患者历史预约记录

        Args:
            patient_id: 患者UUID

        Returns:
            预约记录列表

        注意：如果Java后端没有此接口，将返回空列表
        TODO: 等待Java后端实现该接口
        """
        try:
            # 尝试调用Java后端接口（假设接口路径）
            return self._request('GET', '/agent/api/patient-appointments',
                               params={'patientId': patient_id})
        except Exception as e:
            logger.warning(f"[API] 获取患者预约历史失败: {e}")
            return []  # 优雅降级：返回空列表

    def get_patient_all_scan_data(self, patient_id: str) -> list:
        """
        获取患者所有生物力学扫描数据

        策略：
        1. 先获取患者所有病历
        2. 遍历每个病历，获取扫描数据
        3. 合并返回

        Args:
            patient_id: 患者UUID

        Returns:
            扫描数据列表
        """
        all_scan_data = []

        try:
            # 获取患者病历列表
            result = self.get_medical_records(patient_id)
            medical_records = result.get("medicalRecords", [])

            # 遍历每个病历，获取扫描数据
            for record in medical_records:
                record_id = record.get("id")
                if not record_id:
                    continue

                try:
                    scan_data = self.get_patient_scan_data(record_id)
                    if scan_data:
                        # 添加病历ID信息
                        for data in scan_data:
                            data["medical_record_id"] = record_id
                        all_scan_data.extend(scan_data)
                except Exception as e:
                    logger.warning(f"[API] 获取病历 {record_id} 的扫描数据失败: {e}")
                    continue

            logger.info(f"[API] 获取患者 {patient_id} 的扫描数据: {len(all_scan_data)} 条")
            return all_scan_data

        except Exception as e:
            logger.error(f"[API] 获取患者所有扫描数据失败: {e}")
            return []  # 优雅降级

    # ========== Agent 6 产品推荐相关方法 ==========

    def search_products(self, query: str, category: str = None,
                       product_type: str = None, limit: int = 10) -> list:
        """
        搜索医药产品

        Args:
            query: 搜索关键词
            category: 产品分类
            product_type: 产品类型（PRESCRIPTION/OTC/DEVICE）
            limit: 返回数量限制

        Returns:
            产品列表
        """
        params = {"query": query, "limit": limit}
        if category:
            params["category"] = category
        if product_type:
            params["productType"] = product_type
        return self._request('GET', '/agent/api/search-products', params=params)

    def get_product_detail(self, product_id: str) -> Dict[str, Any]:
        """
        获取产品详情

        Args:
            product_id: 产品UUID

        Returns:
            产品详情字典
        """
        return self._request('GET', '/agent/api/product-detail',
                            params={"productId": product_id})

    def get_recommended_products(self, patient_id: str, diagnosis: str = None,
                                symptoms: str = None) -> list:
        """
        获取基于诊断的推荐产品

        Args:
            patient_id: 患者UUID
            diagnosis: 诊断信息
            symptoms: 症状描述

        Returns:
            推荐产品列表
        """
        params = {"patientId": patient_id}
        if diagnosis:
            params["diagnosis"] = diagnosis
        if symptoms:
            params["symptoms"] = symptoms
        return self._request('GET', '/agent/api/recommended-products', params=params)

    def add_to_cart(self, patient_id: str, product_id: str,
                   quantity: int = 1) -> Dict[str, Any]:
        """
        加入购物车

        Args:
            patient_id: 患者UUID
            product_id: 产品UUID
            quantity: 数量

        Returns:
            购物车操作结果
        """
        return self._request('POST', '/agent/api/add-to-cart',
                            json={
                                "patientId": patient_id,
                                "productId": product_id,
                                "quantity": quantity,
                            })

    def create_product_prescription(self, doctor_id: str, patient_id: str,
                                   product_id: str, dosage_instruction: str,
                                   notes: str = "") -> Dict[str, Any]:
        """
        开具产品处方

        Args:
            doctor_id: 医生UUID
            patient_id: 患者UUID
            product_id: 产品UUID
            dosage_instruction: 用法用量
            notes: 备注

        Returns:
            处方记录结果
        """
        return self._request('POST', '/agent/api/create-product-prescription',
                            json={
                                "doctorId": doctor_id,
                                "patientId": patient_id,
                                "productId": product_id,
                                "dosageInstruction": dosage_instruction,
                                "notes": notes,
                            })

    def close(self):
        """关闭连接"""
        self.session.close()


# ========== 全局单例 ==========

_api_client: Optional[BackendAPIClient] = None


def get_api_client() -> BackendAPIClient:
    """
    获取全局 API 客户端实例（单例模式）

    Returns:
        BackendAPIClient实例
    """
    global _api_client
    if _api_client is None:
        _api_client = BackendAPIClient()
        logger.info("[API客户端] 已初始化")
    return _api_client


# ========== 使用示例 ==========
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 测试 API 客户端
    client = get_api_client()

    try:
        # 测试获取处方信息
        print("测试获取处方信息...")
        # result = client.get_patient_prescription("patient-uuid-xxx")
        # print(f"结果: {result}")
        print("API客户端模块创建成功！")
    except Exception as e:
        print(f"错误: {e}")
