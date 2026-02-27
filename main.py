"""
FastAPI主应用 - 智能医疗咨询系统
基于 LangGraph 架构
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from presentation.routers import chat_router, conversation_router, research_router, compliance_router, recommendation_router
from infrastructure.api.backend_client import get_api_client, APIError, NetworkError
from infrastructure.database.mysql_connection import get_db_connection, close_db_connection

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：初始化数据库连接池
    logger.info("[Startup] 初始化数据库连接池...")
    try:
        db = get_db_connection()
        logger.info("[Startup] 数据库连接池初始化成功")
    except Exception as e:
        logger.error(f"[Startup] 数据库连接池初始化失败: {e}")
        # 不阻止启动，让应用可以处理不需要数据库的请求

    yield  # 应用运行中

    # 关闭时：清理数据库连接池
    logger.info("[Shutdown] 关闭数据库连接池...")
    close_db_connection()
    logger.info("[Shutdown] 数据库连接池已关闭")


# 创建FastAPI应用
app = FastAPI(
    title="智能医疗咨询系统",
    description="基于LangGraph的多Agent智能医疗咨询平台",
    version="3.0.0",
    lifespan=lifespan,
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
app.include_router(conversation_router.router)
app.include_router(research_router.router)
app.include_router(compliance_router.router)
app.include_router(recommendation_router.router)

logger.info("=" * 80)
logger.info("智能医疗咨询系统启动")
logger.info("架构版本: 3.0.0 (LangGraph)")
logger.info("已启用: 健康咨询、报告、提醒、科研、合规审查、产品推荐 Agent")
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


@app.get("/recommendation-test", response_class=HTMLResponse)
async def recommendation_test_page():
    """返回产品推荐Agent测试页面"""
    with open("static/recommendation_test.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "version": "3.0.0",
        "architecture": "langgraph",
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

        # 刷新ID映射缓存
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
async def export_patient_data(session_id: str, conversation_id: str = None):
    """
    导出患者对话数据为 JSON
    """
    from agents.graph_manager import get_graph_manager

    try:
        logger.info(f"[API] 导出会话数据: {session_id}")

        graph_manager = get_graph_manager()
        result = graph_manager.get_messages(
            session_id=session_id,
            conversation_id=conversation_id,
        )

        if not result or result.get("message_count", 0) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"会话不存在或无消息: {session_id}"
            )

        # 构建导出数据
        export_data = {
            "session_id": session_id,
            "conversation_id": conversation_id,
            "message_count": result["message_count"],
            "messages": result["messages"],
        }

        logger.info(f"[API] 成功导出会话数据，共 {result['message_count']} 条消息")
        return export_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] 导出数据失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"导出数据失败: {str(e)}"
        )


@app.get("/api/info")
async def api_info():
    """API信息"""
    return {
        "title": "智能医疗咨询系统 API",
        "version": "3.0.0",
        "architecture": "langgraph",
        "endpoints": {
            "chat": "/api/chat",
            "chat_stream": "/api/chat/stream",
            "session_state": "/api/chat/{session_id}/state",
            "session_messages": "/api/chat/{session_id}/messages",
            "session_checkpoints": "/api/chat/{session_id}/checkpoints",
            "users": "/api/users",
            "conversations": "/api/conversations",
            "conversation_detail": "/api/conversations/{conversation_id}",
            "research_chat": "/api/research/chat",
            "research_chat_stream": "/api/research/chat/stream",
            "recommendation_chat": "/api/recommendation/chat",
            "recommendation_chat_stream": "/api/recommendation/chat/stream",
            "export": "/api/export/{session_id}",
        },
        "features": {
            "state_persistence": "MySQL Checkpoint 持久化",
            "auto_routing": "自动意图路由和 Agent 切换",
            "streaming": "SSE 流式响应",
            "conversation_history": "对话历史自动保存",
        },
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
