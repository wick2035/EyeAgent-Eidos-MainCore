"""
FastAPI主应用 - 智能体集群系统后端服务 + UUID支持
更新日期：2025-11-20 (UUID支持)
"""
import json
import uuid
from typing import Dict, Any, Optional, Union
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from agents.agent_manager import AgentManager
from database.appointment_service_v3 import AppointmentServiceV3
from database.report_service import ReportService
from database.prescription_service import PrescriptionService
from database.reminder_service import ReminderService
from database.chat_service import ChatService
from database.user_history_service_v2 import UserHistoryServiceV2
from database.base_service import normalize_id, is_valid_uuid
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

# 全局数据库服务（使用V3版本）
appointment_service = AppointmentServiceV3()

# 报告服务
report_service = ReportService()
report_generator = ReportGenerator()

# 处方服务
prescription_service = PrescriptionService()
prescription_generator = PrescriptionGenerator()

# 提醒服务
reminder_service = ReminderService()

# 对话历史服务
chat_service = ChatService()

# 用户历史服务
user_history_service = UserHistoryServiceV2()

# 会话存储（生产环境应使用Redis等）
sessions: Dict[str, Dict[str, Any]] = {}


class ChatMessage(BaseModel):
    """聊天消息模型 (支持UUID)"""
    message: str
    session_id: Optional[str] = None
    user_id: Optional[Union[str, int]] = None  # 用户ID（支持Patient_ID或Patient_UUID）
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
    """报告请求模型 (支持UUID)"""
    patient_id: Optional[Union[str, int]] = None  # 支持Patient_ID或Patient_UUID
    phone_number: Optional[str] = None
    medical_record_id: Optional[Union[str, int]] = None  # 支持Medical_Record_ID或Medical_Record_UUID


class AnalysisRequest(BaseModel):
    """分析请求模型 (支持UUID)"""
    patient_id: Optional[Union[str, int]] = None  # 支持Patient_ID或Patient_UUID
    phone_number: Optional[str] = None
    analysis_type: str = "trends"  # trends, compare, anomalies
    record_ids: Optional[list] = None  # 用于对比的记录ID列表（支持混合INT和UUID）


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """返回聊天界面"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """返回历史记录查询界面"""
    return templates.TemplateResponse("history.html", {"request": request})


@app.get("/chat-history", response_class=HTMLResponse)
async def chat_history_page(request: Request):
    """返回对话历史记录查询界面"""
    return templates.TemplateResponse("chat_history.html", {"request": request})


@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """
    处理聊天消息 - 智能路由版本 (支持UUID)
    根据用户角色和消息内容自动选择合适的Agent
    """
    try:
        from utils.intent_detector import get_intent_detector

        # 生成或获取会话ID
        session_id = message.session_id or str(uuid.uuid4())
        role = message.role or "patient"

        # 规范化user_id（兼容INT和UUID）
        user_id_normalized = None
        if message.user_id is not None:
            try:
                user_id_normalized = normalize_id(message.user_id)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"无效的用户ID格式: {message.user_id}")

        print(f"\n[主程序] 收到聊天请求:")
        print(f"  - session_id: {session_id}")
        print(f"  - role: {role}")
        print(f"  - user_id: {user_id_normalized}")
        print(f"  - phone_number: {message.phone_number}")
        print(f"  - message: {message.message[:50]}...")
        
        # 初始化会话
        if session_id not in sessions:
            sessions[session_id] = {
                "messages": [],
                "created_at": None,
                "role": role,
                "current_agent": None,
                "chat_id": None  # 数据库中的Chat_ID
            }

            # 在数据库中创建对话会话 (支持UUID)
            if user_id_normalized or message.phone_number:
                try:
                    from database.user_history_service_v2 import UserHistoryServiceV2
                    user_service = UserHistoryServiceV2()

                    # 根据角色分别查询患者或医生信息
                    patient_id = None
                    doctor_id = None

                    if role == "patient":
                        # 查询患者信息
                        patient_id = user_id_normalized
                        if not patient_id and message.phone_number:
                            user_info = user_service.get_user_by_phone(message.phone_number)
                            if user_info:
                                # 优先使用Patient_UUID，如果没有则使用Patient_ID
                                patient_id = user_info.get('Patient_UUID') or normalize_id(user_info['Patient_ID'])

                    elif role == "doctor":
                        # 查询医生信息
                        doctor_id = user_id_normalized
                        if not doctor_id and message.phone_number:
                            doctor_info = user_service.get_doctor_by_phone(message.phone_number)
                            if doctor_info:
                                # 优先使用Doctor_UUID，如果没有则使用Doctor_ID
                                doctor_id = doctor_info.get('Doctor_UUID') or normalize_id(doctor_info['Doctor_ID'])

                    # 根据角色创建对话
                    if role == "patient" and patient_id:
                        chat_id = chat_service.create_chat_for_patient(
                            patient_id=patient_id,
                            title=None,  # 稍后根据第一条消息生成标题
                            conversation_type='general',
                            ai_agent=None  # 稍后根据意图识别结果更新
                        )
                        if chat_id:
                            sessions[session_id]["chat_id"] = chat_id
                            print(f"[对话历史] 创建患者对话: Chat_ID={chat_id}, Patient_ID={patient_id}")

                    elif role == "doctor" and doctor_id:
                        chat_id = chat_service.create_chat_for_doctor(
                            doctor_id=doctor_id,
                            title=None,
                            conversation_type='general',
                            ai_agent=None
                        )
                        if chat_id:
                            sessions[session_id]["chat_id"] = chat_id
                            print(f"[对话历史] 创建医生对话: Chat_ID={chat_id}, Doctor_ID={doctor_id}")

                    else:
                        print(f"[对话历史] 无法创建对话: role={role}, patient_id={patient_id}, doctor_id={doctor_id}")

                except Exception as e:
                    print(f"[对话历史] 创建对话失败: {e}")
                    import traceback
                    traceback.print_exc()
        
        # 获取对话历史（用于意图识别）
        conversation_history = sessions[session_id].get("messages", [])

        # 获取当前agent状态
        current_agent = sessions[session_id].get("current_agent")
        current_stage = sessions[session_id].get("current_stage")

        # 1. 意图识别 - 判断使用哪个Agent
        intent_detector = get_intent_detector()
        intent_result = intent_detector.detect_intent(
            message.message,
            role=role,
            conversation_history=conversation_history,
            current_agent=current_agent,
            current_stage=current_stage
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

            # 保存消息到数据库
            chat_id = sessions[session_id].get("chat_id")
            if chat_id:
                try:
                    chat_service.save_message(
                        chat_id=chat_id,
                        message_content=message.message,
                        message_type='user',
                        sender_info=f"{role}_{message.user_id or message.phone_number}",
                        context={'session_id': session_id}
                    )
                    chat_service.save_message(
                        chat_id=chat_id,
                        message_content=response,
                        message_type='ai',
                        sender_info='system',
                        context={'session_id': session_id, 'blocked': True, 'reason': intent_result['reason']}
                    )
                except Exception as e:
                    print(f"[对话历史] 保存blocked消息失败: {e}")

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
        
        # 创建或获取Agent (支持UUID)
        agent = agent_manager.get_or_create_agent(
            session_id,
            agent_type,
            user_id=user_id_normalized,
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
        elif agent_type == "reminder":
            response, is_completed = agent.chat(message.message)
            stage = agent.stage.value
        else:  # report agent
            response, is_completed = agent.chat(message.message)
            stage = agent.stage.value

        # 更新会话中的当前stage（用于下次意图识别）
        sessions[session_id]["current_stage"] = stage

        # 保存消息到会话
        sessions[session_id]["messages"].append({
            "role": "user",
            "content": message.message
        })
        sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": response
        })

        # 保存消息到数据库
        chat_id = sessions[session_id].get("chat_id")
        if chat_id:
            try:
                # 保存用户消息
                chat_service.save_message(
                    chat_id=chat_id,
                    message_content=message.message,
                    message_type='user',
                    sender_info=f"{role}_{user_id_normalized or message.phone_number}",
                    context={'session_id': session_id}
                )

                # 保存AI消息
                chat_service.save_message(
                    chat_id=chat_id,
                    message_content=response,
                    message_type='ai',
                    sender_info=f'agent_{agent_type}',
                    context={
                        'session_id': session_id,
                        'stage': stage,
                        'is_completed': is_completed
                    }
                )

                # 更新对话的AI代理信息(如果还未设置)
                chat_info = chat_service.get_chat_by_id(chat_id)
                if chat_info and not chat_info.get('AI_Agent'):
                    from database.db_connection import DatabaseConnection
                    db = DatabaseConnection()
                    # 支持UUID和INT ID查询
                    chat_id_for_update = normalize_id(chat_id)
                    db.execute_update(
                        "UPDATE chat_conversation SET AI_Agent = %s WHERE Chat_UUID = %s OR CAST(Chat_ID AS CHAR) = %s",
                        (f'agent_{agent_type}', chat_id_for_update, chat_id_for_update)
                    )
                    db.close()

                # 如果是第一条消息,生成对话标题
                if chat_info and not chat_info.get('Title'):
                    # 简单地使用用户第一条消息的前30个字符作为标题
                    title = message.message[:30] + ('...' if len(message.message) > 30 else '')
                    chat_service.update_chat_title(chat_id, title)
                    print(f"[对话历史] 更新对话标题: {title}")

                print(f"[对话历史] 消息已保存到数据库: Chat_ID={chat_id}")

            except Exception as e:
                print(f"[对话历史] 保存消息失败: {e}")
                import traceback
                traceback.print_exc()

        print(f"[主程序] 对话完成状态: {is_completed}")

        # 3. 对于health agent,在信息收集完成后(APPOINTMENT_BOOKING阶段)尝试预约
        # 关键改变:不等到完全completed才处理预约,而是在预约阶段就处理
        if agent_type == "health" and hasattr(agent, 'needs_appointment') and agent.needs_appointment:
            # 【修复】必须在APPOINTMENT_BOOKING阶段才能执行预约,确保信息已收集完整
            if (hasattr(agent, 'appointment_confirmed') and not agent.appointment_confirmed 
                and stage == "appointment_booking"):  # 添加阶段检查
                try:
                    print("[调试] 检测到需要预约且尚未确认,且已到预约阶段,开始处理预约...")

                    # 获取患者数据
                    patient_data = agent.get_patient_data()

                    print(f"[调试] 患者数据: {json.dumps(patient_data, ensure_ascii=False)}")

                    # 调用预约服务
                    db_result = appointment_service.process_appointment(patient_data)

                    print(f"[数据库] 预约处理结果: {db_result}")

                    # 关键:将预约结果反馈给agent
                    agent.set_appointment_result(
                        success=db_result['success'],
                        message=db_result['message'],
                        appointment_info=db_result if db_result['success'] else None
                    )

                    if db_result['success']:
                        # 预约成功
                        sessions[session_id]["appointment_result"] = db_result

                        # 【修复】使用正确的键路径访问patient_id
                        # 在响应中添加预约成功信息
                        response += f"\n\n✅ {db_result['message']}"
                        response += f"\n预约ID：{db_result['appointment_id']}"
                        if 'appointment_details' in db_result and 'patient_id' in db_result['appointment_details']:
                            response += f"\n患者ID：{db_result['appointment_details']['patient_id']}"

                        # 预约成功后,重新检查完成状态(agent可能已经转入COMPLETED)
                        is_completed = agent.is_completed()
                        print(f"[主程序] 预约成功后,对话完成状态: {is_completed}")
                    else:
                        # 预约失败,agent会保持在APPOINTMENT_BOOKING阶段
                        # 获取失败响应并追加到回复中
                        failure_response = agent.get_appointment_failure_response()
                        if failure_response:
                            response = failure_response

                        # 确保对话未完成,继续收集信息
                        is_completed = False
                        print(f"[主程序] 预约失败,对话继续: {db_result['message']}")

                except Exception as e:
                    import traceback
                    print(f"[数据库错误] 预约处理失败: {str(e)}")
                    traceback.print_exc()

                    # 通知agent预约失败
                    if hasattr(agent, 'set_appointment_result'):
                        agent.set_appointment_result(success=False, message=f"系统错误: {str(e)}")

                    response += f"\n\n⚠️ 预约处理失败: {str(e)},请稍后重试。"
                    is_completed = False
        
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


@app.get("/api/patients/history/{phone_number}")
async def get_patient_history(phone_number: str):
    """
    根据手机号查询患者的完整历史记录
    包括基本信息、就诊记录、预约记录和处方信息

    Args:
        phone_number: 患者手机号

    Returns:
        包含患者完整历史信息的JSON对象
    """
    try:
        # 使用 UserHistoryServiceV2 查询完整历史信息
        history_data = user_history_service.get_user_complete_info_by_phone(phone_number)

        if not history_data.get("basic_info"):
            raise HTTPException(status_code=404, detail=f"未找到手机号 {phone_number} 对应的患者信息")

        # 查询处方信息
        try:
            prescriptions = prescription_service.get_prescriptions_by_phone(phone_number)
        except:
            prescriptions = []

        # 构造返回数据
        return {
            "success": True,
            "patient": history_data.get("basic_info"),
            "medical_records": history_data.get("medical_records", []),
            "appointments": history_data.get("appointments", []),
            "prescriptions": prescriptions
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询患者历史记录失败: {str(e)}")


# ==================== 报告相关API ====================

@app.post("/api/report/generate")
async def generate_report(request: ReportRequest):
    """
    生成病例报告PDF (支持UUID)

    Args:
        request: 包含patient_id或phone_number，以及可选的medical_record_id

    Returns:
        生成结果和文件路径
    """
    try:
        # 获取用户ID（支持UUID）
        patient_id = None
        if request.patient_id:
            try:
                patient_id = normalize_id(request.patient_id)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的患者ID格式: {request.patient_id}")

        if not patient_id and request.phone_number:
            user_info = report_service.db.execute_one(
                "SELECT Patient_UUID, Patient_ID FROM patient WHERE Phone_Number = %s",
                (request.phone_number,)
            )
            if user_info:
                # 优先使用UUID
                patient_id = user_info.get('Patient_UUID') or normalize_id(user_info['Patient_ID'])

        if not patient_id:
            raise HTTPException(status_code=400, detail="未提供有效的患者信息")

        # 如果指定了病例ID，生成单个报告（支持UUID）
        if request.medical_record_id:
            try:
                medical_record_id_normalized = normalize_id(request.medical_record_id)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的病例ID格式: {request.medical_record_id}")

            pdf_path = report_generator.generate_report_from_db(medical_record_id_normalized)
            if pdf_path:
                return {
                    "success": True,
                    "message": "报告生成成功",
                    "file_path": pdf_path,
                    "medical_record_id": medical_record_id_normalized
                }
            else:
                raise HTTPException(status_code=500, detail="报告生成失败")

        # 否则生成最新的报告
        reports = report_service.get_all_reports_by_patient(patient_id, limit=1)
        if not reports:
            raise HTTPException(status_code=404, detail="未找到病例记录")

        # 使用UUID（如果有）否则使用ID
        latest_record_id = reports[0].get('Medical_Record_UUID') or reports[0]['Medical_Record_ID']
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
async def get_report_history(patient_id: str):
    """
    获取用户的历史报告列表 (支持UUID)

    Args:
        patient_id: 用户ID（支持Patient_ID或Patient_UUID）

    Returns:
        报告列表
    """
    try:
        # 规范化patient_id
        try:
            patient_id_normalized = normalize_id(patient_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的患者ID格式: {patient_id}")

        reports = report_service.get_all_reports_by_patient(patient_id_normalized)
        return {
            "success": True,
            "patient_id": patient_id_normalized,
            "count": len(reports),
            "reports": reports
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询报告历史失败: {str(e)}")


@app.post("/api/report/analyze")
async def analyze_reports(request: AnalysisRequest):
    """
    分析历史报告 (支持UUID)

    Args:
        request: 包含patient_id或phone_number，以及analysis_type

    Returns:
        分析结果
    """
    try:
        # 获取用户ID（支持UUID）
        patient_id = None
        if request.patient_id:
            try:
                patient_id = normalize_id(request.patient_id)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的患者ID格式: {request.patient_id}")

        if not patient_id and request.phone_number:
            user_info = report_service.db.execute_one(
                "SELECT Patient_UUID, Patient_ID FROM patient WHERE Phone_Number = %s",
                (request.phone_number,)
            )
            if user_info:
                patient_id = user_info.get('Patient_UUID') or normalize_id(user_info['Patient_ID'])

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
            # 规范化所有record_ids
            normalized_record_ids = []
            for rid in request.record_ids:
                try:
                    normalized_record_ids.append(normalize_id(rid))
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"无效的病例ID格式: {rid}")
            result = agent.compare_records(normalized_record_ids)
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
    报告智能体对话接口 (支持UUID)

    与 /api/chat 类似，但使用 ReportAgent
    """
    try:
        # 生成或获取会话ID
        session_id = message.session_id or str(uuid.uuid4())

        # 规范化user_id
        user_id_normalized = None
        if message.user_id is not None:
            try:
                user_id_normalized = normalize_id(message.user_id)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的用户ID格式: {message.user_id}")

        print(f"\n[报告Agent] 收到对话请求:")
        print(f"  - session_id: {session_id}")
        print(f"  - user_id: {user_id_normalized}")
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
            user_id=user_id_normalized,
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
    """处方请求模型 (支持UUID)"""
    prescription_id: Union[str, int]  # 支持Prescription_ID或Prescription_UUID
    patient_id: Optional[Union[str, int]] = None  # 支持Patient_ID或Patient_UUID
    phone_number: Optional[str] = None


@app.post("/api/prescription/generate")
async def generate_prescription(request: PrescriptionRequest):
    """
    生成处方单PDF (支持UUID)

    Args:
        request: 包含prescription_id（必填），以及可选的patient_id/phone_number用于验证

    Returns:
        生成结果和文件路径
    """
    try:
        # 规范化prescription_id
        try:
            prescription_id_normalized = normalize_id(request.prescription_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的处方ID格式: {request.prescription_id}")

        print(f"[处方API] 收到生成处方单请求: Prescription_ID={prescription_id_normalized}")

        # 可选：验证处方是否属于指定患者
        if request.patient_id or request.phone_number:
            prescription_data = prescription_service.get_prescription_full(prescription_id_normalized)
            if not prescription_data:
                raise HTTPException(status_code=404, detail="未找到处方记录")

            # 验证患者ID
            if request.patient_id:
                try:
                    patient_id_normalized = normalize_id(request.patient_id)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"无效的患者ID格式: {request.patient_id}")

                # 比较UUID或ID
                prescription_patient_uuid = prescription_data['patient_info'].get('patient_uuid')
                prescription_patient_id = str(prescription_data['patient_info'].get('patient_id', ''))
                if patient_id_normalized not in [prescription_patient_uuid, prescription_patient_id]:
                    raise HTTPException(status_code=403, detail="无权访问此处方")

            # 验证手机号
            if request.phone_number:
                if prescription_data['patient_info']['phone'] != request.phone_number:
                    raise HTTPException(status_code=403, detail="无权访问此处方")

        # 生成处方单
        pdf_path = prescription_generator.generate_prescription_from_db(prescription_id_normalized)

        if pdf_path:
            return {
                "success": True,
                "message": "处方单生成成功",
                "file_path": pdf_path,
                "prescription_id": prescription_id_normalized
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
async def get_prescription_list(patient_id: str, limit: int = 50):
    """
    获取患者的处方列表 (支持UUID)

    Args:
        patient_id: 患者ID（支持Patient_ID或Patient_UUID）
        limit: 返回记录数限制（默认50）

    Returns:
        处方摘要列表
    """
    try:
        # 规范化patient_id
        try:
            patient_id_normalized = normalize_id(patient_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的患者ID格式: {patient_id}")

        print(f"[处方API] 查询患者处方列表: Patient_ID={patient_id_normalized}")

        prescriptions = prescription_service.get_prescriptions_by_patient(patient_id_normalized, limit)

        return {
            "success": True,
            "patient_id": patient_id_normalized,
            "count": len(prescriptions),
            "prescriptions": prescriptions
        }

    except HTTPException:
        raise
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
async def get_prescription_detail(prescription_id: str):
    """
    获取单个处方的完整详情 (支持UUID)

    Args:
        prescription_id: 处方ID（支持Prescription_ID或Prescription_UUID）

    Returns:
        完整处方信息（包含药物明细）
    """
    try:
        # 规范化prescription_id
        try:
            prescription_id_normalized = normalize_id(prescription_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的处方ID格式: {prescription_id}")

        print(f"[处方API] 查询处方详情: Prescription_ID={prescription_id_normalized}")

        prescription_data = prescription_service.get_prescription_full(prescription_id_normalized)

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
    """提醒请求模型 (支持UUID)"""
    patient_id: Optional[Union[str, int]] = None  # 支持Patient_ID或Patient_UUID
    phone_number: Optional[str] = None
    reminder_id: Optional[Union[str, int]] = None  # 支持Reminder_ID或Reminder_UUID
    status: Optional[str] = None
    reminder_type: Optional[str] = None


@app.get("/api/reminder/list/{patient_id}")
async def get_reminder_list(patient_id: str, status: Optional[str] = None, limit: int = 50):
    """
    获取患者的提醒列表 (支持UUID)

    Args:
        patient_id: 患者ID（支持Patient_ID或Patient_UUID）
        status: 状态过滤 (pending/sent/completed/cancelled/expired)
        limit: 返回记录数限制（默认50）

    Returns:
        提醒列表
    """
    try:
        # 规范化patient_id
        try:
            patient_id_normalized = normalize_id(patient_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的患者ID格式: {patient_id}")

        print(f"[提醒API] 查询患者提醒列表: Patient_ID={patient_id_normalized}, Status={status}")

        reminders = reminder_service.get_reminders_by_patient(patient_id_normalized, status=status, limit=limit)

        return {
            "success": True,
            "patient_id": patient_id_normalized,
            "count": len(reminders),
            "reminders": reminders
        }

    except HTTPException:
        raise
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


# ==================== 对话历史相关API ====================

@app.get("/api/chat/history/patient/{patient_id}")
async def get_patient_chat_history(patient_id: str, status: Optional[str] = None, limit: int = 20):
    """
    获取患者的对话历史列表 (支持UUID)

    Args:
        patient_id: 患者ID（支持Patient_ID或Patient_UUID）
        status: 状态过滤 (active/archived/closed)
        limit: 返回记录数限制

    Returns:
        对话历史列表
    """
    try:
        # 规范化patient_id
        try:
            patient_id_normalized = normalize_id(patient_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的患者ID格式: {patient_id}")

        print(f"[对话历史API] 查询患者对话历史: Patient_ID={patient_id_normalized}, Status={status}")

        chats = chat_service.get_user_chats(
            user_type='patient',
            user_id=patient_id_normalized,
            status=status,
            limit=limit
        )

        return {
            "success": True,
            "patient_id": patient_id_normalized,
            "count": len(chats),
            "chats": chats
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询对话历史失败: {str(e)}")


@app.get("/api/chat/history/phone/{phone_number}")
async def get_chat_history_by_phone(phone_number: str, status: Optional[str] = None, limit: int = 20):
    """
    通过手机号获取患者的对话历史列表

    Args:
        phone_number: 患者手机号
        status: 状态过滤
        limit: 返回记录数限制

    Returns:
        对话历史列表
    """
    try:
        print(f"[对话历史API] 通过手机号查询对话历史: Phone={phone_number}, Status={status}")

        # 先获取patient_id
        from database.user_history_service_v2 import UserHistoryServiceV2
        user_service = UserHistoryServiceV2()
        user_info = user_service.get_user_by_phone(phone_number)

        if not user_info:
            raise HTTPException(status_code=404, detail="未找到该手机号对应的用户")

        patient_id = user_info['Patient_ID']

        chats = chat_service.get_user_chats(
            user_type='patient',
            user_id=patient_id,
            status=status,
            limit=limit
        )

        return {
            "success": True,
            "phone_number": phone_number,
            "patient_id": patient_id,
            "count": len(chats),
            "chats": chats
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询对话历史失败: {str(e)}")


@app.get("/api/chat/messages/{chat_id}")
async def get_chat_messages(chat_id: str, limit: Optional[int] = None, offset: int = 0):
    """
    获取对话的所有消息 (支持UUID)

    Args:
        chat_id: 对话ID（支持Chat_ID或Chat_UUID）
        limit: 返回消息数量限制
        offset: 偏移量(用于分页)

    Returns:
        消息列表
    """
    try:
        # 规范化chat_id
        try:
            chat_id_normalized = normalize_id(chat_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的对话ID格式: {chat_id}")

        print(f"[对话历史API] 查询对话消息: Chat_ID={chat_id_normalized}")

        messages = chat_service.get_chat_messages(
            chat_id=chat_id_normalized,
            limit=limit,
            offset=offset
        )

        # 获取对话元数据(标题、AI代理等信息)
        chat = chat_service.get_chat_by_id(chat_id_normalized)

        return {
            "success": True,
            "chat_id": chat_id_normalized,
            "count": len(messages),
            "messages": messages,
            "chat": chat
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询对话消息失败: {str(e)}")


@app.get("/api/chat/recent/{patient_id}")
async def get_recent_chats_with_preview(patient_id: str, limit: int = 10):
    """
    获取患者最近的对话及最后一条消息预览 (支持UUID)

    Args:
        patient_id: 患者ID（支持Patient_ID或Patient_UUID）
        limit: 返回数量限制

    Returns:
        对话列表(包含最后一条消息)
    """
    try:
        # 规范化patient_id
        try:
            patient_id_normalized = normalize_id(patient_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的患者ID格式: {patient_id}")

        print(f"[对话历史API] 查询最近对话: Patient_ID={patient_id_normalized}")

        chats = chat_service.get_recent_chats_with_last_message(
            user_type='patient',
            user_id=patient_id_normalized,
            limit=limit
        )

        return {
            "success": True,
            "patient_id": patient_id_normalized,
            "count": len(chats),
            "chats": chats
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询最近对话失败: {str(e)}")


@app.get("/api/chat/stats/{chat_id}")
async def get_chat_statistics(chat_id: str):
    """
    获取对话的统计信息 (支持UUID)

    Args:
        chat_id: 对话ID（支持Chat_ID或Chat_UUID）

    Returns:
        统计信息
    """
    try:
        # 规范化chat_id
        try:
            chat_id_normalized = normalize_id(chat_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的对话ID格式: {chat_id}")

        print(f"[对话历史API] 查询对话统计: Chat_ID={chat_id_normalized}")

        stats = chat_service.get_chat_statistics(chat_id_normalized)

        if not stats:
            raise HTTPException(status_code=404, detail="未找到对话统计信息")

        return {
            "success": True,
            "stats": stats
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询对话统计失败: {str(e)}")


@app.post("/api/chat/archive/{chat_id}")
async def archive_chat_conversation(chat_id: str):
    """
    归档对话 (支持UUID)

    Args:
        chat_id: 对话ID（支持Chat_ID或Chat_UUID）

    Returns:
        操作结果
    """
    try:
        # 规范化chat_id
        try:
            chat_id_normalized = normalize_id(chat_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的对话ID格式: {chat_id}")

        print(f"[对话历史API] 归档对话: Chat_ID={chat_id_normalized}")

        success = chat_service.archive_chat(chat_id_normalized)

        if success:
            return {
                "success": True,
                "message": "对话已归档",
                "chat_id": chat_id_normalized
            }
        else:
            raise HTTPException(status_code=500, detail="归档对话失败")

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"归档对话失败: {str(e)}")


@app.delete("/api/chat/delete/{chat_id}")
async def delete_chat_conversation(chat_id: str):
    """
    删除对话(会级联删除所有消息) (支持UUID)

    Args:
        chat_id: 对话ID（支持Chat_ID或Chat_UUID）

    Returns:
        操作结果
    """
    try:
        # 规范化chat_id
        try:
            chat_id_normalized = normalize_id(chat_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的对话ID格式: {chat_id}")

        print(f"[对话历史API] 删除对话: Chat_ID={chat_id_normalized}")

        success = chat_service.delete_chat(chat_id_normalized)

        if success:
            return {
                "success": True,
                "message": "对话已删除",
                "chat_id": chat_id_normalized
            }
        else:
            raise HTTPException(status_code=500, detail="删除对话失败")

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"删除对话失败: {str(e)}")


@app.post("/api/chat/reminder", response_model=ChatResponse)
async def chat_reminder(message: ChatMessage):
    """
    提醒智能体对话接口 (支持UUID)

    与 /api/chat 类似，但使用 ReminderAgent
    """
    try:
        # 生成或获取会话ID
        session_id = message.session_id or str(uuid.uuid4())

        # 规范化user_id
        user_id_normalized = None
        if message.user_id is not None:
            try:
                user_id_normalized = normalize_id(message.user_id)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的用户ID格式: {message.user_id}")

        print(f"\n[提醒Agent] 收到对话请求:")
        print(f"  - session_id: {session_id}")
        print(f"  - user_id: {user_id_normalized}")
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
            user_id=user_id_normalized,
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
    
    # 执行启动初始化任务
    from utils.startup_tasks import on_startup
    on_startup()


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    print("系统正在关闭...")
    # 关闭数据库连接
    appointment_service.close()
    report_service.close()
    prescription_service.close()
    reminder_service.close()
    chat_service.__del__()  # 关闭chat_service数据库连接
    print("数据库连接已关闭")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

