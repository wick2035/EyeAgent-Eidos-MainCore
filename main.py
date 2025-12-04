"""
FastAPI主应用 - 智能医疗咨询系统（重构版）
基于清洁架构，精简到 < 100行
"""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from presentation.routers import chat_router, agent_router, conversation_router, research_router
from infrastructure.api.backend_client import get_api_client, APIError, NetworkError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="智能医疗咨询系统",
    description="基于LangChain的多Agent智能医疗咨询平台（重构版）",
    version="2.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 配置模板
templates = Jinja2Templates(directory="templates")

# 注册路由
app.include_router(chat_router.router)
app.include_router(agent_router.router)
app.include_router(conversation_router.router)
app.include_router(research_router.router)  # 医问通科研Agent路由

logger.info("=" * 80)
logger.info("智能医疗咨询系统启动")
logger.info("架构版本: 2.0.0 (清洁架构)")
logger.info("已启用: ResearchAgent (医问通科研Agent)")
logger.info("=" * 80)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """返回聊天界面"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/research-test", response_class=HTMLResponse)
async def research_test_page():
    """返回科研Agent测试页面"""
    with open("static/research_test.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/health")
async def health_check():
    """健康检查"""
    from agents.agent_manager import AgentManager
    from presentation.routers.chat_router import agent_manager
    
    return {
        "status": "healthy",
        "version": "2.0.0",
        "architecture": "clean_architecture",
        "active_sessions": agent_manager.get_active_sessions_count(),
    }


@app.get("/api/users")
async def get_users():
    """
    获取所有患者列表（供前端下拉框使用）
    调用后端 /agent/api/get-all-patient 接口
    """
    try:
        logger.info("[API] 获取患者列表")
        client = get_api_client()
        patients = client.get_all_patients()

        # 刷新ID映射缓存（新增）
        try:
            from infrastructure.services.id_mapping_service import get_id_mapping_service
            id_mapping = get_id_mapping_service()
            id_mapping.refresh_mappings()
            logger.debug("[API] ID映射缓存已刷新")
        except Exception as e:
            logger.warning(f"[API] 刷新ID映射缓存失败: {e}")

        # 性别映射
        gender_map = {"MALE": "男", "FEMALE": "女"}

        # 转换为前端期望的格式
        users = []
        for patient in patients:
            users.append({
                "Patient_ID": patient.get("id"),
                "Name": patient.get("patientName"),
                "Gender": gender_map.get(patient.get("gender"), "未知"),
                "Age": patient.get("age"),
                "Phone_Number": patient.get("phone")
            })

        logger.info(f"[API] 成功获取 {len(users)} 个患者，ID映射已刷新")
        return {
            "success": True,
            "users": users
        }

    except (APIError, NetworkError) as e:
        logger.error(f"[API] 获取患者列表失败: {e}")
        return {
            "success": False,
            "users": [],
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"[API] 获取患者列表异常: {e}")
        return {
            "success": False,
            "users": [],
            "error": str(e)
        }


@app.get("/api/export/{session_id}")
async def export_patient_data(session_id: str):
    """
    导出患者对话数据为 JSON
    """
    from fastapi import HTTPException
    from presentation.routers.chat_router import agent_manager

    try:
        logger.info(f"[API] 导出会话数据: {session_id}")

        # 从 agent_manager 获取会话数据
        conversation = agent_manager.get_conversation(session_id)

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"会话不存在: {session_id}"
            )

        # 构建导出数据
        export_data = {
            "session_id": session_id,
            "agent_type": conversation.agent_type if hasattr(conversation, 'agent_type') else "unknown",
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if hasattr(msg.timestamp, 'isoformat') else str(msg.timestamp)
                }
                for msg in conversation.messages
            ],
            "patient_info": conversation.patient_info if hasattr(conversation, 'patient_info') else {},
            "summary": conversation.summary if hasattr(conversation, 'summary') else ""
        }

        logger.info(f"[API] 成功导出会话数据，共 {len(export_data['messages'])} 条消息")
        return export_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] 导出数据失败: {e}")
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"导出数据失败: {str(e)}"
        )


@app.get("/api/info")
async def api_info():
    """API信息"""
    return {
        "title": "智能医疗咨询系统 API",
        "version": "2.0.0",
        "architecture": "clean_architecture",
        "endpoints": {
            "chat": "/api/chat",
            "users": "/api/users",
            "conversations": "/api/conversations",
            "conversation_detail": "/api/conversations/{conversation_id}",
            "agent_status": "/api/agents/sessions/{session_id}",
            "list_sessions": "/api/agents/sessions",
            "cleanup": "/api/agents/cleanup",
            "stats": "/api/agents/stats",
            "research_chat": "/api/research/chat",
            "research_chat_stream": "/api/research/chat/stream",
            "research_conversations": "/api/research/conversations",
            "research_health": "/api/research/health",
        },
        "new_features": {
            "conversation_persistence": "对话历史自动保存到数据库",
            "conversation_list": "GET /api/conversations 获取历史会话列表",
            "continue_conversation": "POST /api/chat 传入 conversation_id 继续对话",
            "research_agent": "医问通科研Agent，支持文献搜索和机构数据分析",
            "sse_streaming": "科研Agent支持SSE流式响应",
        },
        "breaking_changes": {
            "patient_id": "现在必需，且必须是UUID格式",
            "user_id": "已弃用，请使用patient_id",
            "phone_number": "已弃用，前端应先查询获取patient_id",
        }
    }


if __name__ == "__main__":
    print("http://127.0.0.1:8000")
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

