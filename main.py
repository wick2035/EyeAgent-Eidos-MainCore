"""
FastAPI主应用 - 智能医疗咨询系统
基于 LangGraph 架构
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from math import ceil, isfinite
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from presentation.routers import chat_router, conversation_router, research_router, compliance_router, recommendation_router
from presentation.routers import asr_router
from presentation.routers import file_router
from presentation.routers import platform_chat_turn_router
from presentation.routers import research_document_router
from infrastructure.api.backend_client import get_api_client, APIError, NetworkError
from infrastructure.database.mysql_connection import get_db_connection, close_db_connection
from presentation.exception_handlers.platform_validation_handler import (
    install_platform_validation_handler,
)
from presentation.middleware.internal_jwt_auth import install_internal_auth
from application.services.chat_turn_watchdog import get_chat_turn_watchdog
from application.services.chat_turn_execution_registry import (
    get_chat_turn_execution_registry,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    natural_timeout = _positive_env_seconds(
        "PLATFORM_TURN_DRAIN_NATURAL_TIMEOUT_SECONDS",
        60,
    )
    abort_timeout = _positive_env_seconds(
        "PLATFORM_TURN_DRAIN_ABORT_TIMEOUT_SECONDS",
        30,
    )
    execution_registry = get_chat_turn_execution_registry()
    execution_registry.start_accepting()

    # 启动时：初始化数据库连接池
    logger.info("[Startup] 初始化数据库连接池...")
    try:
        db = get_db_connection()
        logger.info("[Startup] 数据库连接池初始化成功")
    except Exception as e:
        logger.error(f"[Startup] 数据库连接池初始化失败: {e}")
        # 不阻止启动，让应用可以处理不需要数据库的请求

    watchdog_stop = asyncio.Event()
    watchdog_task = None
    try:
        watchdog = get_chat_turn_watchdog()
        watchdog_task = asyncio.create_task(
            watchdog.run(watchdog_stop),
            name="chat-turn-watchdog",
        )
        logger.info("[Startup] 附件回合 watchdog 已启动")
    except Exception as error:
        logger.error(
            "[Startup] 附件回合 watchdog 启动失败: %s",
            type(error).__name__,
        )

    try:
        yield  # 应用运行中
    finally:
        try:
            await _drain_platform_turns(
                execution_registry,
                natural_timeout,
                abort_timeout,
            )
            if watchdog_task is not None:
                watchdog_stop.set()
                try:
                    await watchdog_task
                except Exception as error:
                    logger.error(
                        "[Shutdown] 附件回合 watchdog 退出异常: %s",
                        type(error).__name__,
                    )
                else:
                    logger.info("[Shutdown] 附件回合 watchdog 已停止")
        finally:
            # Watchdog 异常或取消也不能跳过原有数据库清理。
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

install_platform_validation_handler(app)

# 内部 API 认证先注册，随后注册的 CORS 位于外层并覆盖认证错误响应。
install_internal_auth(app)

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
app.include_router(asr_router.router)
app.include_router(file_router.router)
app.include_router(platform_chat_turn_router.router)
app.include_router(research_document_router.router)

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


@app.get("/health/ready")
async def readiness_check():
    """只表达本实例是否继续接收新的 platform 回合。"""
    registry = get_chat_turn_execution_registry()
    payload = {
        "status": "draining" if registry.is_draining() else "ready",
        "active_platform_turns": registry.active_count(),
    }
    if registry.is_draining():
        return JSONResponse(status_code=503, content=payload)
    return payload


def _positive_env_seconds(name: str, default: int) -> float:
    raw_value = os.getenv(name, str(default))
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive number") from exc
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return value


def _strict_env_boolean(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    raise ValueError(f"{name} must equal true or false")


async def _drain_platform_turns(
    execution_registry,
    natural_timeout: float,
    abort_timeout: float,
) -> bool:
    if not execution_registry.begin_drain():
        return execution_registry.active_count() == 0
    active_at_start = execution_registry.active_count()
    logger.info(
        "[Shutdown] platform turn drain 开始: active=%s",
        active_at_start,
    )
    idle = await execution_registry.wait_until_idle(natural_timeout)
    signalled = 0
    if not idle:
        signalled = execution_registry.signal_all()
        idle = await execution_registry.wait_until_idle(abort_timeout)
    logger.info(
        "[Shutdown] platform turn drain 结束: active=%s, "
        "signalled=%s, idle=%s",
        execution_registry.active_count(),
        signalled,
        idle,
    )
    return idle


class PlatformDrainServer(uvicorn.Server):
    """在 Uvicorn 关闭 listener 前先排空 platform 附件回合。"""

    def __init__(
        self,
        config: uvicorn.Config,
        *,
        natural_timeout: float,
        abort_timeout: float,
    ) -> None:
        super().__init__(config)
        self._platform_natural_timeout = natural_timeout
        self._platform_abort_timeout = abort_timeout

    async def shutdown(self, sockets=None) -> None:
        await _drain_platform_turns(
            get_chat_turn_execution_registry(),
            self._platform_natural_timeout,
            self._platform_abort_timeout,
        )
        await super().shutdown(sockets=sockets)


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
    print("http://127.0.0.1:20602")
    reload_enabled = _strict_env_boolean("UVICORN_RELOAD", False)
    graceful_timeout = ceil(
        _positive_env_seconds(
            "UVICORN_GRACEFUL_SHUTDOWN_SECONDS",
            100,
        )
    )
    natural_timeout = _positive_env_seconds(
        "PLATFORM_TURN_DRAIN_NATURAL_TIMEOUT_SECONDS",
        60,
    )
    abort_timeout = _positive_env_seconds(
        "PLATFORM_TURN_DRAIN_ABORT_TIMEOUT_SECONDS",
        30,
    )
    if reload_enabled:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=20602,
            reload=True,
            timeout_graceful_shutdown=graceful_timeout,
            log_level="info",
        )
    else:
        config = uvicorn.Config(
            "main:app",
            host="0.0.0.0",
            port=20602,
            reload=False,
            timeout_graceful_shutdown=graceful_timeout,
            log_level="info",
        )
        PlatformDrainServer(
            config,
            natural_timeout=natural_timeout,
            abort_timeout=abort_timeout,
        ).run()
