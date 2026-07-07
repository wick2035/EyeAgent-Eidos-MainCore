"""
RecommendationAgent 专用工具
医药产品推荐：根据诊断/症状搜索和推荐药品、器械

支持医生端（处方推荐）和患者端（OTC购买推荐）
"""
import json
import logging
import uuid
from datetime import datetime, timedelta
from langchain.tools import tool

logger = logging.getLogger(__name__)


# ========== 产品搜索工具 ==========

@tool
def search_products(
    query: str,
    category: str = "",
    product_type: str = "",
    limit: int = 10
) -> str:
    """
    搜索医药产品（药品、医疗器械）。

    Args:
        query: 搜索关键词（如"滴眼液"、"人工泪液"、"近视防控"）
        category: 产品分类筛选（如"眼科用药"、"抗生素"、"隐形眼镜"），为空则不限
        product_type: 产品类型筛选，可选值：
            - "PRESCRIPTION": 处方药
            - "OTC": 非处方药
            - "DEVICE": 医疗器械
            为空则不限
        limit: 返回数量限制（默认10）

    Returns:
        JSON格式的产品列表，每个产品包含：product_id, product_name, generic_name,
        product_type, category, unit_price, specification, stock_status,
        image_url, indications, is_prescription

    使用场景：
    - 医生根据诊断搜索相关药品
    - 患者根据症状搜索非处方药或器械
    - 按分类浏览可用产品
    """
    try:
        logger.info(
            f"[Tool] search_products: query={query}, category={category}, "
            f"product_type={product_type}, limit={limit}"
        )

        # TODO: 替换为真实后端 API 调用
        # from infrastructure.api.backend_client import get_api_client
        # client = get_api_client()
        # result = client.search_products(query, category, product_type, limit)

        # Stub: 返回模拟产品数据
        mock_products = _get_mock_products(query, category, product_type, limit)

        logger.info(f"[Tool Success] search_products: 找到 {len(mock_products)} 个产品")
        return json.dumps(mock_products, ensure_ascii=False)

    except Exception as e:
        error_msg = f"搜索产品失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def get_product_detail(product_id: str) -> str:
    """
    获取单个医药产品的详细信息。

    Args:
        product_id: 产品UUID

    Returns:
        JSON格式的产品详情，包含完整字段：product_id, product_name, generic_name,
        product_type, category, manufacturer, specification, dosage_form,
        unit_price, stock_status, image_url, description, indications,
        contraindications, side_effects, usage_instruction, approval_number,
        is_prescription

    使用场景：
    - 查看产品完整信息（禁忌症、不良反应等）
    - 在推荐前获取完整数据以确认适用性
    """
    try:
        logger.info(f"[Tool] get_product_detail: product_id={product_id}")

        # TODO: 替换为真实后端 API 调用
        # from infrastructure.api.backend_client import get_api_client
        # client = get_api_client()
        # result = client.get_product_detail(product_id)

        # Stub: 返回模拟数据
        mock_detail = {
            "product_id": product_id,
            "product_name": "玻璃酸钠滴眼液",
            "generic_name": "玻璃酸钠",
            "product_type": "OTC",
            "category": "眼科用药",
            "manufacturer": "参天制药",
            "specification": "5ml:5mg",
            "dosage_form": "滴眼液",
            "unit_price": 32.50,
            "stock_status": "IN_STOCK",
            "image_url": "https://img.example.com/product/hyaluronate.jpg",
            "description": "用于干眼症等眼部干燥症状的缓解",
            "indications": "干眼症、角结膜上皮损伤、术后恢复",
            "contraindications": "对本品成分过敏者禁用",
            "side_effects": "偶见眼部刺激感、过敏反应",
            "usage_instruction": "每次1-2滴，每日3-6次，滴入眼睑内",
            "approval_number": "国药准字H20040351",
            "is_prescription": False,
        }

        logger.info(f"[Tool Success] get_product_detail: {mock_detail['product_name']}")
        return json.dumps(mock_detail, ensure_ascii=False)

    except Exception as e:
        error_msg = f"获取产品详情失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def get_recommended_products(
    patient_id: str,
    diagnosis: str = "",
    symptoms: str = "",
    product_type: str = ""
) -> str:
    """
    基于患者诊断/症状获取智能推荐产品列表。

    Args:
        patient_id: 患者UUID
        diagnosis: 诊断信息（如"干眼症"、"近视"、"结膜炎"）
        symptoms: 症状描述（如"眼睛干涩、视力模糊"）
        product_type: 限定产品类型，可选值：
            - "PRESCRIPTION": 仅处方药
            - "OTC": 仅非处方药
            - "DEVICE": 仅医疗器械
            为空则返回所有类型

    Returns:
        JSON格式的推荐产品列表，每个产品包含完整信息和推荐理由(recommendation_reason)、
        匹配度评分(relevance_score)

    使用场景：
    - 医生查看针对特定诊断的推荐药品
    - 患者根据症状获取适合的OTC产品推荐
    - 综合推荐药品和器械
    """
    try:
        logger.info(
            f"[Tool] get_recommended_products: patient={patient_id}, "
            f"diagnosis={diagnosis}, symptoms={symptoms}"
        )

        # TODO: 替换为真实后端 API 调用
        # from infrastructure.api.backend_client import get_api_client
        # client = get_api_client()
        # result = client.get_recommended_products(patient_id, diagnosis, symptoms)

        # Stub: 返回模拟推荐数据
        mock_recommendations = _get_mock_recommendations(diagnosis, symptoms, product_type)

        logger.info(f"[Tool Success] get_recommended_products: 推荐 {len(mock_recommendations)} 个产品")
        return json.dumps(mock_recommendations, ensure_ascii=False)

    except Exception as e:
        error_msg = f"获取推荐产品失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


# ========== 患者操作工具 ==========

@tool
def add_to_cart(
    patient_id: str,
    product_id: str,
    quantity: int = 1
) -> str:
    """
    将产品加入患者的购物车。

    Args:
        patient_id: 患者UUID
        product_id: 产品UUID
        quantity: 购买数量（默认1）

    Returns:
        JSON格式的购物车状态

    使用场景：
    - 患者选定产品后加入购物车
    - 批量添加推荐产品
    """
    try:
        logger.info(
            f"[Tool] add_to_cart: patient={patient_id}, "
            f"product={product_id}, quantity={quantity}"
        )

        # TODO: 替换为真实后端 API 调用
        cart_item_id = str(uuid.uuid4())
        result = {
            "success": True,
            "cart_item_id": cart_item_id,
            "patient_id": patient_id,
            "product_id": product_id,
            "quantity": quantity,
            "added_at": datetime.now().isoformat(),
            "message": "产品已加入购物车（stub模拟）"
        }

        logger.info(f"[Tool Success] add_to_cart: cart_item_id={cart_item_id}")
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        error_msg = f"加入购物车失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


# ========== 医生操作工具 ==========

@tool
def create_product_prescription(
    doctor_id: str,
    patient_id: str,
    product_id: str,
    dosage_instruction: str,
    notes: str = ""
) -> str:
    """
    医生为患者开具产品处方/推荐记录。

    Args:
        doctor_id: 医生UUID
        patient_id: 患者UUID
        product_id: 产品UUID
        dosage_instruction: 用法用量说明（如"每日3次，每次1-2滴"）
        notes: 医嘱备注（可选）

    Returns:
        JSON格式的处方记录结果

    使用场景：
    - 医生确认推荐产品并记录处方
    - 为患者开具处方药推荐
    """
    try:
        logger.info(
            f"[Tool] create_product_prescription: doctor={doctor_id}, "
            f"patient={patient_id}, product={product_id}"
        )

        # TODO: 替换为真实后端 API 调用
        prescription_id = str(uuid.uuid4())
        result = {
            "success": True,
            "prescription_id": prescription_id,
            "doctor_id": doctor_id,
            "patient_id": patient_id,
            "product_id": product_id,
            "dosage_instruction": dosage_instruction,
            "notes": notes,
            "created_at": datetime.now().isoformat(),
            "message": "产品处方已开具（stub模拟）"
        }

        logger.info(f"[Tool Success] create_product_prescription: prescription_id={prescription_id}")
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        error_msg = f"开具产品处方失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


# ========== 数据获取工具 ==========

@tool
def get_patient_diagnosis_summary(patient_id: str) -> str:
    """
    获取患者最近的诊断摘要信息，包括诊断、病历和用药记录。

    Args:
        patient_id: 患者UUID

    Returns:
        JSON格式的诊断摘要，包含：
        - patient_info: 患者基本信息
        - latest_diagnosis: 最近诊断
        - medical_records: 最近病历摘要
        - current_medications: 当前用药

    使用场景：
    - 产品推荐前了解患者病情
    - 避免推荐与当前用药冲突的产品
    - 根据诊断精准推荐
    """
    try:
        logger.info(f"[Tool] get_patient_diagnosis_summary: patient_id={patient_id}")

        # 复用已有的后端客户端获取病历
        try:
            from infrastructure.api.backend_client import get_api_client
            client = get_api_client()
            medical_data = client.get_medical_records(patient_id)

            patient_info = medical_data.get("patient", {})
            records = medical_data.get("medicalRecords", [])

            summary = {
                "patient_info": {
                    "id": patient_info.get("id", patient_id),
                    "name": patient_info.get("patientName", "未知"),
                    "age": patient_info.get("age", "未知"),
                    "gender": patient_info.get("gender", "未知"),
                },
                "latest_diagnosis": "",
                "medical_records_count": len(records),
                "recent_records": [],
            }

            # 提取最近病历信息
            for record in records[:3]:
                record_summary = {
                    "id": record.get("id", ""),
                    "diagnosis": record.get("diagnosis", "待诊断"),
                    "chief_complaint": record.get("chiefComplaint", ""),
                    "department": record.get("department", ""),
                }
                summary["recent_records"].append(record_summary)
                if not summary["latest_diagnosis"] and record.get("diagnosis"):
                    summary["latest_diagnosis"] = record.get("diagnosis")

            logger.info(f"[Tool Success] get_patient_diagnosis_summary: {len(records)} 条病历")
            return json.dumps(summary, ensure_ascii=False)

        except Exception as api_error:
            logger.warning(f"[Tool] 从后端获取病历失败，使用模拟数据: {api_error}")
            # 降级返回模拟数据
            mock_summary = {
                "patient_info": {
                    "id": patient_id,
                    "name": "测试患者",
                    "age": 35,
                    "gender": "MALE",
                },
                "latest_diagnosis": "干眼症",
                "medical_records_count": 2,
                "recent_records": [
                    {
                        "id": str(uuid.uuid4()),
                        "diagnosis": "干眼症",
                        "chief_complaint": "双眼干涩不适3月",
                        "department": "眼科",
                    }
                ],
            }
            return json.dumps(mock_summary, ensure_ascii=False)

    except Exception as e:
        error_msg = f"获取患者诊断摘要失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


# ========== AgentToolController 新接口工具 ==========

@tool
def search_medicines(
    page_num: int = 1,
    page_size: int = 10,
    keyword: str = "",
) -> str:
    """搜索药品（连接真实药品数据库 medicine-page）。

    Args:
        page_num: 页码，从 1 开始
        page_size: 每页数量，默认 10，建议 5-20
        keyword: 药品名称关键字（模糊匹配 drugName），为空则返回全部药品

    Returns:
        JSON 字符串，每个药品包含：
        - id: 药品主键
        - drugId: 业务编号
        - drugName: 药品名称
        - drugCategory: 分类（如"眼科用药"）
        - drugSpecification: 规格
        - drugDosageForm: 剂型（如"滴眼液"）
        - manufacturer: 生产厂家
        - price: 价格
        - stockQuantity: 库存数量
        - isPrescriptionDrug: 是否处方药（true/false）
        - drugStatus: 药品状态
        - insuranceCategory: 医保类别
        - warningInfo: 警告信息
        - drugDescription: 药品说明

    使用场景：
    - 医生：根据诊断搜索可开具的药品（处方药 + OTC 全类型均可）
    - 患者：搜索 OTC 药品自购（处方药需标注"需医生处方"，不可直接加购）
    - 药品搜索请优先使用本工具；search_products 仅作器械（DEVICE）类的兜底
    """
    try:
        logger.info(
            f"[Tool] search_medicines: page_num={page_num}, page_size={page_size}, keyword={keyword}"
        )
        from infrastructure.api.backend_client import get_api_client
        client = get_api_client()
        result = client.search_medicines(page_num, page_size, keyword)
        if not isinstance(result, list):
            result = result if result is not None else []

        logger.info(f"[Tool Success] search_medicines: 找到 {len(result)} 个药品")
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        error_msg = f"搜索药品失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


@tool
def create_prescription_order(
    prescription_id: str,
    remark: str = "",
) -> str:
    """根据已存在的处方ID创建药品订单（仅医生权限）。

    Args:
        prescription_id: 处方UUID（必须来自工具返回，不可凭空捏造）
        remark: 订单备注（可选）

    Returns:
        JSON字符串，包含订单信息：id（订单ID）、orderNo、prescriptionId、
        orderStatus、totalAmount、expireTime、createTime 等

    使用场景：
    - 仅医生模式（role="doctor"）可调用
    - 必须在医生**显式确认**（如"确认下单"、"为患者下单"）后调用
    - 调用前应先用 get_patient_prescription_detail 确认处方真实存在
    - 工具未返回成功之前禁止说"已下单"

    ⚠️ 当前实现说明：
    - 真实接口 POST /agent/api/create-prescription-order 需 sa-token 医生登录态
      （后端 StpUtil.getLoginIdAsString），系统尚未接入 sa-token 流转
    - 本工具暂为 Mock 实现，返回模拟订单数据（含 _mock=true 标记）
    - 等 sa-token 方案落地后，将切换为 client.create_prescription_order(...) 真实调用
    """
    try:
        if not prescription_id:
            return "处方ID不能为空"

        logger.info(
            f"[Tool] create_prescription_order(MOCK): prescription_id={prescription_id}, remark={remark}"
        )

        # TODO(sa-token): 接入医生登录态 sa-token 后，切换为真实调用：
        #   from infrastructure.api.backend_client import get_api_client
        #   client = get_api_client()
        #   result = client.create_prescription_order(prescription_id, remark, sa_token=...)
        #   return json.dumps(result, ensure_ascii=False)

        order_id = str(uuid.uuid4())
        now = datetime.now()
        result = {
            "id": order_id,
            "orderNo": now.strftime("%Y%m%d%H%M%S") + order_id[:5],
            "prescriptionId": prescription_id,
            "orderType": "PRESCRIPTION",
            "orderStatus": "PENDING_PAYMENT",
            "totalAmount": 0.0,
            "paymentMethod": None,
            "paidTime": None,
            "expireTime": (now + timedelta(days=1)).isoformat(timespec="seconds"),
            "remark": remark or "AI工具代医生创建处方订单",
            "createTime": now.isoformat(timespec="seconds"),
            "updateTime": now.isoformat(timespec="seconds"),
            "_mock": True,
            "_note": "当前为 Mock 实现，sa-token 鉴权方案落地后将切换为真实接口",
        }

        logger.info(
            f"[Tool Success] create_prescription_order(MOCK): order_id={order_id}"
        )
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        error_msg = f"创建处方订单失败: {str(e)}"
        logger.error(f"[Tool Error] {error_msg}")
        return error_msg


# ========== Mock 数据生成 ==========

def _get_mock_products(query: str, category: str, product_type: str, limit: int) -> list:
    """生成模拟产品搜索结果"""
    all_products = [
        {
            "product_id": "prod-001-hyaluronate",
            "product_name": "玻璃酸钠滴眼液",
            "generic_name": "玻璃酸钠",
            "product_type": "OTC",
            "category": "眼科用药",
            "unit_price": 32.50,
            "specification": "5ml:5mg",
            "dosage_form": "滴眼液",
            "stock_status": "IN_STOCK",
            "image_url": "https://img.example.com/product/hyaluronate.jpg",
            "indications": "干眼症、角结膜上皮损伤",
            "is_prescription": False,
        },
        {
            "product_id": "prod-002-carbomer",
            "product_name": "卡波姆眼用凝胶",
            "generic_name": "卡波姆",
            "product_type": "OTC",
            "category": "眼科用药",
            "unit_price": 45.00,
            "specification": "10g",
            "dosage_form": "眼用凝胶",
            "stock_status": "IN_STOCK",
            "image_url": "https://img.example.com/product/carbomer.jpg",
            "indications": "干眼症、眼部干燥",
            "is_prescription": False,
        },
        {
            "product_id": "prod-003-levofloxacin",
            "product_name": "左氧氟沙星滴眼液",
            "generic_name": "左氧氟沙星",
            "product_type": "PRESCRIPTION",
            "category": "眼科用药",
            "unit_price": 28.00,
            "specification": "5ml:24.4mg",
            "dosage_form": "滴眼液",
            "stock_status": "IN_STOCK",
            "image_url": "https://img.example.com/product/levofloxacin.jpg",
            "indications": "细菌性结膜炎、角膜炎、泪囊炎",
            "is_prescription": True,
        },
        {
            "product_id": "prod-004-orthokeratology",
            "product_name": "角膜塑形镜（OK镜）",
            "generic_name": "角膜塑形镜",
            "product_type": "DEVICE",
            "category": "近视防控器械",
            "unit_price": 8800.00,
            "specification": "定制",
            "dosage_form": "医疗器械",
            "stock_status": "IN_STOCK",
            "image_url": "https://img.example.com/product/ok-lens.jpg",
            "indications": "青少年近视防控、轻中度近视矫正",
            "is_prescription": True,
        },
        {
            "product_id": "prod-005-atropine",
            "product_name": "低浓度阿托品滴眼液",
            "generic_name": "硫酸阿托品",
            "product_type": "PRESCRIPTION",
            "category": "眼科用药",
            "unit_price": 198.00,
            "specification": "5ml:0.25mg (0.01%)",
            "dosage_form": "滴眼液",
            "stock_status": "IN_STOCK",
            "image_url": "https://img.example.com/product/atropine.jpg",
            "indications": "儿童青少年近视防控",
            "is_prescription": True,
        },
        {
            "product_id": "prod-006-eyemask",
            "product_name": "蒸汽热敷眼罩",
            "generic_name": "蒸汽眼罩",
            "product_type": "DEVICE",
            "category": "眼部护理器械",
            "unit_price": 39.90,
            "specification": "10片/盒",
            "dosage_form": "一次性眼罩",
            "stock_status": "IN_STOCK",
            "image_url": "https://img.example.com/product/steam-mask.jpg",
            "indications": "缓解眼疲劳、干眼辅助治疗",
            "is_prescription": False,
        },
        {
            "product_id": "prod-007-bluelight-glasses",
            "product_name": "防蓝光护目镜",
            "generic_name": "防蓝光眼镜",
            "product_type": "DEVICE",
            "category": "视力防护器械",
            "unit_price": 128.00,
            "specification": "成人款",
            "dosage_form": "眼镜",
            "stock_status": "IN_STOCK",
            "image_url": "https://img.example.com/product/bluelight-glasses.jpg",
            "indications": "长时间使用电子屏幕导致的视疲劳",
            "is_prescription": False,
        },
        {
            "product_id": "prod-008-tobramycin",
            "product_name": "妥布霉素地塞米松滴眼液",
            "generic_name": "妥布霉素/地塞米松",
            "product_type": "PRESCRIPTION",
            "category": "眼科用药",
            "unit_price": 35.50,
            "specification": "5ml",
            "dosage_form": "滴眼液",
            "stock_status": "IN_STOCK",
            "image_url": "https://img.example.com/product/tobradex.jpg",
            "indications": "眼部炎症合并感染、术后抗炎",
            "is_prescription": True,
        },
    ]

    # 按条件过滤
    filtered = all_products
    if product_type:
        filtered = [p for p in filtered if p["product_type"] == product_type]
    if category:
        filtered = [p for p in filtered if category in p["category"]]

    # 按关键词简单匹配（模拟搜索）
    if query:
        query_lower = query.lower()
        scored = []
        for p in filtered:
            score = 0
            searchable = f"{p['product_name']}{p.get('generic_name','')}{p['indications']}{p['category']}"
            for char in query_lower:
                if char in searchable.lower():
                    score += 1
            if score > 0:
                scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        filtered = [p for _, p in scored]

    return filtered[:limit]


def _get_mock_recommendations(diagnosis: str, symptoms: str, product_type: str) -> list:
    """生成模拟推荐结果"""
    # 根据诊断/症状关键词匹配推荐
    recommendations = []

    search_text = f"{diagnosis}{symptoms}".lower()

    if "干眼" in search_text or "干涩" in search_text:
        recommendations = [
            {
                "product_id": "prod-001-hyaluronate",
                "product_name": "玻璃酸钠滴眼液",
                "generic_name": "玻璃酸钠",
                "product_type": "OTC",
                "category": "眼科用药",
                "unit_price": 32.50,
                "specification": "5ml:5mg",
                "dosage_form": "滴眼液",
                "stock_status": "IN_STOCK",
                "image_url": "https://img.example.com/product/hyaluronate.jpg",
                "indications": "干眼症、角结膜上皮损伤",
                "is_prescription": False,
                "relevance_score": 0.95,
                "recommendation_reason": "一线人工泪液，适用于轻中度干眼症，安全性高",
            },
            {
                "product_id": "prod-002-carbomer",
                "product_name": "卡波姆眼用凝胶",
                "generic_name": "卡波姆",
                "product_type": "OTC",
                "category": "眼科用药",
                "unit_price": 45.00,
                "specification": "10g",
                "dosage_form": "眼用凝胶",
                "stock_status": "IN_STOCK",
                "image_url": "https://img.example.com/product/carbomer.jpg",
                "indications": "干眼症、眼部干燥",
                "is_prescription": False,
                "relevance_score": 0.88,
                "recommendation_reason": "凝胶剂型，持续润滑效果更持久，适合夜间使用",
            },
            {
                "product_id": "prod-006-eyemask",
                "product_name": "蒸汽热敷眼罩",
                "generic_name": "蒸汽眼罩",
                "product_type": "DEVICE",
                "category": "眼部护理器械",
                "unit_price": 39.90,
                "specification": "10片/盒",
                "dosage_form": "一次性眼罩",
                "stock_status": "IN_STOCK",
                "image_url": "https://img.example.com/product/steam-mask.jpg",
                "indications": "缓解眼疲劳、干眼辅助治疗",
                "is_prescription": False,
                "relevance_score": 0.75,
                "recommendation_reason": "热敷可促进睑板腺分泌，辅助改善干眼症状",
            },
        ]
    elif "近视" in search_text:
        recommendations = [
            {
                "product_id": "prod-004-orthokeratology",
                "product_name": "角膜塑形镜（OK镜）",
                "generic_name": "角膜塑形镜",
                "product_type": "DEVICE",
                "category": "近视防控器械",
                "unit_price": 8800.00,
                "specification": "定制",
                "dosage_form": "医疗器械",
                "stock_status": "IN_STOCK",
                "image_url": "https://img.example.com/product/ok-lens.jpg",
                "indications": "青少年近视防控、轻中度近视矫正",
                "is_prescription": True,
                "relevance_score": 0.92,
                "recommendation_reason": "近视防控金标准，夜间佩戴白天无需戴镜",
            },
            {
                "product_id": "prod-005-atropine",
                "product_name": "低浓度阿托品滴眼液",
                "generic_name": "硫酸阿托品",
                "product_type": "PRESCRIPTION",
                "category": "眼科用药",
                "unit_price": 198.00,
                "specification": "5ml:0.25mg (0.01%)",
                "dosage_form": "滴眼液",
                "stock_status": "IN_STOCK",
                "image_url": "https://img.example.com/product/atropine.jpg",
                "indications": "儿童青少年近视防控",
                "is_prescription": True,
                "relevance_score": 0.88,
                "recommendation_reason": "低浓度阿托品可有效延缓近视进展，副作用小",
            },
        ]
    elif "结膜炎" in search_text or "感染" in search_text or "炎症" in search_text:
        recommendations = [
            {
                "product_id": "prod-003-levofloxacin",
                "product_name": "左氧氟沙星滴眼液",
                "generic_name": "左氧氟沙星",
                "product_type": "PRESCRIPTION",
                "category": "眼科用药",
                "unit_price": 28.00,
                "specification": "5ml:24.4mg",
                "dosage_form": "滴眼液",
                "stock_status": "IN_STOCK",
                "image_url": "https://img.example.com/product/levofloxacin.jpg",
                "indications": "细菌性结膜炎、角膜炎、泪囊炎",
                "is_prescription": True,
                "relevance_score": 0.93,
                "recommendation_reason": "广谱抗菌，眼科感染一线用药",
            },
            {
                "product_id": "prod-008-tobramycin",
                "product_name": "妥布霉素地塞米松滴眼液",
                "generic_name": "妥布霉素/地塞米松",
                "product_type": "PRESCRIPTION",
                "category": "眼科用药",
                "unit_price": 35.50,
                "specification": "5ml",
                "dosage_form": "滴眼液",
                "stock_status": "IN_STOCK",
                "image_url": "https://img.example.com/product/tobradex.jpg",
                "indications": "眼部炎症合并感染、术后抗炎",
                "is_prescription": True,
                "relevance_score": 0.85,
                "recommendation_reason": "抗菌+抗炎双效，适合炎症合并感染",
            },
        ]
    else:
        # 默认推荐常用产品
        recommendations = [
            {
                "product_id": "prod-001-hyaluronate",
                "product_name": "玻璃酸钠滴眼液",
                "generic_name": "玻璃酸钠",
                "product_type": "OTC",
                "category": "眼科用药",
                "unit_price": 32.50,
                "specification": "5ml:5mg",
                "dosage_form": "滴眼液",
                "stock_status": "IN_STOCK",
                "image_url": "https://img.example.com/product/hyaluronate.jpg",
                "indications": "干眼症、角结膜上皮损伤",
                "is_prescription": False,
                "relevance_score": 0.70,
                "recommendation_reason": "常用眼科基础用药，适用范围广",
            },
            {
                "product_id": "prod-007-bluelight-glasses",
                "product_name": "防蓝光护目镜",
                "generic_name": "防蓝光眼镜",
                "product_type": "DEVICE",
                "category": "视力防护器械",
                "unit_price": 128.00,
                "specification": "成人款",
                "dosage_form": "眼镜",
                "stock_status": "IN_STOCK",
                "image_url": "https://img.example.com/product/bluelight-glasses.jpg",
                "indications": "长时间使用电子屏幕导致的视疲劳",
                "is_prescription": False,
                "relevance_score": 0.60,
                "recommendation_reason": "日常护眼，减少蓝光对眼部的伤害",
            },
        ]

    # 按类型过滤
    if product_type:
        recommendations = [r for r in recommendations if r["product_type"] == product_type]

    return recommendations


# ========== 工具列表组装 ==========

from agents.tools.agent_tools import (
    get_current_time,
    get_patient_prescription_detail,
)

# 通用工具
RECOMMENDATION_COMMON_TOOLS = [
    get_current_time,
]

# 数据获取工具
RECOMMENDATION_DATA_TOOLS = [
    get_patient_diagnosis_summary,
    get_patient_prescription_detail,
]

# 产品搜索工具
RECOMMENDATION_PRODUCT_TOOLS = [
    search_medicines,         # 真实药品搜索（首选，处方药 + OTC 全类型）
    search_products,          # Mock，主要用于器械（DEVICE）兜底
    get_product_detail,       # Mock 详情
    get_recommended_products, # Mock 智能推荐
]

# 操作工具
RECOMMENDATION_ACTION_TOOLS = [
    add_to_cart,
    create_product_prescription,
    create_prescription_order,  # 由处方ID创建订单（Mock，待 sa-token 鉴权方案落地）
]

# RecommendationAgent 完整工具列表
AGENT_6_TOOLS = (
    RECOMMENDATION_COMMON_TOOLS
    + RECOMMENDATION_DATA_TOOLS
    + RECOMMENDATION_PRODUCT_TOOLS
    + RECOMMENDATION_ACTION_TOOLS
)


# ========== 模块信息 ==========
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Recommendation Tools 模块信息")
    print("=" * 50)
    print(f"通用工具数量: {len(RECOMMENDATION_COMMON_TOOLS)}")
    print(f"数据获取工具: {len(RECOMMENDATION_DATA_TOOLS)}")
    print(f"产品搜索工具: {len(RECOMMENDATION_PRODUCT_TOOLS)}")
    print(f"操作工具: {len(RECOMMENDATION_ACTION_TOOLS)}")
    print(f"总工具数量: {len(AGENT_6_TOOLS)}")

    print("\n所有可用工具:")
    for i, t in enumerate(AGENT_6_TOOLS, 1):
        print(f"  {i}. {t.name}: {t.description[:50]}...")
