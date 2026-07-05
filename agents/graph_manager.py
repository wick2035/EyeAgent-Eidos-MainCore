"""
GraphManager - LangGraph 图管理器

替代原有的 AgentManager，提供基于 LangGraph 的对话管理。
"""
import logging
from typing import Dict, Any, Optional, Generator, AsyncGenerator, List
import asyncio

from langchain_core.messages import HumanMessage, AIMessage

from agents.graph.state import MedicalState, create_initial_state
from agents.graph.graph_builder import get_medical_graph, create_medical_graph
from agents.graph.id_mapping import ThreadIDManager, get_thread_config
from agents.graph.checkpointer import get_checkpointer
from agents.graph.persistence_adapter import PersistenceAdapter, NullPersistenceAdapter

logger = logging.getLogger(__name__)


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
            logger.warning(f"[GraphManager] 创建 MySQL 适配器失败，使用空适配器: {e}")
            return NullPersistenceAdapter()

    def chat(
        self,
        patient_id: str,
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

        logger.info(f"[GraphManager] chat: patient={patient_id}, thread={thread_id}")

        # === 安全检查：角色校验 + 输入防护 ===
        from utils.role_verification import verify_role
        from utils.input_guard import check_input_safety, RiskLevel, HIGH_RISK_RESPONSE, LOW_RISK_RESPONSE

        verified_role, was_downgraded = verify_role(role, patient_id, doctor_id)
        if was_downgraded:
            logger.warning(
                f"[GraphManager] 角色降级: {role} -> {verified_role}, "
                f"patient_id={patient_id}, doctor_id={doctor_id}"
            )
            role = verified_role
            if agent_type in ("compliance", "research"):
                agent_type = "health"

        guard_result = check_input_safety(message, context={
            "role": role, "agent_type": agent_type, "patient_id": patient_id,
        })
        if not guard_result.is_safe:
            logger.warning(
                f"[GraphManager] 安全拦截: risk={guard_result.risk_level.value}, "
                f"category={guard_result.category.value if guard_result.category else 'N/A'}, "
                f"detail={guard_result.detail}"
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
                user_context = {
                    "stage": "greeting" if is_first else None,
                    "agent_type": agent_type,
                }

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

                logger.debug(
                    f"[GraphManager] 两阶段写入 - 用户消息已保存, AI占位: {assistant_msg_id}"
                )

            except Exception as e:
                logger.error(f"[GraphManager] 保存用户消息失败: {e}", exc_info=True)
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

            # 调用图
            result = self.graph.invoke(
                input_state,
                config=thread_config,
            )

            # 提取响应
            response = self._extract_response(result)

            # 获取结果中的 Agent 类型
            current_agent = result.get("current_agent", agent_type)
            current_stage = result.get("stage", "greeting")

            # === 两阶段写入 - 第二阶段：更新 AI 回复为成功 ===
            if assistant_msg_id and conversation_id:
                try:
                    # 提取工具调用结果
                    tool_results = self._extract_tool_results(result)

                    self.persistence.update_assistant_success(
                        message_id=assistant_msg_id,
                        content=response,
                        token_used=result.get("token_used"),
                        tool_results=tool_results,
                        context={
                            "stage": current_stage,
                            "agent_type": current_agent,
                        },
                    )
                    logger.debug(f"[GraphManager] 两阶段写入 - AI回复已更新: {assistant_msg_id}")

                except Exception as e:
                    logger.error(f"[GraphManager] 更新 AI 回复失败: {e}", exc_info=True)

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
                    f"[GraphManager] Agent 切换: {previous_agent} -> {current_agent}, "
                    f"thread={thread_id}"
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
            }

        except Exception as e:
            # === 两阶段写入 - 失败处理：更新 AI 回复为失败 ===
            if assistant_msg_id and conversation_id:
                try:
                    self.persistence.update_assistant_failed(
                        message_id=assistant_msg_id,
                        error_message=str(e),
                    )
                    logger.debug(f"[GraphManager] 两阶段写入 - AI回复标记失败: {assistant_msg_id}")
                except Exception as pe:
                    logger.error(f"[GraphManager] 更新 AI 失败状态失败: {pe}", exc_info=True)

            logger.error(f"[GraphManager] chat 失败: {e}", exc_info=True)
            return {
                "response": "抱歉，我遇到了一些技术问题，请稍后再试。",
                "agent_type": agent_type,
                "stage": "error",
                "is_completed": False,
                "thread_id": thread_id,
                "error": str(e),
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

        logger.info(f"[GraphManager] chat_stream: patient={patient_id}, thread={thread_id}")

        # === 安全检查：角色校验 + 输入防护 ===
        from utils.role_verification import verify_role
        from utils.input_guard import check_input_safety, RiskLevel, HIGH_RISK_RESPONSE, LOW_RISK_RESPONSE

        verified_role, was_downgraded = verify_role(role, patient_id, doctor_id)
        if was_downgraded:
            logger.warning(
                f"[GraphManager] 角色降级: {role} -> {verified_role}, "
                f"patient_id={patient_id}, doctor_id={doctor_id}"
            )
            role = verified_role
            if agent_type in ("compliance", "research"):
                agent_type = "health"

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

                user_context = {
                    "stage": "greeting" if is_first else None,
                    "agent_type": agent_type,
                }

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
                logger.error(f"[GraphManager] 流式 - 保存用户消息失败: {e}", exc_info=True)

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
            logger.error(f"[GraphManager] chat_stream 失败: {e}", exc_info=True)
            yield {
                "type": "error",
                "content": "抱歉，我遇到了一些技术问题，请稍后再试。",
                "metadata": {"error": str(e)},
            }

        # === 两阶段写入 - 第二阶段：流结束后保存完整回复 ===
        if assistant_msg_id and conversation_id:
            try:
                if stream_error:
                    self.persistence.update_assistant_failed(
                        message_id=assistant_msg_id,
                        error_message=str(stream_error),
                    )
                else:
                    self.persistence.update_assistant_success(
                        message_id=assistant_msg_id,
                        content=full_response,
                        token_used=None,  # 流式模式无法准确获取 token
                        tool_results=None,
                        context={
                            "stage": current_stage,
                            "agent_type": current_agent,
                        },
                    )
                    logger.debug(f"[GraphManager] 流式 - AI回复已保存: {assistant_msg_id}")

            except Exception as e:
                logger.error(f"[GraphManager] 流式 - 保存 AI 回复失败: {e}", exc_info=True)

    async def chat_stream_async(
        self,
        patient_id: str,
        session_id: str,
        message: str,
        role: str = "patient",
        doctor_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        agent_type: str = "health",
        **kwargs,
    ) -> AsyncGenerator[Dict[str, Any], None]:
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

        # 获取线程配置
        thread_config = get_thread_config(session_id, conversation_id)
        thread_id = thread_config["configurable"]["thread_id"]

        logger.info(f"[GraphManager] chat_stream_async: patient={patient_id}, thread={thread_id}")

        # === 安全检查：角色校验 + 输入防护 ===
        from utils.role_verification import verify_role
        from utils.input_guard import check_input_safety, RiskLevel, HIGH_RISK_RESPONSE, LOW_RISK_RESPONSE

        verified_role, was_downgraded = verify_role(role, patient_id, doctor_id)
        if was_downgraded:
            logger.warning(
                f"[GraphManager] 角色降级: {role} -> {verified_role}, "
                f"patient_id={patient_id}, doctor_id={doctor_id}"
            )
            role = verified_role
            if agent_type in ("compliance", "research"):
                agent_type = "health"

        guard_result = check_input_safety(message, context={
            "role": role, "agent_type": agent_type, "patient_id": patient_id,
        })
        if not guard_result.is_safe:
            logger.warning(
                f"[GraphManager] 安全拦截(async_stream): risk={guard_result.risk_level.value}, "
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

                self.persistence.save_user_message(
                    chat_id=conversation_id,
                    content=message,
                    sender_id=sender_id,
                    context={
                        "stage": "greeting" if is_first else None,
                        "agent_type": agent_type,
                    },
                    is_first_message=is_first,
                )

                assistant_msg_id = self.persistence.create_assistant_placeholder(
                    chat_id=conversation_id,
                    context={"stage": agent_type, "agent_type": agent_type},
                )

            except Exception as e:
                logger.error(f"[GraphManager] 流式 - 保存用户消息失败: {e}", exc_info=True)

        # 准备输入状态（标记流式模式）
        input_state = self._prepare_input_state(
            patient_id=patient_id,
            session_id=session_id,
            message=message,
            role=role,
            doctor_id=doctor_id,
            conversation_id=conversation_id,
            agent_type=agent_type,
            is_streaming=True,  # 关键：标记流式模式
            **kwargs,
        )

        # 用于拼接完整响应
        full_response = ""
        current_agent = agent_type
        current_stage = "greeting"
        stream_error = None

        # 收集工具调用事件，流结束后持久化到 context.tool_results
        collected_tool_calls: List[Dict[str, Any]] = []

        try:
            streaming_graph = get_streaming_medical_graph()

            async for event in streaming_graph.astream_events(
                input_state,
                config=thread_config,
                version="v2",
            ):
                event_type = event.get("event", "")

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
                    tool_input = event.get("data", {}).get("input", {})
                    collected_tool_calls.append({
                        "tool": tool_name,
                        "status": "start",
                        "input": tool_input,
                        "text_offset": len(full_response),
                    })
                    yield {
                        "type": "tool_start",
                        "content": "",
                        "metadata": {
                            "tool": tool_name,
                            "input": tool_input,
                        },
                    }

                # 工具调用结束。匹配 tool_start 设置的条目，
                # 把 status/input 升级为 end/output，text_offset 保留不变；
                # 若找不到匹配(异常序列)，用当前文本位置兜底附加。
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = str(event.get("data", {}).get("output", ""))[:500]
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
            logger.error(f"[GraphManager] chat_stream_async 失败: {e}", exc_info=True)
            yield {
                "type": "error",
                "content": "抱歉，我遇到了一些技术问题，请稍后再试。",
                "metadata": {"error": str(e)},
            }

        # 兜底：节点内部使用阻塞 agent.invoke 时，astream_events 捕获不到 on_chat_model_stream，
        # full_response 会为空。此时从最终状态取 last_response 补发一次，保证回复能到达前端。
        if not full_response and not stream_error:
            try:
                final_state = streaming_graph.get_state(thread_config)
                fallback_resp = ""
                if final_state and getattr(final_state, "values", None):
                    fallback_resp = final_state.values.get("last_response", "") or ""
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
                logger.warning(f"[GraphManager] 流式回退 last_response 失败: {e}")

        # === 两阶段写入 - 第二阶段：流结束后保存完整回复 ===
        if assistant_msg_id and conversation_id:
            try:
                if stream_error:
                    self.persistence.update_assistant_failed(
                        message_id=assistant_msg_id,
                        error_message=str(stream_error),
                    )
                else:
                    self.persistence.update_assistant_success(
                        message_id=assistant_msg_id,
                        content=full_response,
                        token_used=None,
                        tool_results=collected_tool_calls if collected_tool_calls else None,
                        context={
                            "stage": current_stage,
                            "agent_type": current_agent,
                        },
                    )
                    logger.debug(f"[GraphManager] 流式 - AI回复已保存: {assistant_msg_id}")

            except Exception as e:
                logger.error(f"[GraphManager] 流式 - 保存 AI 回复失败: {e}", exc_info=True)

        # 发送完成事件
        yield {
            "type": "done",
            "content": full_response,
            "metadata": {
                "agent_type": current_agent,
                "stage": current_stage,
            },
        }

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
            logger.error(f"[GraphManager] 获取状态失败: {e}")
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
            logger.error(f"[GraphManager] 重置会话失败: {e}")
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
            logger.error(f"[GraphManager] 获取 Agent 历史失败: {e}")
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
            logger.error(f"[GraphManager] 获取检查点列表失败: {e}")
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
            logger.error(f"[GraphManager] 获取消息历史失败: {e}")
            return {"message_count": 0, "messages": []}

    def _prepare_input_state(
        self,
        patient_id: str,
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
        state["messages"] = [HumanMessage(content=message)]

        # 加载患者基本信息（每轮注入，确保 Agent 始终持有真实患者数据）
        try:
            from infrastructure.api.backend_client import get_api_client
            client = get_api_client()
            medical_data = client.get_medical_records(patient_id)
            patient_raw = medical_data.get("patient", {}) if medical_data else {}
            if patient_raw:
                # 将后端字段名统一映射到 domain 字段名
                _gender_map = {
                    "male": "男", "female": "女",
                    "MALE": "男", "FEMALE": "女",
                }
                raw_gender = str(patient_raw.get("gender", ""))
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
                logger.debug(
                    f"[GraphManager] 患者信息加载成功: {state['patient_info'].get('name')}"
                )
        except Exception as _e:
            logger.warning(f"[GraphManager] 加载患者信息失败，将继续执行: {_e}")
            # patient_info 保持 None，各 agent 的 context builder 会优雅降级

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

    def _extract_tool_results(self, result: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        从结果中提取工具调用结果

        Args:
            result: 图执行结果

        Returns:
            工具调用结果列表，如果没有则返回 None
        """
        tool_results = []

        # 从消息中提取工具调用
        messages = result.get("messages", [])
        for msg in messages:
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_results.append({
                        "tool": tool_call.get("name", "unknown"),
                        "args": tool_call.get("args", {}),
                    })

        # 从状态中提取（如果有）
        if result.get("tool_results"):
            if isinstance(result["tool_results"], list):
                tool_results.extend(result["tool_results"])
            else:
                tool_results.append(result["tool_results"])

        return tool_results if tool_results else None


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
