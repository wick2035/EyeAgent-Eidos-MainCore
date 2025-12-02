"""
Agent管理路由 - 管理Agent实例和会话
"""
import logging
from typing import List
from fastapi import APIRouter, HTTPException, status

from presentation.schemas.agent_schemas import AgentStatusResponse
from agents.agent_manager import AgentManager

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/agents", tags=["agents"])

# 全局AgentManager实例（应该与chat_router共享）
_agent_manager = None


def get_agent_manager() -> AgentManager:
    """获取全局AgentManager实例"""
    global _agent_manager
    if _agent_manager is None:
        from presentation.routers.chat_router import agent_manager as chat_agent_manager
        _agent_manager = chat_agent_manager
    return _agent_manager


@router.get("/sessions", response_model=List[dict])
async def list_sessions():
    """
    列出所有活跃会话
    
    Returns:
        会话列表
    """
    try:
        agent_manager = get_agent_manager()
        sessions = agent_manager.get_all_sessions()
        
        return {
            "total": len(sessions),
            "sessions": sessions
        }
    
    except Exception as e:
        logger.error(f"[AgentRouter] 列出会话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"列出会话失败: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=AgentStatusResponse)
async def get_session_status(session_id: str):
    """
    获取会话状态
    
    Args:
        session_id: 会话ID
    
    Returns:
        AgentStatusResponse: Agent状态
    """
    try:
        agent_manager = get_agent_manager()
        agent = agent_manager.get_agent(session_id)
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {session_id}"
            )
        
        summary = agent.get_conversation_summary()
        
        return AgentStatusResponse(
            session_id=summary["session_id"],
            patient_id=summary["patient_id"],
            agent_type=summary["agent_type"],
            stage=summary["stage"],
            is_completed=summary["is_completed"],
            message_count=summary["message_count"],
            role=summary["role"],
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AgentRouter] 获取状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取状态失败: {str(e)}"
        )


@router.post("/cleanup")
async def cleanup_expired_sessions():
    """
    清理过期会话
    
    Returns:
        清理结果
    """
    try:
        agent_manager = get_agent_manager()
        expired_count = agent_manager.cleanup_expired_sessions()
        
        return {
            "message": "清理完成",
            "expired_count": expired_count
        }
    
    except Exception as e:
        logger.error(f"[AgentRouter] 清理会话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理会话失败: {str(e)}"
        )


@router.get("/stats")
async def get_stats():
    """
    获取系统统计信息
    
    Returns:
        统计信息
    """
    try:
        agent_manager = get_agent_manager()
        
        return {
            "active_sessions": agent_manager.get_active_sessions_count(),
            "total_agents": len(agent_manager.agents),
        }
    
    except Exception as e:
        logger.error(f"[AgentRouter] 获取统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计失败: {str(e)}"
        )

