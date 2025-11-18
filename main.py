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
from database.appointment_service_v2 import AppointmentServiceV2
from database.report_service import ReportService
from database.prescription_service import PrescriptionService
from database.reminder_service import ReminderService
from utils.report_generator import ReportGenerator
from utils.prescription_generator import PrescriptionGenerator

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

# 全局数据库服务（使用V2版本以匹配数据库架构）
appointment_service = AppointmentServiceV2()

# 报告服务
report_service = ReportService()
report_generator = ReportGenerator()

# 处方服务
prescription_service = PrescriptionService()
prescription_generator = PrescriptionGenerator()

# 提醒服务
reminder_service = ReminderService()

# 会话存储（生产环境应使用Redis等）
sessions: Dict[str, Dict[str, Any]] = {}


class ChatMessage(BaseModel):
    """聊天消息模型"""
    message: str
    session_id: Optional[str] = None
    user_id: Optional[int] = None  # 用于模拟不同用户（Patient_ID）
    phone_number: Optional[str] = None  # 用户手机号（推荐使用，可获取完整历史信息）
    role: Optional[str] = "patient"  # 用户角色：patient（患者）或 doctor（医生）


class ChatResponse(BaseModel):
    """聊天响应模型"""
    response: str
    session_id: str
    is_completed: bool
    stage: str
    agent_type: Optional[str] = None  # 当前使用的agent类型


class ReportRequest(BaseModel):
    """报告请求模型"""
    patient_id: Optional[int] = None
    phone_number: Optional[str] = None
    medical_record_id: Optional[int] = None


class AnalysisRequest(BaseModel):
    """分析请求模型"""
    patient_id: Optional[int] = None
    phone_number: Optional[str] = None
    analysis_type: str = "trends"  # trends, compare, anomalies
    record_ids: Optional[list] = None  # 用于对比的记录ID列表


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """返回聊天界面"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """
    处理聊天消息 - 智能路由版本
    根据用户角色和消息内容自动选择合适的Agent
    """
    try:
        from utils.intent_detector import get_intent_detector
        
        # 生成或获取会话ID
        session_id = message.session_id or str(uuid.uuid4())
        role = message.role or "patient"
        
        print(f"\n[主程序] 收到聊天请求:")
        print(f"  - session_id: {session_id}")
        print(f"  - role: {role}")
        print(f"  - user_id: {message.user_id}")
        print(f"  - phone_number: {message.phone_number}")
        print(f"  - message: {message.message[:50]}...")
        
        # 初始化会话
        if session_id not in sessions:
            sessions[session_id] = {
                "messages": [],
                "created_at": None,
                "role": role,
                "current_agent": None
            }
        
        # 获取对话历史（用于意图识别）
        conversation_history = sessions[session_id].get("messages", [])
        
        # 1. 意图识别 - 判断使用哪个Agent
        intent_detector = get_intent_detector()
        intent_result = intent_detector.detect_intent(
            message.message,
            role=role,
            conversation_history=conversation_history
        )
        
        print(f"[意图识别] Agent类型: {intent_result['agent_type']}, "
              f"置信度: {intent_result['confidence']:.2f}, "
              f"原因: {intent_result['reason']}")
        
        # 检查是否被阻止（患者尝试生成报告等）
        if intent_result.get('blocked'):
            print(f"[权限控制] 操作被阻止: {intent_result['reason']}")
            response = f"抱歉，{intent_result['reason']}。您可以查看和分析现有的报告，但无法生成新报告。"
            
            # 保存消息到会话
            sessions[session_id]["messages"].append({
                "role": "user",
                "content": message.message
            })
            sessions[session_id]["messages"].append({
                "role": "assistant",
                "content": response
            })
            
            return ChatResponse(
                response=response,
                session_id=session_id,
                is_completed=False,
                stage="blocked",
                agent_type=None
            )
        
        # 2. 获取或创建对应的Agent
        agent_type = intent_result['agent_type']
        current_agent = sessions[session_id].get("current_agent")
        
        # 判断是否需要切换Agent
        if current_agent and current_agent != agent_type:
            print(f"[Agent切换] {current_agent} -> {agent_type}")
            # 重置agent以切换
            agent_manager.reset_agent(session_id)
        
        # 创建或获取Agent
        agent = agent_manager.get_or_create_agent(
            session_id, 
            agent_type,
            user_id=message.user_id,
            phone_number=message.phone_number,
            role=role  # 传递角色参数
        )
        
        # 更新当前使用的Agent
        sessions[session_id]["current_agent"] = agent_type
        
        print(f"[主程序] 使用Agent: {agent_type}")
        
        # 处理消息
        if agent_type == "health":
            response = agent.chat(message.message)
            is_completed = agent.is_completed()
            stage = agent.stage.value
        else:  # report agent
            response, is_completed = agent.chat(message.message)
            stage = agent.stage.value
        
        # 保存消息到会话
        sessions[session_id]["messages"].append({
            "role": "user",
            "content": message.message
        })
        sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": response
        })
        
        print(f"[主程序] 对话完成状态: {is_completed}")
        
        # 3. 对于health agent，检查是否需要保存预约
        if agent_type == "health" and is_completed and hasattr(agent, 'needs_appointment') and agent.needs_appointment:
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
            stage=stage,
            agent_type=agent_type
        )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
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


@app.get("/api/users")
async def get_users():
    """
    获取可用的用户列表（用于前端模拟不同用户）
    """
    try:
        query = """
            SELECT DISTINCT
                Patient_ID,
                Name,
                Phone_Number,
                Gender,
                Age
            FROM patient
            ORDER BY Patient_ID DESC
            LIMIT 20
        """
        users = appointment_service.db.execute_query(query)
        return {
            "success": True,
            "users": users
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询用户列表失败: {str(e)}")


# ==================== 报告相关API ====================

@app.post("/api/report/generate")
async def generate_report(request: ReportRequest):
    """
    生成病例报告PDF
    
    Args:
        request: 包含patient_id或phone_number，以及可选的medical_record_id
        
    Returns:
        生成结果和文件路径
    """
    try:
        # 获取用户ID
        patient_id = request.patient_id
        if not patient_id and request.phone_number:
            user_info = report_service.db.execute_one(
                "SELECT Patient_ID FROM patient WHERE Phone_Number = %s",
                (request.phone_number,)
            )
            if user_info:
                patient_id = user_info['Patient_ID']
        
        if not patient_id:
            raise HTTPException(status_code=400, detail="未提供有效的患者信息")
        
        # 如果指定了病例ID，生成单个报告
        if request.medical_record_id:
            pdf_path = report_generator.generate_report_from_db(request.medical_record_id)
            if pdf_path:
                return {
                    "success": True,
                    "message": "报告生成成功",
                    "file_path": pdf_path,
                    "medical_record_id": request.medical_record_id
                }
            else:
                raise HTTPException(status_code=500, detail="报告生成失败")
        
        # 否则生成最新的报告
        reports = report_service.get_all_reports_by_patient(patient_id, limit=1)
        if not reports:
            raise HTTPException(status_code=404, detail="未找到病例记录")
        
        latest_record_id = reports[0]['Medical_Record_ID']
        pdf_path = report_generator.generate_report_from_db(latest_record_id)
        
        if pdf_path:
            return {
                "success": True,
                "message": "报告生成成功",
                "file_path": pdf_path,
                "medical_record_id": latest_record_id
            }
        else:
            raise HTTPException(status_code=500, detail="报告生成失败")
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成报告时出错: {str(e)}")


@app.get("/api/report/history/{patient_id}")
async def get_report_history(patient_id: int):
    """
    获取用户的历史报告列表
    
    Args:
        patient_id: 用户ID
        
    Returns:
        报告列表
    """
    try:
        reports = report_service.get_all_reports_by_patient(patient_id)
        return {
            "success": True,
            "patient_id": patient_id,
            "count": len(reports),
            "reports": reports
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询报告历史失败: {str(e)}")


@app.post("/api/report/analyze")
async def analyze_reports(request: AnalysisRequest):
    """
    分析历史报告
    
    Args:
        request: 包含patient_id或phone_number，以及analysis_type
        
    Returns:
        分析结果
    """
    try:
        # 获取用户ID
        patient_id = request.patient_id
        if not patient_id and request.phone_number:
            user_info = report_service.db.execute_one(
                "SELECT Patient_ID FROM patient WHERE Phone_Number = %s",
                (request.phone_number,)
            )
            if user_info:
                patient_id = user_info['Patient_ID']
        
        if not patient_id:
            raise HTTPException(status_code=400, detail="未提供有效的患者信息")
        
        # 创建临时的 ReportAgent 进行分析
        from agents.agent_2 import ReportAgent
        agent = ReportAgent(patient_id=patient_id)
        
        # 根据分析类型执行不同的分析
        if request.analysis_type == "trends":
            result = agent.analyze_history_trends(patient_id)
        elif request.analysis_type == "anomalies":
            result = agent.detect_anomalies(patient_id)
        elif request.analysis_type == "compare":
            if not request.record_ids or len(request.record_ids) < 2:
                raise HTTPException(status_code=400, detail="对比分析需要至少两个病例ID")
            result = agent.compare_records(request.record_ids)
        else:
            raise HTTPException(status_code=400, detail=f"未知的分析类型: {request.analysis_type}")
        
        return {
            "success": True,
            "analysis_type": request.analysis_type,
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"分析报告时出错: {str(e)}")


@app.post("/api/chat/report", response_model=ChatResponse)
async def chat_report(message: ChatMessage):
    """
    报告智能体对话接口
    
    与 /api/chat 类似，但使用 ReportAgent
    """
    try:
        # 生成或获取会话ID
        session_id = message.session_id or str(uuid.uuid4())
        
        print(f"\n[报告Agent] 收到对话请求:")
        print(f"  - session_id: {session_id}")
        print(f"  - user_id: {message.user_id}")
        print(f"  - phone_number: {message.phone_number}")
        print(f"  - message: {message.message[:50]}...")
        
        # 初始化会话
        if session_id not in sessions:
            sessions[session_id] = {
                "messages": [],
                "agent_type": "report",
                "created_at": None
            }
        
        # 获取或创建报告智能体
        agent = agent_manager.get_or_create_agent(
            session_id, 
            "report", 
            user_id=message.user_id,
            phone_number=message.phone_number
        )
        
        # 处理消息
        response, is_completed = agent.chat(message.message)
        
        # 保存消息到会话
        sessions[session_id]["messages"].append({
            "role": "user",
            "content": message.message
        })
        sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": response
        })
        
        # 返回响应
        return ChatResponse(
            response=response,
            session_id=session_id,
            is_completed=is_completed,
            stage=agent.stage.value
        )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"处理报告对话时出错: {str(e)}")


# ==================== 处方相关API ====================

class PrescriptionRequest(BaseModel):
    """处方请求模型"""
    prescription_id: int
    patient_id: Optional[int] = None
    phone_number: Optional[str] = None


@app.post("/api/prescription/generate")
async def generate_prescription(request: PrescriptionRequest):
    """
    生成处方单PDF
    
    Args:
        request: 包含prescription_id（必填），以及可选的patient_id/phone_number用于验证
        
    Returns:
        生成结果和文件路径
    """
    try:
        print(f"[处方API] 收到生成处方单请求: Prescription_ID={request.prescription_id}")
        
        # 可选：验证处方是否属于指定患者
        if request.patient_id or request.phone_number:
            prescription_data = prescription_service.get_prescription_full(request.prescription_id)
            if not prescription_data:
                raise HTTPException(status_code=404, detail="未找到处方记录")
            
            # 验证患者ID
            if request.patient_id:
                if prescription_data['patient_info']['patient_id'] != request.patient_id:
                    raise HTTPException(status_code=403, detail="无权访问此处方")
            
            # 验证手机号
            if request.phone_number:
                if prescription_data['patient_info']['phone'] != request.phone_number:
                    raise HTTPException(status_code=403, detail="无权访问此处方")
        
        # 生成处方单
        pdf_path = prescription_generator.generate_prescription_from_db(request.prescription_id)
        
        if pdf_path:
            return {
                "success": True,
                "message": "处方单生成成功",
                "file_path": pdf_path,
                "prescription_id": request.prescription_id
            }
        else:
            raise HTTPException(status_code=500, detail="处方单生成失败")
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成处方单时出错: {str(e)}")


@app.get("/api/prescription/list/{patient_id}")
async def get_prescription_list(patient_id: int, limit: int = 50):
    """
    获取患者的处方列表
    
    Args:
        patient_id: 患者ID
        limit: 返回记录数限制（默认50）
        
    Returns:
        处方摘要列表
    """
    try:
        print(f"[处方API] 查询患者处方列表: Patient_ID={patient_id}")
        
        prescriptions = prescription_service.get_prescriptions_by_patient(patient_id, limit)
        
        return {
            "success": True,
            "patient_id": patient_id,
            "count": len(prescriptions),
            "prescriptions": prescriptions
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询处方列表失败: {str(e)}")


@app.get("/api/prescription/list/phone/{phone_number}")
async def get_prescription_list_by_phone(phone_number: str, limit: int = 50):
    """
    通过手机号获取患者的处方列表
    
    Args:
        phone_number: 患者手机号
        limit: 返回记录数限制（默认50）
        
    Returns:
        处方摘要列表
    """
    try:
        print(f"[处方API] 通过手机号查询处方列表: Phone={phone_number}")
        
        prescriptions = prescription_service.get_prescriptions_by_phone(phone_number, limit)
        
        return {
            "success": True,
            "phone_number": phone_number,
            "count": len(prescriptions),
            "prescriptions": prescriptions
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询处方列表失败: {str(e)}")


@app.get("/api/prescription/detail/{prescription_id}")
async def get_prescription_detail(prescription_id: int):
    """
    获取单个处方的完整详情
    
    Args:
        prescription_id: 处方ID
        
    Returns:
        完整处方信息（包含药物明细）
    """
    try:
        print(f"[处方API] 查询处方详情: Prescription_ID={prescription_id}")
        
        prescription_data = prescription_service.get_prescription_full(prescription_id)
        
        if not prescription_data:
            raise HTTPException(status_code=404, detail="未找到处方记录")
        
        return {
            "success": True,
            "prescription": prescription_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询处方详情失败: {str(e)}")


# ==================== 提醒相关API ====================

class ReminderRequest(BaseModel):
    """提醒请求模型"""
    patient_id: Optional[int] = None
    phone_number: Optional[str] = None
    reminder_id: Optional[int] = None
    status: Optional[str] = None
    reminder_type: Optional[str] = None


@app.get("/api/reminder/list/{patient_id}")
async def get_reminder_list(patient_id: int, status: Optional[str] = None, limit: int = 50):
    """
    获取患者的提醒列表

    Args:
        patient_id: 患者ID
        status: 状态过滤 (pending/sent/completed/cancelled/expired)
        limit: 返回记录数限制（默认50）

    Returns:
        提醒列表
    """
    try:
        print(f"[提醒API] 查询患者提醒列表: Patient_ID={patient_id}, Status={status}")

        reminders = reminder_service.get_reminders_by_patient(patient_id, status=status, limit=limit)

        return {
            "success": True,
            "patient_id": patient_id,
            "count": len(reminders),
            "reminders": reminders
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询提醒列表失败: {str(e)}")


@app.get("/api/reminder/list/phone/{phone_number}")
async def get_reminder_list_by_phone(phone_number: str, status: Optional[str] = None, limit: int = 50):
    """
    通过手机号获取患者的提醒列表

    Args:
        phone_number: 患者手机号
        status: 状态过滤
        limit: 返回记录数限制

    Returns:
        提醒列表
    """
    try:
        print(f"[提醒API] 通过手机号查询提醒列表: Phone={phone_number}, Status={status}")

        reminders = reminder_service.get_reminders_by_phone(phone_number, status=status, limit=limit)

        return {
            "success": True,
            "phone_number": phone_number,
            "count": len(reminders),
            "reminders": reminders
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询提醒列表失败: {str(e)}")


@app.get("/api/reminder/pending")
async def get_pending_reminders(limit: int = 100):
    """
    获取待发送的提醒（用于定时任务）

    Args:
        limit: 返回记录数限制（默认100）

    Returns:
        待发送提醒列表
    """
    try:
        print(f"[提醒API] 查询待发送提醒")

        reminders = reminder_service.get_pending_reminders(limit=limit)

        return {
            "success": True,
            "count": len(reminders),
            "reminders": reminders
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询待发送提醒失败: {str(e)}")


@app.post("/api/reminder/create")
async def create_reminder(request: Dict[str, Any]):
    """
    创建新提醒

    Args:
        request: 提醒数据（包含patient_id, reminder_type, reminder_title等）

    Returns:
        创建结果
    """
    try:
        print(f"[提醒API] 创建提醒: {request}")

        from datetime import datetime

        # 解析时间字符串
        scheduled_time_str = request.get('scheduled_time')
        if isinstance(scheduled_time_str, str):
            scheduled_time = datetime.fromisoformat(scheduled_time_str.replace('Z', '+00:00'))
        else:
            scheduled_time = scheduled_time_str

        result = reminder_service.create_reminder(
            patient_id=request['patient_id'],
            reminder_type=request['reminder_type'],
            reminder_title=request['reminder_title'],
            reminder_content=request['reminder_content'],
            scheduled_time=scheduled_time,
            advance_days=request.get('advance_days', 1),
            priority=request.get('priority', 'normal'),
            medical_record_id=request.get('medical_record_id'),
            appointment_id=request.get('appointment_id'),
            prescription_id=request.get('prescription_id'),
            repeat_type=request.get('repeat_type', 'once'),
            max_repeat_count=request.get('max_repeat_count', 1),
            created_by=request.get('created_by', 'system'),
            notes=request.get('notes')
        )

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"创建提醒失败: {str(e)}")


@app.post("/api/reminder/update")
async def update_reminder(request: ReminderRequest):
    """
    更新提醒状态

    Args:
        request: 包含reminder_id和status

    Returns:
        更新结果
    """
    try:
        print(f"[提醒API] 更新提醒状态: ID={request.reminder_id}, Status={request.status}")

        if not request.reminder_id or not request.status:
            raise HTTPException(status_code=400, detail="缺少必需参数: reminder_id和status")

        result = reminder_service.update_reminder_status(
            reminder_id=request.reminder_id,
            status=request.status,
            action_by='api'
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"更新提醒失败: {str(e)}")


@app.post("/api/chat/reminder", response_model=ChatResponse)
async def chat_reminder(message: ChatMessage):
    """
    提醒智能体对话接口

    与 /api/chat 类似，但使用 ReminderAgent
    """
    try:
        # 生成或获取会话ID
        session_id = message.session_id or str(uuid.uuid4())

        print(f"\n[提醒Agent] 收到对话请求:")
        print(f"  - session_id: {session_id}")
        print(f"  - user_id: {message.user_id}")
        print(f"  - phone_number: {message.phone_number}")
        print(f"  - message: {message.message[:50]}...")

        # 初始化会话
        if session_id not in sessions:
            sessions[session_id] = {
                "messages": [],
                "agent_type": "reminder",
                "created_at": None
            }

        # 获取或创建提醒智能体
        agent = agent_manager.get_or_create_agent(
            session_id,
            "reminder",
            user_id=message.user_id,
            phone_number=message.phone_number,
            role=message.role or "patient"
        )

        # 处理消息
        response, is_completed = agent.chat(message.message)

        # 保存消息到会话
        sessions[session_id]["messages"].append({
            "role": "user",
            "content": message.message
        })
        sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": response
        })

        # 返回响应
        return ChatResponse(
            response=response,
            session_id=session_id,
            is_completed=is_completed,
            stage=agent.stage.value,
            agent_type="reminder"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"处理提醒对话时出错: {str(e)}")


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
    report_service.close()
    prescription_service.close()
    reminder_service.close()
    print("数据库连接已关闭")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

