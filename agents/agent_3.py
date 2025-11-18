"""
3号智能体 - 提醒管理（复诊提醒、预约提醒、用药提醒）+ 生物力学报告生成
"""
import json
from enum import Enum
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from utils.llm_config import get_llm
from database.reminder_service import ReminderService
from database.user_history_service_v2 import UserHistoryServiceV2
from database.biomechanics_service import BiomechanicsService
from utils.biomechanics_report_generator import BiomechanicsReportGenerator


class ReminderStage(Enum):
    """对话阶段"""
    GREETING = "greeting"  # 问候阶段
    SELECT_ACTION = "select_action"  # 选择操作
    VIEW_REMINDERS = "view_reminders"  # 查看提醒
    CREATE_REMINDER = "create_reminder"  # 创建提醒
    UPDATE_REMINDER = "update_reminder"  # 更新提醒
    CONFIG_SETTINGS = "config_settings"  # 配置设置
    GENERATE_BIOMECHANICS_REPORT = "generate_biomechanics_report"  # 生成生物力学报告
    COMPLETED = "completed"  # 完成


class ReminderAgent:
    """3号提醒管理智能体"""

    def __init__(self, patient_id: int = None, phone_number: str = None, role: str = "patient"):
        """
        初始化提醒智能体

        Args:
            patient_id: 用户ID（Patient_ID）
            phone_number: 手机号（推荐使用）
            role: 用户角色（patient/doctor）
        """
        self.llm = get_llm()
        self.stage = ReminderStage.GREETING
        self.conversation_history = []

        # 用户角色
        self.role = role  # patient 或 doctor

        # 用户信息
        self.patient_id = patient_id
        self.phone_number = phone_number

        # 服务实例
        self.reminder_service = ReminderService()
        self.history_service = UserHistoryServiceV2()
        self.biomechanics_service = BiomechanicsService()
        self.biomechanics_generator = BiomechanicsReportGenerator()

        # 用户数据
        self.user_info = None
        self.reminders = []
        self.reminder_config = None
        self.load_user_data()

        # 当前操作相关
        self.selected_reminder_id = None
        self.pending_reminder_data = {}
        self.pending_biomechanics_data = {}

        # 初始化对话链
        self.conversation_chain = self._create_conversation_chain()

    def load_user_data(self):
        """加载用户数据"""
        try:
            # 优先使用手机号
            if self.phone_number:
                self.user_info = self.history_service.get_user_by_phone(self.phone_number)
                if self.user_info:
                    self.patient_id = self.user_info['Patient_ID']
                    self.reminders = self.reminder_service.get_reminders_by_phone(self.phone_number)
                    self.reminder_config = self.reminder_service.get_reminder_config(self.patient_id)
            elif self.patient_id:
                self.user_info = self.history_service.get_user_by_id(self.patient_id)
                if self.user_info:
                    self.reminders = self.reminder_service.get_reminders_by_patient(self.patient_id)
                    self.reminder_config = self.reminder_service.get_reminder_config(self.patient_id)

            print(f"[ReminderAgent] 加载用户数据完成: patient_id={self.patient_id}, 提醒数={len(self.reminders)}")

        except Exception as e:
            print(f"[ReminderAgent] 加载用户数据失败: {e}")

    def _create_conversation_chain(self):
        """创建对话链"""
        template = """你是小Reminder，一位专业的健康提醒助手，负责帮助用户管理复诊提醒、预约提醒和用药提醒。

当前对话阶段：{stage}
当前用户角色：{role}

用户信息：
{user_info}

当前提醒列表：
{reminders_summary}

提醒配置：
{config_info}

对话历史：
{history}

你的职责：
1. 查看和管理用户的所有提醒
2. 创建新的复诊、预约或用药提醒
3. 更新或取消现有提醒
4. 帮助用户配置提醒偏好设置
5. 提供友好的提醒时间建议
6. 生成生物力学检查报告（基础报告或详细报告）

可用操作：
- 查看提醒：显示所有待处理的提醒
- 创建提醒：为复诊、预约或用药创建新提醒
- 更新提醒：修改提醒时间或取消提醒
- 配置设置：调整提醒偏好（提前天数、通知方式等）
- 生成生物力学报告：生成眼科生物力学检查报告

用户消息：{input}

请根据当前阶段和用户消息，给出专业、友好的回复。如果用户想执行某个操作，引导用户提供必要信息。
"""

        prompt = PromptTemplate(
            input_variables=["stage", "role", "user_info", "reminders_summary", "config_info", "history", "input"],
            template=template
        )

        return LLMChain(llm=self.llm, prompt=prompt)

    def chat(self, user_message: str) -> tuple[str, bool]:
        """
        处理用户消息

        Args:
            user_message: 用户消息

        Returns:
            (AI响应, 是否完成)
        """
        print(f"\n[ReminderAgent] 收到消息: {user_message[:50]}...")
        print(f"[ReminderAgent] 当前阶段: {self.stage.value}")

        # 检查是否是特殊命令
        command_result = self._handle_command(user_message)
        if command_result:
            return command_result

        # 构建对话上下文
        user_info_text = self._format_user_info()
        reminders_summary = self._format_reminders_summary()
        config_info = self._format_config_info()
        history_text = self._format_conversation_history()

        # 调用LLM生成响应
        try:
            response = self.conversation_chain.run(
                stage=self.stage.value,
                role=self.role,
                user_info=user_info_text,
                reminders_summary=reminders_summary,
                config_info=config_info,
                history=history_text,
                input=user_message
            )

            # 保存对话历史
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })

            # 更新对话阶段
            self._update_stage(user_message, response)

            is_completed = self.stage == ReminderStage.COMPLETED

            print(f"[ReminderAgent] 响应生成完成，下一阶段: {self.stage.value}")

            return response, is_completed

        except Exception as e:
            print(f"[ReminderAgent] 对话处理异常: {e}")
            import traceback
            traceback.print_exc()
            return f"抱歉，处理消息时遇到问题：{str(e)}", False

    def _handle_command(self, message: str) -> Optional[tuple[str, bool]]:
        """
        处理特殊命令

        Args:
            message: 用户消息

        Returns:
            如果是命令则返回(响应, 是否完成)，否则返回None
        """
        message_lower = message.lower().strip()

        # 如果正在创建提醒，处理用户输入
        if self.stage == ReminderStage.CREATE_REMINDER:
            return self._handle_create_reminder_input(message), False

        # 如果正在生成生物力学报告，处理用户输入
        if self.stage == ReminderStage.GENERATE_BIOMECHANICS_REPORT:
            # 从数据库获取最新的检查数据
            scan_data = None
            if self.phone_number:
                scan_data = self.biomechanics_service.get_latest_scan_by_phone(self.phone_number)
            elif self.patient_id:
                scan_data = self.biomechanics_service.get_latest_scan_by_patient(self.patient_id)

            return self.handle_biomechanics_report_input(message, scan_data)

        # 查看所有提醒
        if any(kw in message for kw in ['查看提醒', '我的提醒', '提醒列表', '所有提醒']):
            return self._cmd_view_reminders(), False

        # 查看待处理提醒
        if any(kw in message for kw in ['待处理', '未完成', 'pending']):
            return self._cmd_view_pending_reminders(), False

        # 创建复诊提醒
        if '创建复诊提醒' in message or '添加复诊提醒' in message or '新建复诊提醒' in message:
            self.stage = ReminderStage.CREATE_REMINDER
            self.pending_reminder_data = {'type': 'follow_up', 'step': 1}
            return "好的，我来帮您创建复诊提醒。\n\n请告诉我复诊日期（例如：2025-12-01 或 明天/后天）", False

        # 创建预约提醒
        if '创建预约提醒' in message or '添加预约提醒' in message or '新建预约提醒' in message:
            self.stage = ReminderStage.CREATE_REMINDER
            self.pending_reminder_data = {'type': 'appointment', 'step': 1}
            return "好的，我来帮您创建预约提醒。\n\n请告诉我预约时间（例如：2025-12-01 14:00 或 明天下午2点）", False

        # 创建用药提醒
        if '创建用药提醒' in message or '添加用药提醒' in message or '新建用药提醒' in message:
            self.stage = ReminderStage.CREATE_REMINDER
            self.pending_reminder_data = {'type': 'medication', 'step': 1}
            return "好的，我来帮您创建用药提醒。\n\n请告诉我药物名称：", False

        # 取消提醒
        if '取消提醒' in message or '删除提醒' in message:
            # 提取提醒ID
            import re
            match = re.search(r'(?:ID|id|编号)[:\s]*(\d+)', message)
            if match:
                reminder_id = int(match.group(1))
                return self._cmd_cancel_reminder(reminder_id), False
            else:
                # 显示待处理的提醒让用户选择
                return self._cmd_show_reminders_for_cancel(), False

        # 完成提醒
        if '完成提醒' in message or '标记完成' in message:
            import re
            match = re.search(r'(?:ID|id|编号)[:\s]*(\d+)', message)
            if match:
                reminder_id = int(match.group(1))
                return self._cmd_complete_reminder(reminder_id), False
            else:
                return "请告诉我要完成的提醒ID，例如：完成提醒 ID:1", False

        # 配置设置
        if '配置' in message or '设置' in message or '偏好' in message:
            self.stage = ReminderStage.CONFIG_SETTINGS
            return self._cmd_show_config(), False

        # 生成生物力学报告
        if any(kw in message for kw in ['生成生物力学报告', '生物力学报告', '眼科检查报告', '生成报告']):
            # 检查权限（仅医生可以生成报告）
            if self.role != "doctor":
                return "抱歉，只有医生才能生成生物力学报告。", False

            self.stage = ReminderStage.GENERATE_BIOMECHANICS_REPORT
            self.pending_biomechanics_data = {'step': 1}
            return self._cmd_start_biomechanics_report(), False

        return None

    def _cmd_view_reminders(self) -> str:
        """查看所有提醒"""
        if not self.reminders:
            return "您目前还没有任何提醒记录。\n\n您可以创建复诊提醒、预约提醒或用药提醒。"

        # 按状态分组
        pending = [r for r in self.reminders if r['Status'] == 'pending']
        sent = [r for r in self.reminders if r['Status'] == 'sent']
        completed = [r for r in self.reminders if r['Status'] == 'completed']

        response = f"📋 **您的提醒列表**\n\n"

        if pending:
            response += f"⏰ **待处理** ({len(pending)}条)\n"
            for r in pending[:5]:  # 最多显示5条
                response += self._format_reminder_item(r)
            if len(pending) > 5:
                response += f"... 还有 {len(pending) - 5} 条待处理提醒\n"
            response += "\n"

        if sent:
            response += f"✉️ **已发送** ({len(sent)}条)\n"
            for r in sent[:3]:
                response += self._format_reminder_item(r)
            response += "\n"

        if completed:
            response += f"✅ **已完成** ({len(completed)}条)\n\n"

        response += "\n您可以：\n- 查看详情：「查看提醒 ID:X」\n- 取消提醒：「取消提醒 ID:X」\n- 完成提醒：「完成提醒 ID:X」"

        return response

    def _cmd_view_pending_reminders(self) -> str:
        """查看待处理提醒"""
        pending = [r for r in self.reminders if r['Status'] == 'pending']

        if not pending:
            return "您目前没有待处理的提醒。"

        response = f"⏰ **待处理提醒** ({len(pending)}条)\n\n"

        for r in pending:
            response += self._format_reminder_item(r, detailed=True)

        return response

    def _cmd_cancel_reminder(self, reminder_id: int) -> str:
        """取消提醒"""
        result = self.reminder_service.update_reminder_status(
            reminder_id=reminder_id,
            status='cancelled',
            action_by=self.role
        )

        if result['success']:
            # 重新加载提醒列表
            self.load_user_data()
            return f"✅ 提醒已成功取消（ID:{reminder_id}）"
        else:
            return f"❌ 取消提醒失败：{result['message']}"

    def _cmd_complete_reminder(self, reminder_id: int) -> str:
        """完成提醒"""
        result = self.reminder_service.update_reminder_status(
            reminder_id=reminder_id,
            status='completed',
            action_by=self.role
        )

        if result['success']:
            self.load_user_data()
            return f"✅ 提醒已标记为完成（ID:{reminder_id}）"
        else:
            return f"❌ 标记失败：{result['message']}"

    def _cmd_show_config(self) -> str:
        """显示配置"""
        if not self.reminder_config:
            return "未找到您的提醒配置。"

        config = self.reminder_config
        response = "⚙️ **提醒配置**\n\n"
        response += f"复诊提醒：{'✅ 已启用' if config['Enable_Follow_Up'] else '❌ 已禁用'}\n"
        response += f"预约提醒：{'✅ 已启用' if config['Enable_Appointment'] else '❌ 已禁用'}\n"
        response += f"用药提醒：{'✅ 已启用' if config['Enable_Medication'] else '❌ 已禁用'}\n"
        response += f"默认提前天数：{config['Default_Advance_Days']} 天\n"
        response += f"通知方式：{config['Preferred_Notification_Method']}\n"
        response += f"免打扰时间：{config['Quiet_Hours_Start']} - {config['Quiet_Hours_End']}\n"

        response += "\n您可以通过对话修改这些设置。"

        return response

    def _cmd_show_reminders_for_cancel(self) -> str:
        """显示待处理的提醒供用户选择取消"""
        pending = [r for r in self.reminders if r['Status'] == 'pending']

        if not pending:
            return "您目前没有待处理的提醒可以取消。"

        response = "📋 **待处理的提醒** (可取消)\n\n"

        for r in pending[:10]:  # 最多显示10条
            response += self._format_reminder_item(r, detailed=False)

        response += "\n请回复：「取消提醒 ID:X」来取消指定的提醒"

        return response

    def _handle_create_reminder_input(self, message: str) -> str:
        """
        处理创建提醒时的用户输入

        Args:
            message: 用户输入

        Returns:
            响应消息
        """
        reminder_type = self.pending_reminder_data.get('type')
        step = self.pending_reminder_data.get('step', 1)

        # 取消创建
        if message in ['取消', '不了', '算了']:
            self.stage = ReminderStage.SELECT_ACTION
            self.pending_reminder_data = {}
            return "好的，已取消创建提醒。还有什么我可以帮您的吗？"

        try:
            if reminder_type == 'follow_up':
                return self._create_follow_up_reminder(message, step)
            elif reminder_type == 'appointment':
                return self._create_appointment_reminder_flow(message, step)
            elif reminder_type == 'medication':
                return self._create_medication_reminder_flow(message, step)
            else:
                self.stage = ReminderStage.SELECT_ACTION
                return "抱歉，未知的提醒类型。"

        except Exception as e:
            print(f"[ReminderAgent] 创建提醒失败: {e}")
            import traceback
            traceback.print_exc()
            self.stage = ReminderStage.SELECT_ACTION
            self.pending_reminder_data = {}
            return f"抱歉，创建提醒时出错：{str(e)}\n\n请稍后重试。"

    def _create_follow_up_reminder(self, message: str, step: int) -> str:
        """创建复诊提醒的流程"""
        if step == 1:
            # 解析日期
            scheduled_time = self._parse_datetime(message)
            if not scheduled_time:
                return "抱歉，无法识别日期格式。请重新输入（例如：2025-12-01 或 明天）"

            self.pending_reminder_data['scheduled_time'] = scheduled_time
            self.pending_reminder_data['step'] = 2

            return f"好的，复诊日期设为：{scheduled_time.strftime('%Y年%m月%d日')}\n\n请问需要提前几天提醒您？（直接输入数字，默认3天）"

        elif step == 2:
            # 解析提前天数
            import re
            match = re.search(r'(\d+)', message)
            advance_days = int(match.group(1)) if match else 3

            scheduled_time = self.pending_reminder_data['scheduled_time']

            # 调用service创建提醒
            result = self.reminder_service.create_follow_up_reminder(
                patient_id=self.patient_id,
                follow_up_date=scheduled_time,
                advance_days=advance_days,
                notes="用户自行创建"
            )

            # 清理状态
            self.stage = ReminderStage.SELECT_ACTION
            self.pending_reminder_data = {}

            # 重新加载提醒列表
            if result['success']:
                self.load_user_data()
                return f"✅ 复诊提醒创建成功！\n\n📅 复诊日期：{scheduled_time.strftime('%Y年%m月%d日')}\n⏰ 提前提醒：{advance_days}天\n\n我会在 {(scheduled_time - timedelta(days=advance_days)).strftime('%Y年%m月%d日')} 提醒您。"
            else:
                return f"❌ 创建失败：{result['message']}"

        return "处理错误"

    def _create_appointment_reminder_flow(self, message: str, step: int) -> str:
        """创建预约提醒的流程"""
        if step == 1:
            # 解析预约时间
            scheduled_time = self._parse_datetime(message)
            if not scheduled_time:
                return "抱歉，无法识别时间格式。请重新输入（例如：2025-12-01 14:00 或 明天下午2点）"

            self.pending_reminder_data['scheduled_time'] = scheduled_time
            self.pending_reminder_data['step'] = 2

            return f"好的，预约时间设为：{scheduled_time.strftime('%Y年%m月%d日 %H:%M')}\n\n请问需要提前几天提醒您？（直接输入数字，默认1天）"

        elif step == 2:
            # 解析提前天数
            import re
            match = re.search(r'(\d+)', message)
            advance_days = int(match.group(1)) if match else 1

            scheduled_time = self.pending_reminder_data['scheduled_time']

            # 创建预约提醒（通用方式，因为没有appointment_id）
            result = self.reminder_service.create_reminder(
                patient_id=self.patient_id,
                reminder_type='appointment',
                reminder_title='预约就诊提醒',
                reminder_content=f"您预约的就诊时间为 {scheduled_time.strftime('%Y年%m月%d日 %H:%M')}，请准时就诊。",
                scheduled_time=scheduled_time,
                advance_days=advance_days,
                priority='high',
                created_by=self.role
            )

            # 清理状态
            self.stage = ReminderStage.SELECT_ACTION
            self.pending_reminder_data = {}

            # 重新加载提醒列表
            if result['success']:
                self.load_user_data()
                return f"✅ 预约提醒创建成功！\n\n📅 预约时间：{scheduled_time.strftime('%Y年%m月%d日 %H:%M')}\n⏰ 提前提醒：{advance_days}天\n\n我会在 {(scheduled_time - timedelta(days=advance_days)).strftime('%Y年%m月%d日')} 提醒您。"
            else:
                return f"❌ 创建失败：{result['message']}"

        return "处理错误"

    def _create_medication_reminder_flow(self, message: str, step: int) -> str:
        """创建用药提醒的流程"""
        if step == 1:
            # 收集药物名称
            self.pending_reminder_data['medication_name'] = message
            self.pending_reminder_data['step'] = 2
            return f"药物名称：{message}\n\n请告诉我用法用量（例如：每日3次，每次1-2滴）："

        elif step == 2:
            # 收集用法用量
            self.pending_reminder_data['dosage'] = message
            self.pending_reminder_data['step'] = 3
            return f"用法用量：{message}\n\n请告诉我疗程天数（例如：7）："

        elif step == 3:
            # 收集疗程天数并创建
            import re
            match = re.search(r'(\d+)', message)
            if not match:
                return "请输入有效的天数（例如：7）"

            duration_days = int(match.group(1))
            medication_name = self.pending_reminder_data['medication_name']
            dosage = self.pending_reminder_data['dosage']

            # 创建用药提醒（通用方式，因为可能没有prescription_id）
            content = f"请按时服用 {medication_name}。\n用法用量：{dosage}"

            result = self.reminder_service.create_reminder(
                patient_id=self.patient_id,
                reminder_type='medication',
                reminder_title='用药提醒',
                reminder_content=content,
                scheduled_time=datetime.now() + timedelta(days=1),
                advance_days=0,
                priority='normal',
                repeat_type='daily',
                max_repeat_count=duration_days,
                created_by=self.role,
                notes=f"药物：{medication_name}，用法：{dosage}"
            )

            # 清理状态
            self.stage = ReminderStage.SELECT_ACTION
            self.pending_reminder_data = {}

            # 重新加载提醒列表
            if result['success']:
                self.load_user_data()
                return f"✅ 用药提醒创建成功！\n\n💊 药物：{medication_name}\n📋 用法：{dosage}\n📅 疗程：{duration_days}天\n⏰ 提醒频率：每日\n\n从明天开始，我会每天提醒您按时用药。"
            else:
                return f"❌ 创建失败：{result['message']}"

        return "处理错误"

    def _parse_datetime(self, text: str) -> Optional[datetime]:
        """
        解析日期时间字符串

        Args:
            text: 用户输入的日期时间文本

        Returns:
            解析后的datetime对象，失败返回None
        """
        import re
        from dateutil import parser as date_parser

        text = text.strip()

        # 处理相对日期
        today = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

        if '今天' in text or '今日' in text:
            # 尝试提取时间
            time_match = re.search(r'(\d{1,2})[点:：](\d{1,2})?', text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                return today.replace(hour=hour, minute=minute)
            return today

        elif '明天' in text or '明日' in text:
            base_time = today + timedelta(days=1)
            time_match = re.search(r'(\d{1,2})[点:：](\d{1,2})?', text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                return base_time.replace(hour=hour, minute=minute)
            return base_time

        elif '后天' in text:
            base_time = today + timedelta(days=2)
            time_match = re.search(r'(\d{1,2})[点:：](\d{1,2})?', text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                return base_time.replace(hour=hour, minute=minute)
            return base_time

        elif '下周' in text:
            return today + timedelta(days=7)

        elif '下个月' in text or '下月' in text:
            return today + timedelta(days=30)

        # 尝试解析标准日期格式
        try:
            # 尝试常见格式
            formats = [
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d',
                '%Y/%m/%d %H:%M',
                '%Y/%m/%d',
                '%m-%d %H:%M',
                '%m-%d',
                '%m月%d日 %H:%M',
                '%m月%d日',
            ]

            for fmt in formats:
                try:
                    parsed = datetime.strptime(text, fmt)
                    # 如果只有月日，补充年份
                    if parsed.year == 1900:
                        parsed = parsed.replace(year=today.year)
                        # 如果日期已过，设为明年
                        if parsed < today:
                            parsed = parsed.replace(year=today.year + 1)
                    return parsed
                except ValueError:
                    continue

            # 使用dateutil进行智能解析
            parsed = date_parser.parse(text, fuzzy=True)
            return parsed

        except Exception as e:
            print(f"[ReminderAgent] 日期解析失败: {e}")
            return None

    def _format_reminder_item(self, reminder: Dict[str, Any], detailed: bool = False) -> str:
        """格式化单个提醒项"""
        type_emoji = {
            'follow_up': '🏥',
            'appointment': '📅',
            'medication': '💊',
            'checkup': '🔬',
            'custom': '📝'
        }

        emoji = type_emoji.get(reminder['Reminder_Type'], '📝')
        title = reminder['Reminder_Title']
        scheduled_time = reminder['Scheduled_Time']
        reminder_id = reminder['Reminder_ID']

        if detailed:
            content = reminder['Reminder_Content']
            return f"{emoji} **{title}** (ID:{reminder_id})\n   时间：{scheduled_time}\n   内容：{content}\n\n"
        else:
            return f"{emoji} {title} - {scheduled_time} (ID:{reminder_id})\n"

    def _format_user_info(self) -> str:
        """格式化用户信息"""
        if not self.user_info:
            return "未登录用户"

        return f"""
姓名：{self.user_info.get('Name', '未知')}
手机号：{self.user_info.get('Phone_Number', '未知')}
患者ID：{self.patient_id}
        """.strip()

    def _format_reminders_summary(self) -> str:
        """格式化提醒摘要"""
        if not self.reminders:
            return "当前无提醒记录"

        pending_count = len([r for r in self.reminders if r['Status'] == 'pending'])
        total_count = len(self.reminders)

        return f"共 {total_count} 条提醒，其中 {pending_count} 条待处理"

    def _format_config_info(self) -> str:
        """格式化配置信息"""
        if not self.reminder_config:
            return "未配置"

        return f"""
复诊提醒：{'启用' if self.reminder_config['Enable_Follow_Up'] else '禁用'}
预约提醒：{'启用' if self.reminder_config['Enable_Appointment'] else '禁用'}
用药提醒：{'启用' if self.reminder_config['Enable_Medication'] else '禁用'}
提前天数：{self.reminder_config['Default_Advance_Days']} 天
        """.strip()

    def _format_conversation_history(self) -> str:
        """格式化对话历史"""
        if not self.conversation_history:
            return "暂无对话历史"

        # 只保留最近5轮对话
        recent = self.conversation_history[-10:]
        history_text = ""

        for msg in recent:
            role = "用户" if msg["role"] == "user" else "助手"
            content = msg["content"][:100]  # 截断过长内容
            history_text += f"{role}: {content}\n"

        return history_text.strip()

    def _update_stage(self, user_message: str, ai_response: str):
        """更新对话阶段"""
        # 简单的阶段转换逻辑
        if self.stage == ReminderStage.GREETING:
            self.stage = ReminderStage.SELECT_ACTION

        # 如果用户说再见或感谢（扩展关键词列表，与 Agent1 保持一致）
        farewell_keywords = ['好的', '好', '谢谢', '感谢', '明白了', '知道了', '再见', '拜拜', '没问题', '行', '可以']
        continue_keywords = ['还有', '另外', '还想', '再', '还需要', '继续', '但是', '不过']

        user_lower = user_message.lower().strip()
        has_farewell = any(kw in user_lower for kw in farewell_keywords)
        has_continue = any(kw in user_lower for kw in continue_keywords)
        is_short = len(user_message.strip()) <= 10

        if has_farewell and not has_continue and is_short:
            self.stage = ReminderStage.COMPLETED

    def is_completed(self) -> bool:
        """检查对话是否完成"""
        return self.stage == ReminderStage.COMPLETED

    def get_summary(self) -> Dict[str, Any]:
        """获取对话摘要"""
        pending_reminders = [r for r in self.reminders if r['Status'] == 'pending']

        return {
            'patient_id': self.patient_id,
            'total_reminders': len(self.reminders),
            'pending_reminders': len(pending_reminders),
            'reminder_config': self.reminder_config,
            'conversation_turns': len(self.conversation_history),
            'stage': self.stage.value
        }

    def _cmd_start_biomechanics_report(self) -> str:
        """开始生成生物力学报告流程"""
        return """📋 **生成生物力学报告**

我可以为您生成两种类型的眼科生物力学报告：

1️⃣ **基础报告** - 包含基本眼科生物测量数据
   - 眼轴长度 (AXL)
   - 角膜曲率 (K1, K2)
   - 前房深度 (ACD)
   - 晶状体厚度 (LT)
   - 角膜厚度 (CCT)
   - 角膜直径 (WTW)
   - 瞳孔直径 (PD)

2️⃣ **详细报告** - 包含完整的生物力学分析数据
   - 基础测量数据
   - 多区域角膜厚度分析
   - 角膜屈光力分析
   - 详细的生物力学参数

请回复：
- 「基础报告」或「1」- 生成基础报告
- 「详细报告」或「2」- 生成详细报告"""

    def generate_basic_biomechanics_report(self, scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成基础生物力学报告

        Args:
            scan_data: 检查数据字典，包含所有必需的占位符数据

        Returns:
            包含success, output_path, message的字典
        """
        try:
            result = self.biomechanics_generator.generate_basic_report(scan_data)
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'生成基础报告失败: {str(e)}'
            }

    def generate_detailed_biomechanics_report(self, scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成详细生物力学报告

        Args:
            scan_data: 检查数据字典，包含所有必需的占位符数据

        Returns:
            包含success, output_path, message的字典
        """
        try:
            result = self.biomechanics_generator.generate_detailed_report(scan_data)
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'生成详细报告失败: {str(e)}'
            }

    def handle_biomechanics_report_input(self, message: str, scan_data: Dict[str, Any]) -> tuple[str, bool]:
        """
        处理生物力学报告生成流程

        Args:
            message: 用户消息
            scan_data: 检查数据（从数据库或外部输入）

        Returns:
            (响应消息, 是否完成)
        """
        step = self.pending_biomechanics_data.get('step', 1)

        # 取消生成
        if message in ['取消', '不了', '算了']:
            self.stage = ReminderStage.SELECT_ACTION
            self.pending_biomechanics_data = {}
            return "好的，已取消生成报告。还有什么我可以帮您的吗？", False

        if step == 1:
            # 用户选择报告类型
            message_lower = message.lower().strip()

            if '基础' in message or message == '1':
                self.pending_biomechanics_data['report_type'] = 'basic'
                self.pending_biomechanics_data['step'] = 2

                # 显示需要的字段
                required_fields = self.biomechanics_generator.get_basic_template_fields()
                return f"""好的，我将为您生成基础生物力学报告。

📝 **需要的数据字段** ({len(required_fields)} 个)：
{', '.join(required_fields[:15])}...

请确保已经完成眼科生物测量检查。

是否继续？回复「继续」开始生成，或提供检查数据。""", False

            elif '详细' in message or message == '2':
                self.pending_biomechanics_data['report_type'] = 'detailed'
                self.pending_biomechanics_data['step'] = 2

                # 显示需要的字段
                required_fields = self.biomechanics_generator.get_detailed_template_fields()
                return f"""好的，我将为您生成详细生物力学报告。

📝 **需要的数据字段** ({len(required_fields)} 个)：
包括基础测量数据 + 多区域分析数据

请确保已经完成完整的生物力学检查。

是否继续？回复「继续」开始生成，或提供检查数据。""", False
            else:
                return "请选择报告类型：\n- 回复「基础报告」或「1」\n- 回复「详细报告」或「2」", False

        elif step == 2:
            # 执行报告生成
            report_type = self.pending_biomechanics_data.get('report_type')

            if not scan_data:
                return "❌ 错误：未找到检查数据。请先完成眼科生物测量检查。", False

            # 将数据库数据格式化为报告模板格式
            template_data = self.biomechanics_service.format_scan_for_report(scan_data, report_type)

            # 生成报告
            if report_type == 'basic':
                result = self.generate_basic_biomechanics_report(template_data)
            else:  # detailed
                result = self.generate_detailed_biomechanics_report(template_data)

            # 清理状态
            self.stage = ReminderStage.SELECT_ACTION
            self.pending_biomechanics_data = {}

            if result['success']:
                response = f"""✅ **报告生成成功！**

📄 报告类型：{'基础报告' if report_type == 'basic' else '详细报告'}
📁 保存位置：{result['output_path']}
✏️ 替换字段：{result['replacement_count']} 个
"""
                if result.get('remaining_placeholders'):
                    response += f"\n⚠️ 未替换字段：{len(result['remaining_placeholders'])} 个"
                    response += f"\n（{', '.join(result['remaining_placeholders'][:5])}...）"

                return response, False
            else:
                return f"❌ 生成报告失败：{result['message']}", False

        return "处理错误", False
