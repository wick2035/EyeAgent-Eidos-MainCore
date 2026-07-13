"""
GraphManager - LangGraph 图管理器

替代原有的 AgentManager，提供基于 LangGraph 的对话管理。
"""
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, Generator, AsyncGenerator, List, TypeAlias
import asyncio

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from agents.graph.state import MedicalState, create_initial_state
from agents.graph.graph_builder import get_medical_graph, create_medical_graph
from agents.graph.id_mapping import (
    ThreadIDManager,
    get_branch_thread_config,
    get_thread_config,
)
from agents.graph.checkpointer import get_checkpointer
from agents.graph.persistence_adapter import PersistenceAdapter, NullPersistenceAdapter
from agents.graph.token_usage_extractor import (
    extract_token_used_from_ai_message,
    extract_token_used_from_stream_event,
    merge_token_used,
)
from agents.graph.tool_result_normalizer import (
    normalize_from_stream_events,
    normalize_from_tool_calls,
)
from agents.graph.citation_extractor import (
    deduplicate_citations,
    extract_citations_from_search_results,
    merge_citations,
)
from agents.graph.attachment_citations import (
    CITATION_TOOL_NAME,
    build_attachment_citation_fallback,
    extract_attachment_citations_from_statistics_output,
    extract_attachment_citations_from_tool_output,
)
from application.services.legacy_text_turn_authority import (
    LegacyTextTurnAuthority,
    build_legacy_text_turn_authority,
)
from utils.transient_attachment_context import (
    get_attachment_analysis,
    get_research_document_context,
)

logger = logging.getLogger(__name__)

_PUBLIC_CHAT_ERROR_MESSAGE = "对话暂时不可用，请稍后再试。"
_CHAT_EXECUTION_FAILED = "CHAT_EXECUTION_FAILED"
_CHAT_PERSISTENCE_FAILED = "CHAT_PERSISTENCE_FAILED"
_CHAT_SOURCE_INVALID = "CHAT_SOURCE_INVALID"


PublicGraphChunk: TypeAlias = Dict[str, Any]


@dataclass(frozen=True)
class PreparedGraphTerminal:
    """Prepared path 的内部终态；不得直接透传到平台 SSE。"""

    content: str
    token_used: Optional[int]
    tool_results: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    agent_type: str
    stage: str


PreparedGraphEvent: TypeAlias = PublicGraphChunk | PreparedGraphTerminal


def _validate_prepared_research_options(
    value: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "enable_institution_data",
        "enable_web_search",
        "types",
    }:
        raise ValueError("RESEARCH_OPTIONS_CONFLICT")
    institution = value["enable_institution_data"]
    web = value["enable_web_search"]
    search_types = value["types"]
    if (
        type(institution) is not bool
        or type(web) is not bool
        or not isinstance(search_types, list)
        or not all(
            isinstance(item, str)
            and item in {"general", "pubmed", "scholar"}
            for item in search_types
        )
        or len(set(search_types)) != len(search_types)
    ):
        raise ValueError("RESEARCH_OPTIONS_CONFLICT")
    canonical_types = [
        item
        for item in ("general", "pubmed", "scholar")
        if item in search_types
    ]
    if search_types != canonical_types or web != bool(search_types):
        raise ValueError("RESEARCH_OPTIONS_CONFLICT")
    return {
        "enable_institution_data": institution,
        "enable_web_search": web,
        "types": list(search_types),
    }


def _resolve_legacy_text_turn_authority(
    *,
    agent_type: str,
    patient_id: Optional[str],
    role: str,
    branch_mode: str,
    prepared_mode: bool,
    kwargs: Dict[str, Any],
) -> Optional[LegacyTextTurnAuthority]:
    supplied = kwargs.pop("_legacy_text_turn_authority", None)
    if prepared_mode:
        if supplied is not None:
            raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
        return None
    if role != "doctor" or agent_type not in {"health", "research"}:
        if supplied is not None:
            raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
        return None
    if branch_mode == "normal":
        if supplied is not None:
            raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
        authority = build_legacy_text_turn_authority(
            agent_type=agent_type,
            patient_id=patient_id,
            enable_institution_data=kwargs.get(
                "enable_institution_data",
                False,
            ),
            enable_web_search=kwargs.get("enable_web_search", False),
            web_search_types=kwargs.get("web_search_types", []),
        )
    else:
        if not isinstance(supplied, LegacyTextTurnAuthority):
            raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
        authority = supplied
        if (
            authority.agent_type != agent_type
            or authority.patient_id != patient_id
        ):
            raise ValueError("LEGACY_TURN_CONFIGURATION_INVALID")
    kwargs.update(authority.graph_research_options())
    return authority


def _legacy_user_context(
    *,
    stage: Optional[str],
    agent_type: str,
    patient_id: Optional[str],
    authority: Optional[LegacyTextTurnAuthority],
) -> Dict[str, Any]:
    context = {
        "stage": stage,
        "agent_type": agent_type,
        "patient_id": patient_id,
    }
    if authority is not None:
        metadata = authority.to_message_metadata()
        context.update({
            "turn_configuration": metadata["turn_configuration"],
            "attachment_ids": metadata["attachment_ids"],
        })
    return context


class GraphManager:
    """
    LangGraph 图管理器

    提供对话管理、状态持久化、流式输出等功能。

    使用方式:
        manager = GraphManager()

        # 同步对话
        response = manager.chat(
            patient_id="xxx",
            session_id="xxx",
            message="你好",
        )

        # 流式对话
        for chunk in manager.chat_stream(
            patient_id="xxx",
            session_id="xxx",
            message="你好",
        ):
            print(chunk)
    """

    def __init__(
        self,
        use_singleton: bool = True,
        persistence_adapter: Optional[PersistenceAdapter] = None,
    ):
        """
        初始化 GraphManager

        Args:
            use_singleton: 是否使用单例图，默认 True
            persistence_adapter: 持久化适配器（可选，默认使用 MySQL 适配器）
        """
        if use_singleton:
            self.graph = get_medical_graph()
        else:
            self.graph = create_medical_graph()

        self.checkpointer = get_checkpointer()
        self.thread_id_manager = ThreadIDManager()

        # 初始化持久化适配器
        self.persistence = persistence_adapter or self._create_default_adapter()

        logger.info("[GraphManager] 初始化完成")

    def _create_default_adapter(self) -> PersistenceAdapter:
        """
        创建默认的持久化适配器（MySQL）

        Returns:
            MySQLPersistenceAdapter 实例
        """
        try:
            from agents.graph.mysql_persistence_adapter import get_mysql_persistence_adapter
            return get_mysql_persistence_adapter()
        except Exception as e:
            logger.warning(
                "[GraphManager] 创建 MySQL 适配器失败，使用空适配器, "
                "error_type=%s",
                type(e).__name__,
            )
            return NullPersistenceAdapter()

    def chat(
        self,
        patient_id: Optional[str],
        session_id: str,
        message: str,
        role: str = "patient",
        doctor_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        agent_type: str = "health",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        同步对话接口

        Args:
            patient_id: 患者UUID
            session_id: 会话ID
            message: 用户消息
            role: 用户角色 ("patient" | "doctor")
            doctor_id: 医生UUID（医生模式）
            conversation_id: 数据库会话ID（继续对话）
            agent_type: 初始 Agent 类型
            **kwargs: 其他状态参数

        Returns:
            包含响应和状态的字典:
            {
                "response": str,
                "agent_type": str,
                "stage": str,
                "is_completed": bool,
                "thread_id": str,
            }
        """
        # 获取线程配置
        thread_config = get_thread_config(session_id, conversation_id)
        thread_id = thread_config["configurable"]["thread_id"]

        logger.info("[GraphManager] chat started, agent_type=%s", agent_type)

        # === 安全检查：角色校验 + 输入防护 ===
        from utils.role_verification import verify_role
        from utils.input_guard import check_input_safety, RiskLevel, HIGH_RISK_RESPONSE, LOW_RISK_RESPONSE

        verified_role, was_downgraded = verify_role(
            role,
            patient_id,
            doctor_id,
            allow_same_identity=agent_type == "research",
        )
        if was_downgraded:
            logger.warning(
                "[GraphManager] 角色降级: %s -> %s",
                role,
                verified_role,
            )
            role = verified_role
            if agent_type in ("compliance", "research"):
                agent_type = "health"

        try:
            legacy_authority = _resolve_legacy_text_turn_authority(
                agent_type=agent_type,
                patient_id=patient_id,
                role=role,
                branch_mode="normal",
                prepared_mode=False,
                kwargs=kwargs,
            )
        except ValueError:
            return {
                "response": _PUBLIC_CHAT_ERROR_MESSAGE,
                "agent_type": agent_type,
                "stage": "error",
                "is_completed": False,
                "thread_id": thread_id,
                "error_code": _CHAT_SOURCE_INVALID,
            }

        guard_result = check_input_safety(message, context={
            "role": role, "agent_type": agent_type, "patient_id": patient_id,
        })
        if not guard_result.is_safe:
            logger.warning(
                "[GraphManager] 安全拦截: risk=%s, category=%s",
                guard_result.risk_level.value,
                guard_result.category.value if guard_result.category else "N/A",
            )
            blocked_response = HIGH_RISK_RESPONSE if guard_result.risk_level == RiskLevel.HIGH else LOW_RISK_RESPONSE
            return {
                "response": blocked_response,
                "agent_type": agent_type,
                "stage": "security_blocked",
                "is_completed": guard_result.risk_level == RiskLevel.HIGH,
                "thread_id": thread_id,
            }

        # === 两阶段写入 - 第一阶段：保存用户消息 ===
        assistant_msg_id = None
        if conversation_id:
            try:
                # 判断是否首条消息
                is_first = self.persistence.is_first_message(conversation_id)

                # 确定发送者 ID
                sender_id = doctor_id if role == "doctor" else patient_id

                # 构建用户消息上下文
                user_context = _legacy_user_context(
                    stage="greeting" if is_first else None,
                    agent_type=agent_type,
                    patient_id=patient_id,
                    authority=legacy_authority,
                )

                # 保存用户消息
                self.persistence.save_user_message(
                    chat_id=conversation_id,
                    content=message,
                    sender_id=sender_id,
                    context=user_context,
                    is_first_message=is_first,
                )

                # 创建 AI 回复占位
                assistant_msg_id = self.persistence.create_assistant_placeholder(
                    chat_id=conversation_id,
                    context={"stage": agent_type, "agent_type": agent_type},
                )

                logger.debug("[GraphManager] 两阶段写入 - 用户消息与 AI 占位已保存")

            except Exception as e:
                logger.error(
                    "[GraphManager] 保存用户消息失败, error_type=%s",
                    type(e).__name__,
                )
                # 持久化失败不影响对话，继续执行

        # 准备输入状态
        input_state = self._prepare_input_state(
            patient_id=patient_id,
            session_id=session_id,
            message=message,
            role=role,
            doctor_id=doctor_id,
            conversation_id=conversation_id,
            agent_type=agent_type,
            **kwargs,
        )

        try:
            # 获取当前 Agent（切换前）
            previous_agent = self.checkpointer.get_current_agent(thread_id)
            previous_message_count = self._get_state_message_count(self.graph, thread_config)

            # 调用图
            result = self.graph.invoke(
                input_state,
                config=thread_config,
            )

            # 提取响应和本轮 token usage
            response = self._extract_response(result)
            token_used = self._extract_token_used_from_result(result, previous_message_count)

            # 获取结果中的 Agent 类型
            current_agent = result.get("current_agent", agent_type)
            current_stage = result.get("stage", "greeting")
            citations = self._extract_citations(result, previous_message_count)

            # === 两阶段写入 - 第二阶段：更新 AI 回复为成功 ===
            if assistant_msg_id and conversation_id:
                try:
                    # 提取工具调用结果，CitationBlock 来源已在落库前统一抽取
                    tool_results = self._extract_tool_results(result, previous_message_count)

                    self.persistence.update_assistant_success(
                        message_id=assistant_msg_id,
                        content=response,
                        token_used=token_used,
                        tool_results=tool_results,
                        citations=citations,
                        context={
                            "stage": current_stage,
                            "agent_type": current_agent,
                        },
                    )
                    logger.debug("[GraphManager] 两阶段写入 - AI 回复已更新")

                except Exception as e:
                    logger.error(
                        "[GraphManager] 更新 AI 回复失败, error_type=%s",
                        type(e).__name__,
                    )

            # 检测 Agent 切换并记录历史
            if previous_agent is None:
                # 首次使用，记录初始 Agent
                self.checkpointer.record_agent_switch(
                    thread_id=thread_id,
                    new_agent_type=current_agent,
                    checkpoint_id=thread_config["configurable"].get("checkpoint_id"),
                )
            elif previous_agent != current_agent:
                # Agent 发生切换，记录切换历史
                self.checkpointer.record_agent_switch(
                    thread_id=thread_id,
                    new_agent_type=current_agent,
                    checkpoint_id=thread_config["configurable"].get("checkpoint_id"),
                )
                logger.info(
                    "[GraphManager] Agent 切换: %s -> %s",
                    previous_agent,
                    current_agent,
                )

            # 保存线程映射（agent_type 为主要 Agent）
            self.checkpointer.save_thread_mapping(
                thread_id=thread_id,
                patient_id=patient_id,
                conversation_id=conversation_id,
                session_id=session_id,
                doctor_id=doctor_id,
                agent_type=current_agent,
            )

            return {
                "response": response,
                "agent_type": current_agent,
                "stage": current_stage,
                "is_completed": result.get("is_completed", False),
                "thread_id": thread_id,
                "citations": citations,
            }

        except Exception as e:
            # === 两阶段写入 - 失败处理：更新 AI 回复为失败 ===
            if assistant_msg_id and conversation_id:
                try:
                    self.persistence.update_assistant_failed(
                        message_id=assistant_msg_id,
                        error_message=_CHAT_EXECUTION_FAILED,
                    )
                    logger.debug("[GraphManager] 两阶段写入 - AI 回复标记失败")
                except Exception as pe:
                    logger.error(
                        "[GraphManager] 更新 AI 失败状态失败, error_type=%s",
                        type(pe).__name__,
                    )

            logger.error(
                "[GraphManager] chat 失败, error_type=%s",
                type(e).__name__,
            )
            return {
                "response": "抱歉，我遇到了一些技术问题，请稍后再试。",
                "agent_type": agent_type,
                "stage": "error",
                "is_completed": False,
                "thread_id": thread_id,
                "error_code": _CHAT_EXECUTION_FAILED,
            }

    def chat_stream(
        self,
        patient_id: str,
        session_id: str,
        message: str,
        role: str = "patient",
        doctor_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        agent_type: str = "health",
        **kwargs,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        流式对话接口

        Args:
            (同 chat 方法)

        Yields:
            流式响应块:
            {
                "type": "token" | "tool_call" | "tool_result" | "done",
                "content": str,
                "metadata": dict,
            }
        """
        # 获取线程配置
        thread_config = get_thread_config(session_id, conversation_id)
        thread_id = thread_config["configurable"]["thread_id"]

        logger.info("[GraphManager] chat_stream started, agent_type=%s", agent_type)

        # === 安全检查：角色校验 + 输入防护 ===
        from utils.role_verification import verify_role
        from utils.input_guard import check_input_safety, RiskLevel, HIGH_RISK_RESPONSE, LOW_RISK_RESPONSE

        verified_role, was_downgraded = verify_role(
            role,
            patient_id,
            doctor_id,
            allow_same_identity=agent_type == "research",
        )
        if was_downgraded:
            logger.warning(
                "[GraphManager] 角色降级: %s -> %s",
                role,
                verified_role,
            )
            role = verified_role
            if agent_type in ("compliance", "research"):
                agent_type = "health"

        try:
            legacy_authority = _resolve_legacy_text_turn_authority(
                agent_type=agent_type,
                patient_id=patient_id,
                role=role,
                branch_mode="normal",
                prepared_mode=False,
                kwargs=kwargs,
            )
        except ValueError:
            yield {
                "type": "error",
                "content": _PUBLIC_CHAT_ERROR_MESSAGE,
                "metadata": {"error_code": _CHAT_SOURCE_INVALID},
            }
            return

        guard_result = check_input_safety(message, context={
            "role": role, "agent_type": agent_type, "patient_id": patient_id,
        })
        if not guard_result.is_safe:
            logger.warning(
                f"[GraphManager] 安全拦截(stream): risk={guard_result.risk_level.value}, "
                f"category={guard_result.category.value if guard_result.category else 'N/A'}"
            )
            blocked_response = HIGH_RISK_RESPONSE if guard_result.risk_level == RiskLevel.HIGH else LOW_RISK_RESPONSE
            yield {
                "type": "token",
                "content": blocked_response,
                "metadata": {"security_blocked": True, "risk": guard_result.risk_level.value},
            }
            yield {
                "type": "done",
                "content": "",
                "metadata": {"security_blocked": True},
            }
            return

        # === 两阶段写入 - 第一阶段：保存用户消息 ===
        assistant_msg_id = None
        if conversation_id:
            try:
                is_first = self.persistence.is_first_message(conversation_id)
                sender_id = doctor_id if role == "doctor" else patient_id

                user_context = _legacy_user_context(
                    stage="greeting" if is_first else None,
                    agent_type=agent_type,
                    patient_id=patient_id,
                    authority=legacy_authority,
                )

                self.persistence.save_user_message(
                    chat_id=conversation_id,
                    content=message,
                    sender_id=sender_id,
                    context=user_context,
                    is_first_message=is_first,
                )

                assistant_msg_id = self.persistence.create_assistant_placeholder(
                    chat_id=conversation_id,
                    context={"stage": agent_type, "agent_type": agent_type},
                )

            except Exception as e:
                logger.error(
                    "[GraphManager] 流式 - 保存用户消息失败, error_type=%s",
                    type(e).__name__,
                )

        # 准备输入状态
        input_state = self._prepare_input_state(
            patient_id=patient_id,
            session_id=session_id,
            message=message,
            role=role,
            doctor_id=doctor_id,
            conversation_id=conversation_id,
            agent_type=agent_type,
            **kwargs,
        )

        # 用于拼接完整响应
        full_response = ""
        current_stage = "greeting"
        current_agent = agent_type
        stream_error = None
        token_used = None

        try:
            # 流式调用图
            for event in self.graph.stream(
                input_state,
                config=thread_config,
                stream_mode="updates",
            ):
                # 处理不同类型的事件
                for node_name, node_output in event.items():
                    if node_name == "__end__":
                        yield {
                            "type": "done",
                            "content": "",
                            "metadata": {"node": node_name},
                        }
                        continue

                    # 更新阶段和 Agent 类型
                    if node_output.get("stage"):
                        current_stage = node_output["stage"]
                    if node_output.get("current_agent"):
                        current_agent = node_output["current_agent"]

                    # 提取消息
                    messages = node_output.get("messages", [])
                    for msg in messages:
                        if isinstance(msg, AIMessage):
                            token_used = merge_token_used(
                                token_used,
                                extract_token_used_from_ai_message(msg),
                            )
                            full_response += msg.content
                            yield {
                                "type": "token",
                                "content": msg.content,
                                "metadata": {
                                    "node": node_name,
                                    "stage": node_output.get("stage", ""),
                                },
                            }

                    # 工具调用信息
                    if "tool_calls" in str(node_output):
                        yield {
                            "type": "tool_call",
                            "content": "",
                            "metadata": {"node": node_name},
                        }

            # 保存线程映射
            self.checkpointer.save_thread_mapping(
                thread_id=thread_id,
                patient_id=patient_id,
                conversation_id=conversation_id,
                session_id=session_id,
                doctor_id=doctor_id,
                agent_type=current_agent,
            )

        except Exception as e:
            stream_error = e
            logger.error(
                "[GraphManager] chat_stream 失败, error_type=%s",
                type(e).__name__,
            )
            yield {
                "type": "error",
                "content": _PUBLIC_CHAT_ERROR_MESSAGE,
                "metadata": {"error_code": _CHAT_EXECUTION_FAILED},
            }

        # === 两阶段写入 - 第二阶段：流结束后保存完整回复 ===
        if assistant_msg_id and conversation_id:
            try:
                if stream_error:
                    self.persistence.update_assistant_failed(
                        message_id=assistant_msg_id,
                        error_message=_CHAT_EXECUTION_FAILED,
                    )
                else:
                    self.persistence.update_assistant_success(
                        message_id=assistant_msg_id,
                        content=full_response,
                        token_used=token_used,
                        tool_results=None,
                        context={
                            "stage": current_stage,
                            "agent_type": current_agent,
                        },
                    )
                    logger.debug("[GraphManager] 流式 - AI 回复已保存")

            except Exception as e:
                logger.error(
                    "[GraphManager] 流式 - 保存 AI 回复失败, error_type=%s",
                    type(e).__name__,
                )

    async def chat_stream_prepared_async(
        self,
        *,
        patient_id: Optional[str],
        doctor_id: str,
        session_id: str,
        conversation_id: str,
        message: str,
        user_message_id: str,
        assistant_message_id: str,
        safe_attachment_refs: List[Dict[str, Any]],
        agent_type: str,
        research_options: Optional[Dict[str, Any]],
        health_handle: Optional[str] = None,
        research_handle: Optional[str] = None,
        runnable_config: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[PreparedGraphEvent, None]:
        """复用模型流，但只消费 prepare 已创建的节点并返回内部终态。"""
        allowed_ref_fields = {
            "attachment_id",
            "document_version",
            "content_sha256",
            "page_count",
        }
        if (
            not safe_attachment_refs
            or any(
                not isinstance(ref, dict)
                or set(ref) != allowed_ref_fields
                or not isinstance(ref.get("attachment_id"), str)
                or not ref["attachment_id"]
                for ref in safe_attachment_refs
            )
        ):
            raise ValueError("ATTACHMENT_SAFE_REF_INVALID")
        config = runnable_config or {}
        configurable = config.setdefault("configurable", {})
        if not isinstance(configurable, dict):
            raise ValueError("ATTACHMENT_CONTEXT_UNAVAILABLE")

        prepared_options: Dict[str, Any] = {}
        if agent_type == "health":
            if (
                not isinstance(patient_id, str)
                or not patient_id
                or research_options is not None
                or not isinstance(health_handle, str)
                or not health_handle
                or research_handle is not None
                or configurable.get("attachment_analysis_handle")
                != health_handle
            ):
                raise ValueError("ATTACHMENT_CONTEXT_INCONSISTENT")
            get_attachment_analysis(config)
            transient_config_key = "attachment_analysis_handle"
            transient_handle = health_handle
        elif agent_type == "research":
            prepared_options = _validate_prepared_research_options(
                research_options
            )
            if (
                patient_id is not None
                or health_handle is not None
                or not isinstance(research_handle, str)
                or not research_handle
                or configurable.get("research_document_context_handle")
                != research_handle
            ):
                raise ValueError("RESEARCH_DOCUMENT_CONTEXT_INCONSISTENT")
            get_research_document_context(config)
            transient_config_key = None
            transient_handle = None
        else:
            raise ValueError("PREPARED_AGENT_TYPE_INVALID")

        prepared_context = {
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
            "safe_attachment_refs": list(safe_attachment_refs),
            "transient_config_key": transient_config_key,
            "transient_handle": transient_handle,
        }
        async for event in self.chat_stream_async(
            patient_id=patient_id,
            session_id=session_id,
            message=message,
            role="doctor",
            doctor_id=doctor_id,
            conversation_id=conversation_id,
            agent_type=agent_type,
            enable_institution_data=prepared_options.get(
                "enable_institution_data",
                False,
            ),
            enable_web_search=prepared_options.get(
                "enable_web_search",
                False,
            ),
            web_search_types=prepared_options.get("types", []),
            _prepared_context=prepared_context,
        ):
            yield event

    async def chat_stream_async(
        self,
        patient_id: Optional[str],
        session_id: str,
        message: str,
        role: str = "patient",
        doctor_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        agent_type: str = "health",
        source_message_id: Optional[str] = None,
        branch_mode: str = "normal",
        **kwargs,
    ) -> AsyncGenerator[PreparedGraphEvent, None]:
        """
        异步流式对话接口 - Token 级别流式输出

        使用 astream_events API 实现真正的打字机效果。

        Args:
            (同 chat 方法)

        Yields:
            流式响应块:
            {
                "type": "token" | "node_start" | "node_end" | "tool_start" | "tool_end" | "done" | "error",
                "content": str,
                "metadata": dict,
            }
        """
        from agents.graph.graph_builder import get_streaming_medical_graph

        prepared_context = kwargs.pop("_prepared_context", None)
        prepared_mode = isinstance(prepared_context, dict)

        # 获取线程配置
        thread_config = get_thread_config(session_id, conversation_id)
        thread_id = thread_config["configurable"]["thread_id"]

        logger.info(
            "[GraphManager] chat_stream_async started, agent_type=%s",
            agent_type,
        )

        allowed_branch_modes = {"normal", "edit", "regenerate"}
        if branch_mode not in allowed_branch_modes:
            yield {
                "type": "error",
                "content": _PUBLIC_CHAT_ERROR_MESSAGE,
                "metadata": {"error_code": _CHAT_SOURCE_INVALID},
            }
            return

        regenerate_user_message_id = None
        if branch_mode == "regenerate":
            if not conversation_id or not source_message_id:
                yield {
                    "type": "error",
                    "content": _PUBLIC_CHAT_ERROR_MESSAGE,
                    "metadata": {"error_code": _CHAT_SOURCE_INVALID},
                }
                return
            try:
                regenerate_user = self._get_user_message_for_regenerate(
                    conversation_id,
                    source_message_id,
                )
                message = regenerate_user.message_content
                regenerate_user_message_id = regenerate_user.id
            except Exception as e:
                logger.error(
                    "[GraphManager] 重新生成 - 获取原始用户问题失败, "
                    "error_type=%s",
                    type(e).__name__,
                )
                yield {
                    "type": "error",
                    "content": _PUBLIC_CHAT_ERROR_MESSAGE,
                    "metadata": {"error_code": _CHAT_SOURCE_INVALID},
                }
                return
        elif branch_mode == "edit" and not source_message_id:
            yield {
                "type": "error",
                "content": _PUBLIC_CHAT_ERROR_MESSAGE,
                "metadata": {"error_code": _CHAT_SOURCE_INVALID},
            }
            return

        # === 安全检查：角色校验 + 输入防护 ===
        from utils.role_verification import verify_role
        from utils.input_guard import check_input_safety, RiskLevel, HIGH_RISK_RESPONSE, LOW_RISK_RESPONSE

        verified_role, was_downgraded = verify_role(
            role,
            patient_id,
            doctor_id,
            allow_same_identity=agent_type == "research",
        )
        if was_downgraded:
            if prepared_mode:
                raise ValueError("PREPARED_ROLE_INVALID")
            logger.warning(
                "[GraphManager] 角色降级: %s -> %s",
                role,
                verified_role,
            )
            role = verified_role
            if agent_type in ("compliance", "research"):
                agent_type = "health"

        try:
            legacy_authority = _resolve_legacy_text_turn_authority(
                agent_type=agent_type,
                patient_id=patient_id,
                role=role,
                branch_mode=branch_mode,
                prepared_mode=prepared_mode,
                kwargs=kwargs,
            )
        except ValueError:
            yield {
                "type": "error",
                "content": _PUBLIC_CHAT_ERROR_MESSAGE,
                "metadata": {"error_code": _CHAT_SOURCE_INVALID},
            }
            return

        # === 运行时状态：用于 finally 中统一终态落库 ===
        assistant_message_id = None
        full_response = ""
        stream_completed = False
        cancelled = False
        last_error = None
        token_used = None
        usage_event_run_ids = set()
        previous_message_count = 0
        prepared_message_ids = {}
        branch_history_messages = None
        current_agent = agent_type
        current_stage = "greeting"

        # Prepared path 只绑定已存在的节点；legacy path 仍由这里创建节点。
        if prepared_mode:
            prepared_message_ids = {
                "user_message_id": prepared_context["user_message_id"],
                "assistant_message_id": prepared_context["assistant_message_id"],
            }
            assistant_message_id = prepared_message_ids["assistant_message_id"]
            thread_config = get_branch_thread_config(
                session_id,
                conversation_id,
                assistant_message_id,
            )
            transient_key = prepared_context.get("transient_config_key")
            transient_handle = prepared_context.get("transient_handle")
            if transient_key is not None and transient_handle is not None:
                thread_config["configurable"][transient_key] = transient_handle
            thread_id = thread_config["configurable"]["thread_id"]
            branch_history_messages = self._build_branch_history_messages(
                conversation_id=conversation_id,
                current_user_message_id=prepared_message_ids["user_message_id"],
                current_assistant_message_id=assistant_message_id,
            )
        elif conversation_id:
            try:
                is_first = self.persistence.is_first_message(conversation_id)
                sender_id = doctor_id if role == "doctor" else patient_id

                if branch_mode == "edit":
                    prepared_message_ids = self.persistence.prepare_edit_resend_turn(
                        chat_id=conversation_id,
                        source_message_id=source_message_id,
                        content=message,
                        sender_id=sender_id,
                        context=_legacy_user_context(
                            stage=None,
                            agent_type=agent_type,
                            patient_id=patient_id,
                            authority=legacy_authority,
                        ),
                        expected_authority=legacy_authority,
                    )
                elif branch_mode == "regenerate":
                    prepared_message_ids = self.persistence.prepare_regenerate_turn(
                        chat_id=conversation_id,
                        source_assistant_id=source_message_id,
                        context={
                            "stage": None,
                            "agent_type": agent_type,
                            "patient_id": patient_id,
                        },
                        doctor_id=doctor_id,
                        expected_authority=legacy_authority,
                    )
                    prepared_message_ids.setdefault("user_message_id", regenerate_user_message_id)
                else:
                    prepared_message_ids = self.persistence.prepare_normal_turn(
                        chat_id=conversation_id,
                        content=message,
                        sender_id=sender_id,
                        context=_legacy_user_context(
                            stage="greeting" if is_first else None,
                            agent_type=agent_type,
                            patient_id=patient_id,
                            authority=legacy_authority,
                        ),
                        is_first_message=is_first,
                    )
                assistant_message_id = prepared_message_ids.get("assistant_message_id")
                if assistant_message_id:
                    thread_config = get_branch_thread_config(
                        session_id,
                        conversation_id,
                        assistant_message_id,
                    )
                    thread_id = thread_config["configurable"]["thread_id"]
                    branch_history_messages = (
                        self._build_branch_history_messages(
                            conversation_id=conversation_id,
                            current_user_message_id=prepared_message_ids.get(
                                "user_message_id"
                            ),
                            current_assistant_message_id=assistant_message_id,
                        )
                    )

            except Exception as e:
                logger.error(
                    "[GraphManager] 流式 - 准备消息树节点失败, error_type=%s",
                    type(e).__name__,
                )
                yield {
                    "type": "error",
                    "content": _PUBLIC_CHAT_ERROR_MESSAGE,
                    "metadata": {"error_code": _CHAT_PERSISTENCE_FAILED},
                }
                return

        if not prepared_mode:
            yield {
                "type": "start",
                "content": "",
                "metadata": {
                    "conversation_id": conversation_id,
                    "thread_id": thread_id,
                    "user_message_id": prepared_message_ids.get("user_message_id"),
                    "assistant_message_id": prepared_message_ids.get("assistant_message_id"),
                    "active_node_id": prepared_message_ids.get("assistant_message_id"),
                },
            }

        guard_result = check_input_safety(message, context={
            "role": role, "agent_type": agent_type, "patient_id": patient_id,
        })
        if not guard_result.is_safe:
            logger.warning(
                f"[GraphManager] 安全拦截(async_stream): risk={guard_result.risk_level.value}, "
                f"category={guard_result.category.value if guard_result.category else 'N/A'}"
            )
            blocked_response = HIGH_RISK_RESPONSE if guard_result.risk_level == RiskLevel.HIGH else LOW_RISK_RESPONSE
            if assistant_message_id and conversation_id and not prepared_mode:
                try:
                    self.persistence.update_assistant_success(
                        message_id=assistant_message_id,
                        content=blocked_response,
                        context={
                            "stage": "security_blocked",
                            "agent_type": agent_type,
                        },
                    )
                except Exception as e:
                    logger.error(
                        "[GraphManager] 流式 - 保存安全拦截回复失败, "
                        "error_type=%s",
                        type(e).__name__,
                    )
            yield {
                "type": "token",
                "content": blocked_response,
                "metadata": {"security_blocked": True, "risk": guard_result.risk_level.value},
            }
            if prepared_mode:
                yield PreparedGraphTerminal(
                    content=blocked_response,
                    token_used=None,
                    tool_results=[],
                    citations=[],
                    agent_type=agent_type,
                    stage="security_blocked",
                )
            else:
                yield {
                    "type": "done",
                    "content": blocked_response,
                    "metadata": {
                        "security_blocked": True,
                        "agent_type": agent_type,
                        "stage": "security_blocked",
                    },
                }
            return

        # 准备输入状态（标记流式模式）
        input_kwargs = dict(kwargs)
        if branch_history_messages is not None:
            input_kwargs["history_messages"] = branch_history_messages
        if prepared_mode:
            input_kwargs.update(
                {
                    "platform_prepared": True,
                    "attachments": prepared_context["safe_attachment_refs"],
                    "attachment_analysis": None,
                }
            )
        input_state = self._prepare_input_state(
            patient_id=patient_id,
            session_id=session_id,
            message=message,
            role=role,
            doctor_id=doctor_id,
            conversation_id=conversation_id,
            agent_type=agent_type,
            is_streaming=True,  # 关键：标记流式模式
            **input_kwargs,
        )

        streaming_graph = None

        # 收集工具调用事件，流结束后持久化到 context.tool_results
        collected_tool_calls: List[Dict[str, Any]] = []
        # 收集搜索工具来源，流结束后持久化到 context.citations
        collected_citations: List[Dict[str, Any]] = []
        collected_attachment_citations: List[Dict[str, Any]] = []
        collected_statistics_citations: List[Dict[str, Any]] = []
        citation_tool_seen = False
        statistics_tool_seen = False
        redact_research_tool_payload = (
            prepared_mode and agent_type == "research"
        )

        try:
            streaming_graph = get_streaming_medical_graph()
            previous_message_count = self._get_state_message_count(streaming_graph, thread_config)

            async for event in streaming_graph.astream_events(
                input_state,
                config=thread_config,
                version="v2",
            ):
                event_type = event.get("event", "")

                # 模型结束事件携带完整 AIMessage/metadata，是流式 usage 的最可靠来源。
                if event_type == "on_chat_model_end":
                    event_run_id = event.get("run_id")
                    if event_run_id is None or event_run_id not in usage_event_run_ids:
                        incoming_token_used = extract_token_used_from_stream_event(event)
                        token_used = merge_token_used(token_used, incoming_token_used)
                        if incoming_token_used is not None and event_run_id is not None:
                            usage_event_run_ids.add(event_run_id)

                # Token 流式输出
                if event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        full_response += chunk.content
                        yield {
                            "type": "token",
                            "content": chunk.content,
                            "metadata": {"node": current_agent},
                        }

                # 节点开始
                elif event_type == "on_chain_start":
                    node_name = event.get("name", "")
                    if node_name in ["health", "report", "reminder", "research"]:
                        current_agent = node_name
                        yield {
                            "type": "node_start",
                            "content": "",
                            "metadata": {"node": node_name},
                        }

                # 节点结束
                elif event_type == "on_chain_end":
                    node_name = event.get("name", "")
                    if node_name in ["health", "report", "reminder", "research"]:
                        output = event.get("data", {}).get("output", {})
                        if isinstance(output, dict) and output.get("stage"):
                            current_stage = output["stage"]
                        yield {
                            "type": "node_end",
                            "content": "",
                            "metadata": {"node": node_name, "stage": current_stage},
                        }

                # 工具调用开始。在 LangGraph 流式事件序列中，
                # agent 节点先通过 on_chat_model_stream 流式输出前置文本，
                # 然后 emit AIMessage(tool_calls)，再路由到 ToolNode 触发 on_tool_start。
                # 因此用此时的 full_response 长度作为 text_offset，
                # 持久化后前端可在该位置精确切分"前置文本"与"工具调用"，恢复流式 block 顺序。
                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    if (
                        redact_research_tool_payload
                        and tool_name == CITATION_TOOL_NAME
                    ):
                        citation_tool_seen = True
                    if (
                        redact_research_tool_payload
                        and tool_name == "statistical_analysis"
                    ):
                        statistics_tool_seen = True
                    tool_input = event.get("data", {}).get("input", {})
                    retained_tool_input = (
                        {} if redact_research_tool_payload else tool_input
                    )
                    collected_tool_calls.append({
                        "tool": tool_name,
                        "status": "start",
                        "input": retained_tool_input,
                        "text_offset": len(full_response),
                    })
                    yield {
                        "type": "tool_start",
                        "content": "",
                        "metadata": {
                            "tool": tool_name,
                            "input": retained_tool_input,
                        },
                    }

                # 工具调用结束。匹配 tool_start 设置的条目，
                # 把 status/input 升级为 end/output，text_offset 保留不变；
                # 若找不到匹配(异常序列)，用当前文本位置兜底附加。
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    raw_tool_output = event.get("data", {}).get("output", "")
                    if (
                        redact_research_tool_payload
                        and tool_name == CITATION_TOOL_NAME
                    ):
                        citation_tool_seen = True
                        research_context = get_research_document_context()
                        collected_attachment_citations.extend(
                            extract_attachment_citations_from_tool_output(
                                raw_tool_output,
                                research_context.selection.citation_candidates,
                            )
                        )
                    elif (
                        redact_research_tool_payload
                        and tool_name == "statistical_analysis"
                    ):
                        statistics_tool_seen = True
                        research_context = get_research_document_context()
                        collected_statistics_citations.extend(
                            extract_attachment_citations_from_statistics_output(
                                raw_tool_output,
                                research_context.selection.citation_candidates,
                            )
                        )
                    elif self._is_search_tool(tool_name) or self._looks_like_search_results(raw_tool_output):
                        collected_citations.extend(
                            extract_citations_from_search_results(raw_tool_output)
                        )
                    tool_output = (
                        ""
                        if redact_research_tool_payload
                        else str(raw_tool_output)[:500]
                    )
                    for tc in reversed(collected_tool_calls):
                        if tc.get("tool") == tool_name and tc.get("status") == "start":
                            tc["status"] = "end"
                            tc["output"] = tool_output
                            break
                    else:
                        collected_tool_calls.append({
                            "tool": tool_name,
                            "status": "end",
                            "output": tool_output,
                            "text_offset": len(full_response),
                        })
                    yield {
                        "type": "tool_end",
                        "content": "",
                        "metadata": {
                            "tool": tool_name,
                            "output": tool_output,
                        },
                    }

            # 保存线程映射
            mapping_saved = self.checkpointer.save_thread_mapping(
                thread_id=thread_id,
                patient_id=patient_id,
                conversation_id=conversation_id,
                session_id=session_id,
                doctor_id=doctor_id,
                agent_type=current_agent,
            )
            if prepared_mode and mapping_saved is not True:
                error = RuntimeError("PREPARED_THREAD_MAPPING_FAILED")
                error.error_code = "PREPARED_THREAD_MAPPING_FAILED"
                raise error

        except (asyncio.CancelledError, GeneratorExit) as e:
            cancelled = True
            last_error = e
            logger.info("[GraphManager] chat_stream_async 已取消")
            raise

        except Exception as e:
            last_error = e
            if prepared_mode:
                logger.error(
                    "[GraphManager] prepared graph 失败, error_type=%s",
                    type(e).__name__,
                )
                raise
            logger.error(
                "[GraphManager] chat_stream_async 失败, error_type=%s",
                type(e).__name__,
            )
            yield {
                "type": "error",
                "content": _PUBLIC_CHAT_ERROR_MESSAGE,
                "metadata": {"error_code": _CHAT_EXECUTION_FAILED},
            }
            return

        finally:
            # best-effort：取消或异常时，尽量把 running 占位推进到最终状态。
            if (
                not prepared_mode
                and assistant_message_id
                and conversation_id
                and (cancelled or last_error)
            ):
                try:
                    final_status = "cancelled" if cancelled else "failed"
                    error_message = (
                        "client disconnected"
                        if cancelled
                        else _CHAT_EXECUTION_FAILED
                    )
                    self.persistence.update_assistant_final_status(
                        message_id=assistant_message_id,
                        status=final_status,
                        content=full_response,
                        error_message=error_message,
                        token_used=token_used,
                        tool_results=(
                            normalize_from_stream_events(collected_tool_calls)
                            if collected_tool_calls else None
                        ),
                        citations=(
                            deduplicate_citations(collected_citations)
                            if collected_citations else None
                        ),
                        context={
                            "stage": current_stage,
                            "agent_type": current_agent,
                        },
                    )
                    logger.info(
                        "[GraphManager] 流式 - AI 回复终态已保存, status=%s",
                        final_status,
                    )
                except Exception as persist_error:
                    logger.error(
                        "[GraphManager] 流式 - 保存 AI 回复终态失败, "
                        "error_type=%s",
                        type(persist_error).__name__,
                    )

        # 兜底：节点内部使用阻塞 agent.invoke 时，astream_events 捕获不到 on_chat_model_stream，
        # full_response 会为空。此时从最终状态取 last_response 补发一次，保证回复能到达前端。
        if not full_response and not last_error and streaming_graph is not None:
            try:
                final_state = streaming_graph.get_state(thread_config)
                fallback_resp = ""
                if final_state and getattr(final_state, "values", None):
                    final_values = final_state.values
                    fallback_resp = final_values.get("last_response", "") or ""
                    if token_used is None:
                        token_used = self._extract_token_used_from_result(
                            final_values,
                            previous_message_count,
                        )
                if fallback_resp:
                    full_response = fallback_resp
                    logger.info(
                        f"[GraphManager] 流式未捕获 token，回退 last_response（{len(fallback_resp)} 字）"
                    )
                    yield {
                        "type": "token",
                        "content": fallback_resp,
                        "metadata": {"node": current_agent},
                    }
            except Exception as e:
                if prepared_mode:
                    logger.warning(
                        "[GraphManager] prepared fallback 失败, error_type=%s",
                        type(e).__name__,
                    )
                else:
                    logger.warning(
                        "[GraphManager] 流式回退 last_response 失败, error_type=%s",
                        type(e).__name__,
                    )

        if token_used is None and not last_error and streaming_graph is not None:
            try:
                final_state = streaming_graph.get_state(thread_config)
                if final_state and getattr(final_state, "values", None):
                    token_used = self._extract_token_used_from_result(
                        final_state.values,
                        previous_message_count,
                    )
            except Exception as e:
                if prepared_mode:
                    logger.debug(
                        "[GraphManager] prepared token usage 回退失败, error_type=%s",
                        type(e).__name__,
                    )
                else:
                    logger.debug(
                        "[GraphManager] 流式回退提取 token_used 失败, "
                        "error_type=%s",
                        type(e).__name__,
                    )

        stream_completed = not last_error and not cancelled

        # === 两阶段写入 - 第二阶段：流结束后保存完整回复 ===
        if (
            not prepared_mode
            and assistant_message_id
            and conversation_id
            and stream_completed
        ):
            try:
                self.persistence.update_assistant_success(
                    message_id=assistant_message_id,
                    content=full_response,
                    token_used=token_used,
                    tool_results=(
                        normalize_from_stream_events(collected_tool_calls)
                        if collected_tool_calls else None
                    ),
                    citations=(
                        deduplicate_citations(collected_citations)
                        if collected_citations else None
                    ),
                    context={
                        "stage": current_stage,
                        "agent_type": current_agent,
                    },
                )
                logger.debug("[GraphManager] 流式 - AI 回复已保存")

            except Exception as e:
                logger.error(
                    "[GraphManager] 流式 - 保存 AI 回复失败, error_type=%s",
                    type(e).__name__,
                )

        if prepared_mode and agent_type == "research":
            research_context = get_research_document_context()
            fallback_citations = build_attachment_citation_fallback(
                research_context.selection.citation_candidates
            )
            if (
                not citation_tool_seen
                and not statistics_tool_seen
                and not collected_attachment_citations
                and not collected_statistics_citations
            ):
                collected_attachment_citations = fallback_citations

        final_citations = merge_citations(
            collected_citations,
            [
                *collected_statistics_citations,
                *collected_attachment_citations,
            ],
        )
        if prepared_mode:
            yield PreparedGraphTerminal(
                content=full_response,
                token_used=token_used,
                tool_results=(
                    normalize_from_stream_events(collected_tool_calls)
                    if collected_tool_calls else []
                ),
                citations=final_citations,
                agent_type=current_agent,
                stage=current_stage,
            )
            return

        # legacy path 的 public done 保持原行为。
        yield {
            "type": "done",
            "content": full_response,
            "citations": final_citations,
            "metadata": {
                "agent_type": current_agent,
                "stage": current_stage,
                "citations": final_citations,
            },
        }

    def _get_user_message_for_regenerate(self, conversation_id: str, source_assistant_id: str):
        message = self.persistence.service.message_repo.get_by_id(source_assistant_id)
        if message and message.chat_id != conversation_id:
            raise ValueError("source_assistant_id 必须是当前会话的助手消息")
        if not message or not message.parent_id:
            raise ValueError("无法找到被重生成回答对应的用户问题")
        user = self.persistence.service.message_repo.get_by_id(message.parent_id)
        if not user or user.chat_id != conversation_id or user.message_type != "user":
            raise ValueError("被重生成回答的父节点不是用户消息")
        return user

    def _get_user_prompt_for_regenerate(self, conversation_id: str, source_assistant_id: str) -> str:
        return self._get_user_message_for_regenerate(
            conversation_id,
            source_assistant_id,
        ).message_content

    def _build_branch_history_messages(
        self,
        conversation_id: str,
        current_user_message_id: Optional[str],
        current_assistant_message_id: Optional[str],
    ) -> List[Any]:
        service = getattr(self.persistence, "service", None)
        load_active_path = getattr(service, "load_active_path", None)
        if not load_active_path:
            return []

        try:
            _conversation, messages, _sibling_map = load_active_path(conversation_id)
        except Exception as e:
            logger.warning(
                "[GraphManager] 加载分支 active path 失败，将使用当前消息作为上下文, "
                "error_type=%s",
                type(e).__name__,
            )
            return []

        excluded_ids = {
            message_id
            for message_id in (current_user_message_id, current_assistant_message_id)
            if message_id
        }
        history: List[Any] = []
        for message in messages:
            message_id = getattr(message, "id", None)
            if message_id in excluded_ids:
                continue
            content = getattr(message, "message_content", "") or ""
            if not content:
                continue
            message_type = getattr(message, "message_type", None)
            if message_type == "user":
                history.append(HumanMessage(content=content))
            elif message_type == "assistant":
                history.append(AIMessage(content=content))
        return history

    def get_conversation_state(
        self,
        session_id: str,
        conversation_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        获取会话状态

        Args:
            session_id: 会话ID
            conversation_id: 数据库会话ID

        Returns:
            会话状态字典或 None
        """
        thread_config = get_thread_config(session_id, conversation_id)

        try:
            checkpoint = self.checkpointer.get_tuple(thread_config)
            if checkpoint:
                return checkpoint.checkpoint
            return None
        except Exception as e:
            logger.error(
                "[GraphManager] 获取状态失败, error_type=%s",
                type(e).__name__,
            )
            return None

    def reset_conversation(
        self,
        session_id: str,
        conversation_id: Optional[str] = None,
    ) -> bool:
        """
        重置会话

        Args:
            session_id: 会话ID
            conversation_id: 数据库会话ID

        Returns:
            是否成功
        """
        thread_id = self.thread_id_manager.get_thread_id(session_id, conversation_id)

        try:
            return self.checkpointer.delete_thread(thread_id)
        except Exception as e:
            logger.error(
                "[GraphManager] 重置会话失败, error_type=%s",
                type(e).__name__,
            )
            return False

    def get_agent_history(
        self,
        session_id: str,
        conversation_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取 Agent 使用历史

        Args:
            session_id: 会话ID
            conversation_id: 数据库会话ID

        Returns:
            Agent 使用历史列表
        """
        thread_id = self.thread_id_manager.get_thread_id(session_id, conversation_id)

        try:
            return self.checkpointer.get_agent_history(thread_id)
        except Exception as e:
            logger.error(
                "[GraphManager] 获取 Agent 历史失败, error_type=%s",
                type(e).__name__,
            )
            return []

    def get_checkpoints(
        self,
        session_id: str,
        conversation_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        获取检查点列表

        Args:
            session_id: 会话ID
            conversation_id: 数据库会话ID
            limit: 返回数量限制

        Returns:
            检查点摘要列表
        """
        thread_id = self.thread_id_manager.get_thread_id(session_id, conversation_id)

        try:
            return self.checkpointer.list_checkpoints_summary(thread_id, limit)
        except Exception as e:
            logger.error(
                "[GraphManager] 获取检查点列表失败, error_type=%s",
                type(e).__name__,
            )
            return []

    def get_messages(
        self,
        session_id: str,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取消息历史

        Args:
            session_id: 会话ID
            conversation_id: 数据库会话ID

        Returns:
            消息历史字典
        """
        thread_id = self.thread_id_manager.get_thread_id(session_id, conversation_id)

        try:
            state = self.get_conversation_state(session_id, conversation_id)
            if not state:
                return {"message_count": 0, "messages": []}

            messages = state.get("messages", [])
            formatted_messages = []

            for msg in messages:
                if isinstance(msg, HumanMessage):
                    formatted_messages.append({
                        "type": "human",
                        "content": msg.content,
                    })
                elif isinstance(msg, AIMessage):
                    formatted_messages.append({
                        "type": "ai",
                        "content": msg.content,
                    })
                elif isinstance(msg, dict):
                    formatted_messages.append({
                        "type": msg.get("type", "unknown"),
                        "content": msg.get("content", ""),
                    })

            return {
                "message_count": len(formatted_messages),
                "messages": formatted_messages,
            }

        except Exception as e:
            logger.error(
                "[GraphManager] 获取消息历史失败, error_type=%s",
                type(e).__name__,
            )
            return {"message_count": 0, "messages": []}

    def _prepare_input_state(
        self,
        patient_id: Optional[str],
        session_id: str,
        message: str,
        role: str = "patient",
        doctor_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        agent_type: str = "health",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        准备输入状态

        Args:
            (参数同 chat 方法)

        Returns:
            输入状态字典
        """
        history_messages = kwargs.pop("history_messages", None) or []
        # 创建初始状态（kwargs 透传支持 attachments/attachment_analysis 等扩展字段）
        state = create_initial_state(
            patient_id=patient_id,
            session_id=session_id,
            role=role,
            doctor_id=doctor_id,
            conversation_id=conversation_id,
            agent_type=agent_type,
            **kwargs,
        )

        # 添加用户消息
        state["messages"] = [*history_messages, HumanMessage(content=message)]

        # 科研 prepared 路径无患者；有患者时每轮加载综合画像供个性化。
        try:
            if patient_id is None:
                return state
            from infrastructure.api.backend_client import get_api_client
            client = get_api_client()
            profile = client.get_patient_comprehensive_profile(patient_id)

            if profile:
                patient_raw = profile.get("patient") or {}
                if patient_raw:
                    _gender_map = {
                        "male": "男", "female": "女",
                        "MALE": "男", "FEMALE": "女",
                    }
                    raw_gender = str(patient_raw.get("gender", ""))
                    # patient_info 维持既有 schema，避免破坏现有 build_*_context
                    state["patient_info"] = {
                        "name": patient_raw.get("patientName") or patient_raw.get("name", ""),
                        "age": patient_raw.get("age"),
                        "gender": _gender_map.get(raw_gender, raw_gender),
                        "phone": patient_raw.get("phone", ""),
                        "medical_history": (
                            patient_raw.get("medicalHistory") or patient_raw.get("medical_history")
                        ),
                        "allergy_history": (
                            patient_raw.get("allergyHistory") or patient_raw.get("allergy_history")
                        ),
                        "family_history": (
                            patient_raw.get("familyHistory") or patient_raw.get("family_history")
                        ),
                    }

                # patient_full_data 承载综合画像（病历 + 检查史 + 处方）
                state["patient_full_data"] = {
                    "patient": patient_raw,
                    "medical_records": profile.get("medicalRecords") or [],
                    "check_history": profile.get("checkHistory") or [],
                    "prescriptions": profile.get("prescriptions") or [],
                }
                logger.debug("[GraphManager] 综合画像加载成功")
        except Exception as _e:
            logger.warning(
                "[GraphManager] 加载综合画像失败，将继续执行, error_type=%s",
                type(_e).__name__,
            )
            # patient_info / patient_full_data 保持 None，各 context builder 已优雅降级

        # 合并额外参数
        for key, value in kwargs.items():
            if key in state:
                state[key] = value

        return state

    def _extract_response(self, result: Dict[str, Any]) -> str:
        """
        从结果中提取响应文本

        Args:
            result: 图执行结果

        Returns:
            响应文本
        """
        # 优先使用 last_response
        if result.get("last_response"):
            return result["last_response"]

        # 从消息中提取
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                return msg.content
            elif isinstance(msg, dict) and msg.get("type") == "ai":
                return msg.get("content", "")

        return ""

    def _extract_token_used_from_result(
        self,
        result: Dict[str, Any],
        previous_message_count: int = 0,
    ) -> Optional[int]:
        """
        从图执行结果中提取本轮 AIMessage 的 token_used。

        优先检查本轮新增消息，避免把历史消息 usage 误写到当前 assistant 消息；
        如果没有新增范围或新增消息没有 usage，再回退到最终 assistant 消息和旧的 state 字段。
        """
        messages = result.get("messages", []) if isinstance(result, dict) else []
        if not isinstance(messages, list):
            messages = []

        candidate_groups = []
        if previous_message_count and len(messages) > previous_message_count:
            candidate_groups.append(messages[previous_message_count:])
        candidate_groups.append(messages)

        seen_groups = set()
        for candidates in candidate_groups:
            group_id = id(candidates)
            if group_id in seen_groups:
                continue
            seen_groups.add(group_id)
            for msg in reversed(candidates):
                token_used = extract_token_used_from_ai_message(msg)
                if token_used is not None:
                    return token_used

        return merge_token_used(None, result.get("token_used") if isinstance(result, dict) else None)

    def _get_state_message_count(self, graph, thread_config: Dict[str, Any]) -> int:
        """读取图当前 checkpoint 中的消息数量；失败时返回 0，不阻断对话。"""
        try:
            state = graph.get_state(thread_config)
            values = getattr(state, "values", None)
            if not isinstance(values, dict):
                return 0
            messages = values.get("messages", [])
            return len(messages) if isinstance(messages, list) else 0
        except Exception as e:
            logger.debug(
                "[GraphManager] 读取历史消息数量失败，跳过本轮范围判断, "
                "error_type=%s",
                type(e).__name__,
            )
            return 0

    def _extract_citations(
        self,
        result: Dict[str, Any],
        previous_message_count: int = 0,
    ) -> List[Dict[str, Any]]:
        """从本轮搜索工具结果中抽取并去重 citations。"""
        messages = result.get("messages", []) if isinstance(result, dict) else []
        if not isinstance(messages, list):
            messages = []

        candidate_messages = messages
        if previous_message_count and len(messages) > previous_message_count:
            candidate_messages = messages[previous_message_count:]

        citations: List[Dict[str, Any]] = []
        tool_names_by_id: Dict[Any, str] = {}

        for msg in candidate_messages:
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                for tool_call in msg.tool_calls:
                    tool_call_id = self._get_value(tool_call, "id") or self._get_value(tool_call, "tool_call_id")
                    tool_name = self._get_tool_call_name(tool_call)
                    if tool_call_id and tool_name:
                        tool_names_by_id[tool_call_id] = tool_name

        for msg in candidate_messages:
            if not isinstance(msg, ToolMessage):
                continue
            tool_call_id = self._get_value(msg, "tool_call_id")
            tool_name = self._get_value(msg, "name") or tool_names_by_id.get(tool_call_id, "")
            content = self._get_value(msg, "content")
            if self._is_search_tool(tool_name) or self._looks_like_search_results(content):
                citations.extend(extract_citations_from_search_results(content))

        # 兼容旧状态字段和 A2 统一 tool_results 结构。
        raw_tool_results = result.get("tool_results") if isinstance(result, dict) else None
        for tool_result in raw_tool_results if isinstance(raw_tool_results, list) else []:
            tool_name = self._get_value(tool_result, "name") or self._get_value(tool_result, "tool")
            content = self._get_value(tool_result, "content")
            if content is None:
                content = self._get_value(tool_result, "output")
            if self._is_search_tool(tool_name) or self._looks_like_search_results(content):
                citations.extend(extract_citations_from_search_results(content))

        return deduplicate_citations(citations)

    @staticmethod
    def _is_search_tool(tool_name: Any) -> bool:
        """判断工具名是否属于搜索类工具。"""
        name = str(tool_name or "").lower()
        return "search" in name or name in {"web_search_medical"}

    @staticmethod
    def _looks_like_search_results(value: Any) -> bool:
        """在工具名缺失时，用结构特征兜底识别搜索结果。"""
        if value is None:
            return False
        if hasattr(value, "content"):
            value = getattr(value, "content")
        if isinstance(value, dict):
            return "results_by_type" in value or any(
                key in value for key in ("results", "items", "sources", "citations")
            )
        if isinstance(value, str):
            return "results_by_type" in value or '"url"' in value and '"title"' in value
        return False

    @staticmethod
    def _get_value(source: Any, key: str, default: Any = None) -> Any:
        if source is None:
            return default
        if isinstance(source, dict):
            return source.get(key, default)
        return getattr(source, key, default)

    def _get_tool_call_name(self, tool_call: Any) -> str:
        function_info = self._get_value(tool_call, "function")
        return (
            self._get_value(tool_call, "name")
            or self._get_value(function_info, "name")
            or ""
        )

    def _extract_tool_results(
        self,
        result: Dict[str, Any],
        previous_message_count: int = 0,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        从非流式图结果中提取并归一化工具调用结果。

        只优先处理本轮新增消息，避免把历史 tool_results 重复写入当前 assistant 消息。
        """
        messages = result.get("messages", []) if isinstance(result, dict) else []
        if not isinstance(messages, list):
            messages = []

        candidate_messages = messages
        if previous_message_count and len(messages) > previous_message_count:
            candidate_messages = messages[previous_message_count:]

        tool_calls = []
        tool_messages = []
        for msg in candidate_messages:
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                tool_calls.extend(msg.tool_calls)
            elif isinstance(msg, ToolMessage):
                tool_messages.append(msg)

        normalized = normalize_from_tool_calls(tool_calls, tool_messages)
        if normalized:
            return normalized

        # 兼容旧状态字段：若图节点直接写入 tool_results，也统一走同一结构。
        raw_tool_results = result.get("tool_results") if isinstance(result, dict) else None
        if raw_tool_results:
            normalized_from_state = normalize_from_stream_events(raw_tool_results)
            return normalized_from_state if normalized_from_state else None

        return None


# 单例实例
_graph_manager: Optional[GraphManager] = None


def get_graph_manager() -> GraphManager:
    """
    获取 GraphManager 单例

    Returns:
        GraphManager 实例
    """
    global _graph_manager
    if _graph_manager is None:
        _graph_manager = GraphManager()
    return _graph_manager
