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

from presentation.routers import chat_router, agent_router

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

logger.info("=" * 80)
logger.info("智能医疗咨询系统启动")
logger.info("架构版本: 2.0.0 (清洁架构)")
logger.info("=" * 80)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """返回聊天界面"""
    return templates.TemplateResponse("index.html", {"request": request})


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


@app.get("/api/info")
async def api_info():
    """API信息"""
    return {
        "title": "智能医疗咨询系统 API",
        "version": "2.0.0",
        "architecture": "clean_architecture",
        "endpoints": {
            "chat": "/api/chat",
            "agent_status": "/api/agents/sessions/{session_id}",
            "list_sessions": "/api/agents/sessions",
            "cleanup": "/api/agents/cleanup",
            "stats": "/api/agents/stats",
        },
        "breaking_changes": {
            "patient_id": "现在必需，且必须是UUID格式",
            "user_id": "已弃用，请使用patient_id",
            "phone_number": "已弃用，前端应先查询获取patient_id",
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
