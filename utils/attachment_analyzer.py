"""
附件分析器 - 统一处理图片和 PDF 附件的视觉分析

工作流：
  图片 → qwen3.5-plus (DashScope，原生多模态) → 分析文本
  PDF  → Qwen3.5-397B-A17B (SiliconFlow，多图VLM) → 分析文本

该模块在 chat_router 中同步调用，分析结果注入 MedicalState，
ReAct Agent 节点无需感知多模态，直接处理富化后的文本消息。

也提供 inject_attachment_analysis() 供 Agent 节点直接导入使用，
放在此处避免从 agents.graph.nodes.__init__ 导入产生循环依赖。
"""
import logging
from typing import List, Dict

from langchain_core.messages import HumanMessage

from utils.llm_config import get_llm, get_pdf_analysis_llm

logger = logging.getLogger(__name__)

# 眼科图片分析提示词
_IMAGE_ANALYSIS_PROMPT = (
    "请详细描述这张眼科图像/眼底图的所有可见特征，"
    "包括视网膜结构、血管走行、视神经盘（视杯/视盘比）、黄斑区、色素分布情况等。"
    "如发现异常区域（渗出、出血、新生血管、视网膜脱离等），请重点说明其位置和范围。"
    "请保持客观描述，不做最终诊断。"
)

# PDF 医疗报告分析提示词
_PDF_ANALYSIS_PROMPT = (
    "以上是医疗检查报告的各页图片，请提取并总结以下关键信息：\n"
    "1. 检查项目名称\n"
    "2. 各项检测指标数值及参考范围\n"
    "3. 超出正常范围的异常指标（请标注↑或↓）\n"
    "4. 诊断结论或检查结论\n"
    "5. 医生建议或处理意见\n"
    "请按页面顺序整理，重要异常数据请加粗说明。"
)


def analyze_attachments(attachments: List[Dict], user_message: str = "") -> str:
    """
    统一分析图片和 PDF 附件，返回合并后的分析文本。

    在 chat_router.py 中的 graph_manager.chat() 调用之前同步执行。
    分析结果写入 MedicalState.attachment_analysis，
    Agent 节点将其注入最后一条 HumanMessage。

    Args:
        attachments: AttachmentRef 序列化后的字典列表
        user_message: 用户原始消息（预留，供未来上下文感知分析）

    Returns:
        合并后的分析文本，各附件用双换行分隔；
        无附件或分析失败则返回空字符串。
    """
    if not attachments:
        return ""

    results = []
    for att in attachments:
        file_type = att.get("file_type", "")
        filename = att.get("filename", "附件")

        try:
            if file_type == "image":
                base64_str = att.get("base64", "")
                mime_type = att.get("mime_type", "image/jpeg")
                if not base64_str:
                    logger.warning(f"[AttachmentAnalyzer] 图片附件 {filename} 缺少 base64 数据，跳过")
                    continue
                analysis = _analyze_image(base64_str, mime_type)
                results.append(f"【图片「{filename}」分析结果】\n{analysis}")

            elif file_type == "pdf":
                page_images = att.get("page_images", [])
                if not page_images:
                    logger.warning(f"[AttachmentAnalyzer] PDF附件 {filename} 缺少页面图片，跳过")
                    continue
                analysis = _analyze_pdf_pages(page_images)
                results.append(f"【PDF报告「{filename}」分析结果】\n{analysis}")

            else:
                logger.warning(f"[AttachmentAnalyzer] 未知附件类型: {file_type}，跳过")

        except Exception as e:
            logger.error(f"[AttachmentAnalyzer] 分析附件 {filename} 失败: {e}", exc_info=True)
            results.append(f"【附件「{filename}」分析失败】\n{e}")

    return "\n\n".join(results)


def _analyze_image(base64_str: str, mime_type: str) -> str:
    """
    图片视觉分析 - qwen3.5-plus (DashScope，原生多模态VLM)

    Args:
        base64_str: 图片 base64 字符串（不含 data: 前缀）
        mime_type: 图片 MIME 类型，如 "image/jpeg"

    Returns:
        视觉分析文本
    """
    logger.info(f"[AttachmentAnalyzer] 开始图片分析，mime={mime_type}")
    llm = get_llm()  # qwen3.5-plus，DashScope，原生支持多模态
    msg = HumanMessage(content=[
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{base64_str}"},
        },
        {
            "type": "text",
            "text": _IMAGE_ANALYSIS_PROMPT,
        },
    ])
    response = llm.invoke([msg])
    result = response.content if hasattr(response, "content") else str(response)
    logger.info(f"[AttachmentAnalyzer] 图片分析完成，结果长度={len(result)}")
    return result


def _analyze_pdf_pages(page_images: List[Dict]) -> str:
    """
    PDF 页面视觉分析 - Qwen3.5-397B-A17B (SiliconFlow，大参数VLM)

    将多页图片一次性发送给 VLM 进行整体分析。

    Args:
        page_images: 页面图片列表，每项包含 {base64, mime_type, page}

    Returns:
        PDF 内容分析文本
    """
    logger.info(f"[AttachmentAnalyzer] 开始PDF分析，共 {len(page_images)} 页")
    llm = get_pdf_analysis_llm()  # Qwen3.5-397B-A17B，SiliconFlow

    # 构建多图消息：每页图片 + 最终文字提示
    content = []
    for pg in page_images:
        b64 = pg.get("base64", "")
        mime = pg.get("mime_type", "image/jpeg")
        page_num = pg.get("page", "?")
        if not b64:
            continue
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        })
        logger.debug(f"[AttachmentAnalyzer] 已加入第 {page_num} 页图片")

    if not content:
        return "无有效页面图片可分析"

    content.append({
        "type": "text",
        "text": _PDF_ANALYSIS_PROMPT,
    })

    msg = HumanMessage(content=content)
    response = llm.invoke([msg])
    result = response.content if hasattr(response, "content") else str(response)
    logger.info(f"[AttachmentAnalyzer] PDF分析完成，结果长度={len(result)}")
    return result


def inject_attachment_analysis(messages: list, analysis: str) -> list:
    """
    将附件预分析结果注入最后一条 HumanMessage 的末尾。

    供 health/report/compliance Agent 节点导入使用。
    放在此处（而非 agents.graph.nodes.__init__）避免循环导入。

    Args:
        messages: 当前消息列表（state["messages"]）
        analysis: 附件分析文本（来自 state["attachment_analysis"]）

    Returns:
        注入后的消息列表副本；
        若 analysis 为空或无 HumanMessage 则原样返回。
    """
    if not analysis:
        return messages

    messages = list(messages)
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            original = messages[i].content
            # 仅注入纯文本内容；若 content 为列表（多模态）则跳过
            if isinstance(original, str):
                messages[i] = HumanMessage(
                    content=f"{original}\n\n{analysis}"
                )
            break

    return messages
