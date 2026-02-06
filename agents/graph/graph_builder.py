"""
LangGraph 主图构建器

构建医疗智能体的状态图，集成所有节点和边。
"""
import logging
from typing import Optional

from langgraph.graph import StateGraph, START, END

from agents.graph.state import MedicalState
from agents.graph.checkpointer import MySQLCheckpointSaver, get_checkpointer
from agents.graph.nodes import (
    router_node,
    health_agent_node,
    report_agent_node,
    reminder_agent_node,
    research_agent_node,
    compliance_agent_node,
    response_node,
)
from agents.graph.edges.routing import (
    route_by_agent_type,
    should_continue_or_end,
)

logger = logging.getLogger(__name__)


class MedicalGraphBuilder:
    """
    医疗智能体图构建器

    负责构建和编译 LangGraph 状态图。

    图结构:
        START -> router -> [health/report/reminder/research/compliance] -> response -> END
                    ^                                              |
                    |______________________________________________|
                              (如果需要继续对话)
    """

    def __init__(self, checkpointer: Optional[MySQLCheckpointSaver] = None):
        """
        初始化图构建器

        Args:
            checkpointer: MySQL Checkpoint 保存器，为空则使用默认单例
        """
        self.checkpointer = checkpointer or get_checkpointer()
        self._graph = None
        self._compiled_graph = None

    def build(self) -> StateGraph:
        """
        构建状态图

        Returns:
            未编译的 StateGraph
        """
        logger.info("[GraphBuilder] 开始构建医疗智能体图")

        # 创建状态图
        graph = StateGraph(MedicalState)

        # 添加节点
        graph.add_node("router", router_node)
        graph.add_node("health", health_agent_node)
        graph.add_node("report", report_agent_node)
        graph.add_node("reminder", reminder_agent_node)
        graph.add_node("research", research_agent_node)
        graph.add_node("compliance", compliance_agent_node)
        graph.add_node("output_handler", response_node)  # 避免与状态键 response 冲突

        # 添加入口边
        graph.add_edge(START, "router")

        # 添加路由条件边 (router -> agents)
        graph.add_conditional_edges(
            "router",
            route_by_agent_type,
            {
                "health": "health",
                "report": "report",
                "reminder": "reminder",
                "research": "research",
                "compliance": "compliance",
            }
        )

        # 添加 Agent -> output_handler 边
        graph.add_edge("health", "output_handler")
        graph.add_edge("report", "output_handler")
        graph.add_edge("reminder", "output_handler")
        graph.add_edge("research", "output_handler")
        graph.add_edge("compliance", "output_handler")

        # 添加响应节点条件边 (output_handler -> router 或 END)
        graph.add_conditional_edges(
            "output_handler",
            should_continue_or_end,
            {
                "continue": "router",  # 继续对话，重新路由
                "__end__": END,  # 结束
            }
        )

        self._graph = graph
        logger.info("[GraphBuilder] 图结构构建完成")

        return graph

    def compile(self) -> "CompiledStateGraph":
        """
        编译状态图

        Returns:
            编译后的图，可用于 invoke/stream
        """
        if self._graph is None:
            self.build()

        logger.info("[GraphBuilder] 开始编译图")

        self._compiled_graph = self._graph.compile(
            checkpointer=self.checkpointer,
        )

        logger.info("[GraphBuilder] 图编译完成")

        return self._compiled_graph

    def get_compiled_graph(self) -> "CompiledStateGraph":
        """
        获取编译后的图（懒加载）

        Returns:
            编译后的图
        """
        if self._compiled_graph is None:
            self.compile()

        return self._compiled_graph


# 单例图实例
_graph_builder: Optional[MedicalGraphBuilder] = None
_compiled_graph = None


def get_medical_graph() -> "CompiledStateGraph":
    """
    获取医疗智能体图单例

    Returns:
        编译后的 LangGraph 状态图
    """
    global _graph_builder, _compiled_graph

    if _compiled_graph is None:
        _graph_builder = MedicalGraphBuilder()
        _compiled_graph = _graph_builder.compile()

    return _compiled_graph


def create_medical_graph(checkpointer: Optional[MySQLCheckpointSaver] = None) -> "CompiledStateGraph":
    """
    创建新的医疗智能体图实例

    Args:
        checkpointer: 自定义 Checkpoint 保存器

    Returns:
        新的编译后的图
    """
    builder = MedicalGraphBuilder(checkpointer=checkpointer)
    return builder.compile()


# 流式图单例
_streaming_compiled_graph = None


def get_streaming_medical_graph() -> "CompiledStateGraph":
    """
    获取支持流式输出的医疗智能体图

    使用 MemorySaver 作为 checkpointer（天然支持异步）

    Returns:
        编译后的流式图
    """
    global _streaming_compiled_graph

    if _streaming_compiled_graph is None:
        from langgraph.checkpoint.memory import MemorySaver
        builder = MedicalGraphBuilder(checkpointer=MemorySaver())
        _streaming_compiled_graph = builder.compile()
        logger.info("[GraphBuilder] 流式图编译完成")

    return _streaming_compiled_graph


# 类型别名（用于类型提示）
try:
    from langgraph.graph.state import CompiledStateGraph
except ImportError:
    CompiledStateGraph = object
