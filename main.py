"""
FastAPI主应用 - 智能体集群系统后端服务
"""
import json
import uuid
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from agents.agent_manager import AgentManager
from database.appointment_service import AppointmentService

# 创建FastAPI应用
app = FastAPI(
    title="智能医疗咨询系统",
    description="基于Langchain的智能体集群系统",
    version="1.0.0"
)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 配置模板
templates = Jinja2Templates(directory="templates")

# 全局智能体管理器
agent_manager = AgentManager()

# 全局数据库服务
appointment_service = AppointmentService()

# 会话存储（生产环境应使用Redis等）
sessions: Dict[str, Dict[str, Any]] = {}


class ChatMessage(BaseModel):
    """聊天消息模型"""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天响应模型"""
    response: str
    session_id: str
    is_completed: bool
    stage: str


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """返回聊天界面"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """
    处理聊天消息
    """
    try:
        # 生成或获取会话ID
        session_id = message.session_id or str(uuid.uuid4())
        
        # 初始化会话
        if session_id not in sessions:
            sessions[session_id] = {
                "messages": [],
                "created_at": None
            }
        
        # 获取或创建智能体
        agent = agent_manager.get_or_create_agent(session_id, "health")
        
        # 处理消息
        response = agent.chat(message.message)
        
        # 保存消息到会话
        sessions[session_id]["messages"].append({
            "role": "user",
            "content": message.message
        })
        sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": response
        })
        
        # 检查是否完成对话，如果完成则保存到数据库
        is_completed = agent.is_completed()
        
        print(f"[调试] 对话完成状态: {is_completed}, 需要预约: {agent.needs_appointment}")
        
        if is_completed and agent.needs_appointment:
            try:
                print("[调试] 开始获取患者数据并保存到数据库...")
                
                # 获取患者数据
                patient_data = agent.get_patient_data()
                
                print(f"[调试] 患者数据: {json.dumps(patient_data, ensure_ascii=False)}")
                
                # 保存到数据库
                db_result = appointment_service.process_appointment(patient_data)
                
                print(f"[数据库] 预约处理结果: {db_result}")
                
                if db_result['success']:
                    # 将数据库操作结果保存到会话
                    sessions[session_id]["appointment_result"] = db_result
                    
                    # 在响应中添加预约成功信息
                    response += f"\n\n✅ {db_result['message']}"
                    response += f"\n预约ID：{db_result['appointment_id']}"
                    response += f"\n患者ID：{db_result['patient_id']}"
                else:
                    # 预约失败，追加错误信息
                    response += f"\n\n⚠️ 预约失败：{db_result['message']}"
                    
            except Exception as e:
                import traceback
                print(f"[数据库错误] 保存数据失败: {str(e)}")
                traceback.print_exc()
                response += f"\n\n⚠️ 数据保存失败，但您的信息已记录，请联系客服。"
        
        # 返回响应
        return ChatResponse(
            response=response,
            session_id=session_id,
            is_completed=is_completed,
            stage=agent.stage.value
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理消息时出错: {str(e)}")


@app.get("/api/export/{session_id}")
async def export_patient_data(session_id: str):
    """
    导出患者病例JSON数据
    """
    try:
        agent = agent_manager.get_or_create_agent(session_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 获取患者数据
        patient_data = agent.get_patient_data()
        
        # 打印到控制台
        print("\n" + "="*50)
        print("患者病例数据（JSON格式）")
        print("="*50)
        print(json.dumps(patient_data, ensure_ascii=False, indent=2))
        print("="*50 + "\n")
        
        return JSONResponse(content=patient_data)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出数据时出错: {str(e)}")


@app.post("/api/reset/{session_id}")
async def reset_session(session_id: str):
    """
    重置会话
    """
    try:
        agent_manager.reset_agent(session_id)
        if session_id in sessions:
            sessions[session_id]["messages"] = []
        
        return {"status": "success", "message": "会话已重置"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置会话时出错: {str(e)}")


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """
    获取会话信息
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    agent = agent_manager.get_or_create_agent(session_id)
    
    return {
        "session_id": session_id,
        "messages": sessions[session_id]["messages"],
        "is_completed": agent.is_completed() if agent else False,
        "collected_fields": list(agent.collected_fields) if agent else []
    }


@app.get("/api/stats")
async def get_stats():
    """
    获取系统统计信息
    """
    return {
        "active_sessions": agent_manager.get_active_sessions_count(),
        "total_sessions": len(sessions)
    }


@app.get("/api/appointments")
async def get_appointments():
    """
    获取所有预约记录（用于验证数据库操作）
    """
    try:
        query = """
            SELECT 
                a.Appointment_ID,
                a.Patient_Name,
                a.Appointment_Time,
                a.Appointment_Status,
                d.Name as Doctor_Name,
                d.Title as Doctor_Title
            FROM appointment a
            LEFT JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
            ORDER BY a.Appointment_ID DESC
            LIMIT 50
        """
        appointments = appointment_service.db.execute_query(query)
        return {
            "success": True,
            "count": len(appointments),
            "appointments": appointments
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询预约记录失败: {str(e)}")


@app.get("/api/patients")
async def get_patients():
    """
    获取所有患者记录（用于验证数据库操作）
    """
    try:
        query = """
            SELECT 
                Patient_ID,
                Visit_Card_Number,
                Name,
                Gender,
                Age,
                Phone_Number,
                Chief_Complaint,
                Visit_Date
            FROM patient
            ORDER BY Patient_ID DESC
            LIMIT 50
        """
        patients = appointment_service.db.execute_query(query)
        return {
            "success": True,
            "count": len(patients),
            "patients": patients
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询患者记录失败: {str(e)}")


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    print("=" * 60)
    print("智能医疗咨询系统已启动")
    print("访问地址: http://127.0.0.1:8000")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    print("系统正在关闭...")
    # 关闭数据库连接
    appointment_service.close()
    print("数据库连接已关闭")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

