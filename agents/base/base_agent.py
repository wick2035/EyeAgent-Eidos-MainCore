"""
BaseAgent - 所有智能体的抽象基类
消除40%代码重复，提供统一的对话管理和工具集成框架
支持 LangChain Agent 工具调用
支持对话历史持久化
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from langchain.chat_models.base import BaseChatModel
from langchain.tools import Tool
from langchain.agents import initialize_agent, AgentType as LangChainAgentType, AgentExecutor
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import logging

from domain.models.conversation import Conversation
from domain.enums.agent_type import AgentType
from domain.enums.conversation_stage import ConversationStage
from domain.models.chat_entity import MessageContext
from agents.base.conversation_manager import ConversationManager
from utils.llm_config import get_llm

if TYPE_CHECKING:
    from application.services.chat_persistence_service import ChatPersistenceService

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    智能体抽象基类
    
    职责：
    - 提供通用对话管理框架
    - 集成LangChain工具
    - 管理对话阶段转换
    - 统一错误处理
    
    子类需要实现：
    - _create_system_prompt(): 创建系统提示词
    - _get_stage_prompt(): 获取当前阶段提示
    - _handle_stage_transition(): 处理阶段转换逻辑
    - _extract_info_from_input(): 从用户输入提取信息
    """
    
    def __init__(
        self,
        patient_id: str,
        session_id: str,
        agent_type: AgentType,
        role: str = "patient",
        tools: Optional[List[Tool]] = None,
        conversation_id: Optional[str] = None,
        persistence_service: Optional["ChatPersistenceService"] = None
    ):
        """
        初始化BaseAgent

        Args:
            patient_id: 患者UUID
            session_id: 会话ID
            agent_type: Agent类型
            role: 用户角色（patient/doctor）
            tools: LangChain工具列表
            conversation_id: 数据库会话ID（用于继续对话）
            persistence_service: 持久化服务（用于保存对话）
        """
        self.patient_id = patient_id
        self.session_id = session_id
        self.agent_type = agent_type
        self.role = role
        self.db_conversation_id: Optional[str] = conversation_id
        self.persistence_service = persistence_service

        # 患者信息缓存（在初始化时加载）
        self.patient_info: Optional[Any] = None
        # 患者完整数据（包括历史记录）
        self.patient_full_data: Optional[Any] = None

        # 初始化LLM
        self.llm: BaseChatModel = get_llm()

        # 初始化工具
        self.tools: List[Tool] = tools or []

        # 创建Conversation对象
        self.conversation = Conversation(
            session_id=session_id,
            patient_id=patient_id,
            agent_type=agent_type,
            stage=ConversationStage.GREETING,
            is_completed=False,
        )

        # 初始化对话管理器（带持久化支持）
        self.conversation_manager = ConversationManager(
            self.conversation,
            persistence_service=persistence_service,
            db_conversation_id=conversation_id
        )

        # 如果有 conversation_id，加载历史对话
        if conversation_id and persistence_service:
            self._load_conversation_from_db(conversation_id)

        # 创建 Agent Executor（支持工具调用）
        self.agent_executor: Optional[AgentExecutor] = None
        self._create_agent_executor()

        # 加载患者完整数据（优雅降级）
        self._load_patient_full_data()

        logger.info(f"[{self.__class__.__name__}] 初始化完成: patient={patient_id}, session={session_id}, conversation_id={conversation_id}, tools={len(self.tools)}")
    
    def _create_agent_executor(self):
        """创建支持工具调用的 Agent Executor"""
        if self.tools:
            # 构建系统提示词（包含工具说明）
            system_prompt = self._create_system_prompt()
            tools_description = self._build_tools_description()
            full_prefix = system_prompt + "\n\n" + tools_description

            # 使用 STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION 类型的 Agent
            # 这种类型支持多参数工具调用，使用默认的 JSON blob 格式
            self.agent_executor = initialize_agent(
                tools=self.tools,
                llm=self.llm,
                agent=LangChainAgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=5,
                agent_kwargs={
                    "prefix": full_prefix,
                    # 不自定义 format_instructions，使用默认格式确保 action_input 正确解析
                }
            )
            logger.info(f"[{self.__class__.__name__}] Agent Executor 创建完成，工具数量: {len(self.tools)}")
        else:
            # 无工具时，使用简单的 LLM 调用
            self.agent_executor = None
            logger.info(f"[{self.__class__.__name__}] 无工具，将使用简单 LLM 调用")

    def _build_tools_description(self) -> str:
        """构建工具描述信息，包含患者ID和历史数据"""
        if not self.tools:
            return ""

        lines = ["【可用工具】", ""]
        for tool in self.tools:
            # 获取工具名称和描述
            tool_name = tool.name
            tool_desc = tool.description.split('\n')[0]  # 只取第一行描述
            lines.append(f"- {tool_name}: {tool_desc}")

        lines.append("")
        lines.append(f"【当前患者ID】")
        lines.append(f"patient_id = {self.patient_id}")
        lines.append("调用任何工具时，patient_id 参数必须使用上面的值，不要使用患者姓名。")

        # 添加患者历史数据供 LLM 在预约时使用
        if self.patient_info:
            lines.append("")
            lines.append("【患者病史信息（预约时使用）】")
            lines.append(f"medical_history = {self.patient_info.medical_history or '无'}")
            lines.append(f"allergy_history = {self.patient_info.allergy_history or '无'}")
            lines.append(f"family_history = {self.patient_info.family_history or '无'}")

        lines.append("")
        lines.append("【工具调用规则】")
        lines.append("1. 预约前必须先收集完整信息：主诉症状、期望就诊日期、医院名称")
        lines.append("2. 信息不完整时，先询问用户补充，不要调用工具")
        lines.append("3. 日期格式必须是 yyyy-MM-dd（如 2025-12-03）")
        lines.append("4. 预约时间格式必须是 yyyy-MM-ddTHH:mm:ss（如 2025-12-03T09:00:00）")
        lines.append("5. 普通对话、问候、症状咨询直接回复，无需调用工具")
        lines.append("6. 不要编造预约时间，必须使用工具查询真实数据")
        lines.append("7. reserve_doctor 的 chief_complaint 和 present_illness 必须来自当前对话收集的信息")
        lines.append("8. reserve_doctor 的 medical_history/allergy_history/family_history 使用上面【患者病史信息】中的值")
        lines.append("")

        return "\n".join(lines)

    def _load_patient_info(self):
        """
        加载患者详细信息（优雅降级）

        如果加载失败，Agent仍能正常工作，只是缺少患者详细信息。
        失败原因可能是：
        1. 后端API未实现
        2. 网络错误
        3. 患者不存在
        """
        try:
            from infrastructure.repositories.patient_repository_impl import PatientRepositoryImpl

            patient_repo = PatientRepositoryImpl()
            self.patient_info = patient_repo.get_by_id(self.patient_id)

            if self.patient_info:
                logger.info(
                    f"[{self.__class__.__name__}] 成功加载患者信息: "
                    f"name={self.patient_info.name}, age={self.patient_info.age}"
                )
            else:
                logger.warning(
                    f"[{self.__class__.__name__}] 未找到患者信息: {self.patient_id}"
                )

        except Exception as e:
            # 优雅降级：记录错误但不中断初始化
            logger.error(
                f"[{self.__class__.__name__}] 加载患者信息失败: {e}",
                exc_info=True
            )
            self.patient_info = None

    def _load_conversation_from_db(self, conversation_id: str):
        """
        从数据库加载历史对话

        Args:
            conversation_id: 数据库会话ID
        """
        if not self.persistence_service:
            return

        try:
            conversation_entity, messages = self.persistence_service.load_conversation(conversation_id)

            if not conversation_entity:
                logger.warning(f"[{self.__class__.__name__}] 会话不存在: {conversation_id}")
                return

            # 恢复历史消息到内存
            for msg in messages:
                self.conversation.add_message(msg.message_type, msg.message_content)

            # 标记不是首条消息（避免重复更新标题）
            self.conversation_manager._is_first_user_message = len(messages) == 0

            logger.info(f"[{self.__class__.__name__}] 加载历史对话: {conversation_id}, 消息数={len(messages)}")

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 加载历史对话失败: {e}", exc_info=True)

    def set_persistence(self, service: "ChatPersistenceService", conversation_id: str):
        """
        设置持久化服务和会话ID

        Args:
            service: 持久化服务
            conversation_id: 数据库会话ID
        """
        self.persistence_service = service
        self.db_conversation_id = conversation_id
        self.conversation_manager.set_persistence_service(service, conversation_id)
        logger.info(f"[{self.__class__.__name__}] 设置持久化: {conversation_id}")

    def _load_patient_full_data(self):
        """
        加载患者完整数据（基础信息 + 历史记录）

        使用PatientDataLoader并发加载：
        - 基础信息（姓名、年龄、性别、电话、病史）
        - 历史预约
        - 历史处方
        - 扫描数据
        - 提醒历史

        如果加载失败，Agent仍能正常工作，只是缺少患者详细信息。
        """
        try:
            from infrastructure.loaders.patient_data_loader import PatientDataLoader
            from infrastructure.api.backend_client import get_api_client

            logger.debug(f"[{self.__class__.__name__}] 开始加载患者完整数据...")

            loader = PatientDataLoader(get_api_client())
            self.patient_full_data = loader.load_all_patient_data(self.patient_id)

            # 向后兼容：保留patient_info
            self.patient_info = self.patient_full_data.basic_info

            # 详细日志
            if self.patient_full_data.basic_info:
                logger.info(
                    f"[{self.__class__.__name__}] 患者数据加载完成: "
                    f"基础信息✓ "
                    f"病历{len(self.patient_full_data.medical_records)}条 "
                    f"预约{len(self.patient_full_data.appointments)}条 "
                    f"处方{len(self.patient_full_data.prescriptions)}条 "
                    f"扫描{len(self.patient_full_data.scan_data)}条 "
                    f"提醒{len(self.patient_full_data.reminders)}条"
                )
            else:
                logger.warning(f"[{self.__class__.__name__}] 未找到患者基础信息: {self.patient_id}")

        except Exception as e:
            # 优雅降级：记录错误但不中断初始化
            logger.error(
                f"[{self.__class__.__name__}] 加载患者完整数据失败: {e}",
                exc_info=True
            )
            self.patient_full_data = None
            self.patient_info = None

    @abstractmethod
    def _create_system_prompt(self) -> str:
        """
        创建系统提示词（子类实现）
        
        Returns:
            系统提示词字符串
        """
        pass
    
    @abstractmethod
    def _get_stage_prompt(self) -> str:
        """
        获取当前阶段的提示信息（子类实现）
        
        Returns:
            阶段提示字符串
        """
        pass
    
    @abstractmethod
    def _handle_stage_transition(self, user_input: str, ai_response: str):
        """
        处理阶段转换逻辑（子类实现）
        
        Args:
            user_input: 用户输入
            ai_response: AI响应
        """
        pass
    
    @abstractmethod
    def _extract_info_from_input(self, user_input: str) -> Dict[str, Any]:
        """
        从用户输入中提取信息（子类实现）
        
        Args:
            user_input: 用户输入
        
        Returns:
            提取的信息字典
        """
        pass
    
    def chat(self, user_input: str) -> str:
        """
        处理用户输入并返回响应（支持工具调用）

        Args:
            user_input: 用户输入

        Returns:
            AI响应字符串
        """
        try:
            logger.info(f"[{self.__class__.__name__}] 收到用户输入: {user_input[:50]}...")

            # 1. 添加用户消息到历史
            self.conversation_manager.add_user_message(user_input)

            # 2. 提取信息
            extracted_info = self._extract_info_from_input(user_input)
            logger.debug(f"[{self.__class__.__name__}] 提取信息: {extracted_info}")

            # 3. 构建上下文增强的输入
            additional_context = self._build_additional_context(extracted_info)
            stage_prompt = self._get_stage_prompt()
            history_text = self._get_conversation_history_text()

            # 构建增强输入（包含上下文信息和对话历史）
            enhanced_input = f"""【当前上下文】
{additional_context}

当前阶段: {stage_prompt}

【对话历史】
{history_text}

【用户当前消息】
{user_input}"""

            # 4. 调用 Agent Executor 或简单 LLM
            if self.agent_executor:
                # 使用支持工具调用的 Agent
                result = self.agent_executor.invoke({
                    "input": enhanced_input,
                })
                response = result.get("output", "")
                logger.info(f"[{self.__class__.__name__}] Agent 执行完成，工具调用情况已记录")
            else:
                # 无工具时，直接调用 LLM
                system_prompt = self._create_system_prompt()
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=enhanced_input)
                ]
                llm_response = self.llm.invoke(messages)
                response = llm_response.content

            # 5. 添加AI响应到历史
            self.conversation_manager.add_assistant_message(response)

            # 6. 处理阶段转换
            self._handle_stage_transition(user_input, response)

            logger.info(f"[{self.__class__.__name__}] 生成响应: {response[:50]}...")
            return response

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] chat异常: {e}", exc_info=True)
            return f"抱歉，处理您的请求时出现了问题：{str(e)}"

    def _get_conversation_history_text(self) -> str:
        """获取对话历史文本"""
        history = self.conversation.history
        if not history or len(history) <= 1:
            return "（无历史对话）"

        lines = []
        # 跳过最后一条（刚添加的用户消息）
        for msg in history[:-1]:
            # Message 是 Pydantic BaseModel，使用属性访问
            role = msg.role
            content = msg.content
            if role == "user":
                lines.append(f"患者: {content}")
            elif role == "assistant":
                lines.append(f"助手: {content}")

        return "\n".join(lines) if lines else "（无历史对话）"
    
    def _build_additional_context(self, extracted_info: Dict[str, Any]) -> str:
        """
        构建额外上下文（可被子类覆盖）

        Args:
            extracted_info: 提取的信息

        Returns:
            上下文字符串，包含患者基本信息
        """
        context_parts = []

        # 添加患者基本信息
        if self.patient_info:
            context_parts.append("【患者信息】")
            context_parts.append(f"姓名: {self.patient_info.name}")
            context_parts.append(f"年龄: {self.patient_info.age}岁")
            context_parts.append(f"性别: {self.patient_info.gender}")
            context_parts.append(f"联系电话: {self.patient_info.phone}")

            # 添加病史信息（如果有）
            if self.patient_info.medical_history:
                context_parts.append(f"既往病史: {self.patient_info.medical_history}")

            if self.patient_info.allergy_history:
                context_parts.append(f"过敏史: {self.patient_info.allergy_history}")

            if self.patient_info.family_history:
                context_parts.append(f"家族史: {self.patient_info.family_history}")

            context_parts.append("")  # 空行分隔
        else:
            # 如果没有患者详细信息，至少提供ID
            context_parts.append(f"【患者ID】{self.patient_id}")
            context_parts.append("")

        return "\n".join(context_parts)
    
    def get_current_stage(self) -> ConversationStage:
        """获取当前对话阶段"""
        return self.conversation.stage
    
    def is_completed(self) -> bool:
        """检查对话是否完成"""
        return self.conversation_manager.is_completed()
    
    def reset(self):
        """重置智能体状态"""
        self.conversation.history.clear()
        self.conversation.stage = ConversationStage.GREETING
        self.conversation.is_completed = False
        self.conversation.metadata.clear()
        logger.info(f"[{self.__class__.__name__}] 已重置")
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """
        获取对话摘要

        Returns:
            对话摘要字典
        """
        return {
            "session_id": self.session_id,
            "patient_id": self.patient_id,
            "agent_type": self.agent_type.value,
            "stage": self.conversation.stage.value,
            "is_completed": self.is_completed(),
            "message_count": self.conversation_manager.get_message_count(),
            "role": self.role,
            "conversation_id": self.db_conversation_id,
        }
    
    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"session={self.session_id} "
            f"patient={self.patient_id} "
            f"stage={self.conversation.stage.value}>"
        )

