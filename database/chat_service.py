"""
对话历史记录服务类 + UUID支持
提供对话会话和消息的增删改查操作
支持患者(patient)和医生(doctor)两种用户类型
UUID支持：兼容INT和UUID格式的ID

Updated: 2025-11-20 (UUID support)
"""

import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
import json

from .db_connection import DatabaseConnection
from .base_service import BaseServiceWithUUID, normalize_id

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChatService(BaseServiceWithUUID):
    """对话历史记录服务类 (支持UUID)"""

    def __init__(self):
        """初始化对话服务"""
        super().__init__()
        self.db = DatabaseConnection()

    def __del__(self):
        """析构时关闭数据库连接"""
        self.db.close()

    # ==================== 对话会话管理 ====================

    def create_chat_for_patient(
        self,
        patient_id: Union[str, int],
        title: Optional[str] = None,
        conversation_type: str = 'general',
        ai_agent: Optional[str] = None
    ) -> Optional[str]:
        """
        为患者创建新对话会话

        Args:
            patient_id: 患者ID（支持Patient_ID或Patient_UUID）
            title: 对话标题(可选)
            conversation_type: 对话类型(general/consultation/appointment/report等)
            ai_agent: AI代理名称(agent_1/agent_2/agent_3等)

        Returns:
            新创建的Chat_UUID，失败返回None
        """
        try:
            # 规范化patient_id并查询Patient_ID和Patient_UUID
            patient_id_normalized = normalize_id(patient_id)

            # 查询Patient_ID和Patient_UUID
            if patient_id_normalized.isdigit():
                # 输入是INT，查询UUID
                patient_query = "SELECT Patient_ID, Patient_UUID FROM patient WHERE Patient_ID = %s"
                patient_result = self.db.execute_one(patient_query, (patient_id_normalized,))
                if not patient_result:
                    logger.error(f"未找到患者: {patient_id}")
                    return None
                patient_id_int = patient_result['Patient_ID']
                patient_uuid = patient_result['Patient_UUID']
            else:
                # 输入是UUID，查询INT
                patient_query = "SELECT Patient_ID, Patient_UUID FROM patient WHERE Patient_UUID = %s"
                patient_result = self.db.execute_one(patient_query, (patient_id_normalized,))
                if not patient_result:
                    logger.error(f"未找到患者: {patient_id}")
                    return None
                patient_id_int = patient_result['Patient_ID']
                patient_uuid = patient_result['Patient_UUID']

            # 使用Patient_ID和Patient_UUID插入 (约束要求Patient_ID NOT NULL)
            query = """
                INSERT INTO chat_conversation
                (User_Type, Patient_ID, Patient_UUID, Title, Conversation_Type, AI_Agent)
                VALUES ('patient', %s, %s, %s, %s, %s)
            """
            chat_id = self.db.execute_insert(query, (patient_id_int, patient_uuid, title, conversation_type, ai_agent))

            # 查询生成的Chat_UUID
            chat_uuid_query = "SELECT Chat_UUID FROM chat_conversation WHERE Chat_ID = %s"
            chat_result = self.db.execute_one(chat_uuid_query, (chat_id,))
            chat_uuid = chat_result['Chat_UUID'] if chat_result else None

            logger.info(f"为患者创建对话成功: Patient_UUID={patient_uuid}, Chat_UUID={chat_uuid}")
            return chat_uuid
        except Exception as e:
            logger.error(f"为患者创建对话失败: {e}")
            return None

    def create_chat_for_doctor(
        self,
        doctor_id: Union[str, int],
        title: Optional[str] = None,
        conversation_type: str = 'general',
        ai_agent: Optional[str] = None
    ) -> Optional[str]:
        """
        为医生创建新对话会话

        Args:
            doctor_id: 医生ID（支持Doctor_ID或Doctor_UUID）
            title: 对话标题(可选)
            conversation_type: 对话类型
            ai_agent: AI代理名称

        Returns:
            新创建的Chat_UUID，失败返回None
        """
        try:
            # 规范化doctor_id并查询Doctor_ID和Doctor_UUID
            doctor_id_normalized = normalize_id(doctor_id)

            # 查询Doctor_ID和Doctor_UUID
            if doctor_id_normalized.isdigit():
                # 输入是INT，查询UUID
                doctor_query = "SELECT Doctor_ID, Doctor_UUID FROM doctor WHERE Doctor_ID = %s"
                doctor_result = self.db.execute_one(doctor_query, (doctor_id_normalized,))
                if not doctor_result:
                    logger.error(f"未找到医生: {doctor_id}")
                    return None
                doctor_id_int = doctor_result['Doctor_ID']
                doctor_uuid = doctor_result['Doctor_UUID']
            else:
                # 输入是UUID，查询INT
                doctor_query = "SELECT Doctor_ID, Doctor_UUID FROM doctor WHERE Doctor_UUID = %s"
                doctor_result = self.db.execute_one(doctor_query, (doctor_id_normalized,))
                if not doctor_result:
                    logger.error(f"未找到医生: {doctor_id}")
                    return None
                doctor_id_int = doctor_result['Doctor_ID']
                doctor_uuid = doctor_result['Doctor_UUID']

            # 使用Doctor_ID和Doctor_UUID插入 (约束要求Doctor_ID NOT NULL)
            query = """
                INSERT INTO chat_conversation
                (User_Type, Doctor_ID, Doctor_UUID, Title, Conversation_Type, AI_Agent)
                VALUES ('doctor', %s, %s, %s, %s, %s)
            """
            chat_id = self.db.execute_insert(query, (doctor_id_int, doctor_uuid, title, conversation_type, ai_agent))

            # 查询生成的Chat_UUID
            chat_uuid_query = "SELECT Chat_UUID FROM chat_conversation WHERE Chat_ID = %s"
            chat_result = self.db.execute_one(chat_uuid_query, (chat_id,))
            chat_uuid = chat_result['Chat_UUID'] if chat_result else None

            logger.info(f"为医生创建对话成功: Doctor_UUID={doctor_uuid}, Chat_UUID={chat_uuid}")
            return chat_uuid
        except Exception as e:
            logger.error(f"为医生创建对话失败: {e}")
            return None

    def get_user_chats(
        self,
        user_type: str,
        user_id: Union[str, int],
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取用户的所有对话会话(支持患者和医生)

        Args:
            user_type: 用户类型('patient' 或 'doctor')
            user_id: 用户ID（支持Patient_ID/Patient_UUID或Doctor_ID/Doctor_UUID）
            status: 对话状态过滤('active'/'archived'/'closed'，None表示所有状态)
            limit: 返回记录的最大数量

        Returns:
            对话会话列表
        """
        try:
            user_id_normalized = normalize_id(user_id)

            if user_type == 'patient':
                base_query = """
                    SELECT * FROM chat_conversation
                    WHERE User_Type = 'patient'
                    AND (Patient_UUID = %s OR CAST(Patient_ID AS CHAR) = %s)
                """
                params = [user_id_normalized, user_id_normalized]
            elif user_type == 'doctor':
                base_query = """
                    SELECT * FROM chat_conversation
                    WHERE User_Type = 'doctor'
                    AND (Doctor_UUID = %s OR CAST(Doctor_ID AS CHAR) = %s)
                """
                params = [user_id_normalized, user_id_normalized]
            else:
                logger.error(f"无效的用户类型: {user_type}")
                return []

            # 添加状态过滤
            if status:
                base_query += " AND Status = %s"
                params.append(status)

            # 添加排序和限制
            base_query += " ORDER BY Updated_At DESC LIMIT %s"
            params.append(limit)

            results = self.db.execute_query(base_query, tuple(params))
            logger.info(f"查询到 {len(results)} 个对话会话: {user_type}={user_id}")
            return results
        except Exception as e:
            logger.error(f"查询用户对话失败: {e}")
            return []

    def get_chat_by_id(self, chat_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        根据Chat_ID或Chat_UUID获取对话会话详情

        Args:
            chat_id: 对话ID（支持Chat_ID或Chat_UUID）

        Returns:
            对话会话信息字典，未找到返回None
        """
        try:
            chat_id_normalized = normalize_id(chat_id)
            query = """
                SELECT * FROM chat_conversation
                WHERE Chat_UUID = %s OR CAST(Chat_ID AS CHAR) = %s
            """
            result = self.db.execute_one(query, (chat_id_normalized, chat_id_normalized))
            if result:
                logger.info(f"查询到对话: Chat_ID/UUID={chat_id}")
            else:
                logger.warning(f"未找到对话: Chat_ID/UUID={chat_id}")
            return result
        except Exception as e:
            logger.error(f"查询对话详情失败: {e}")
            return None

    def update_chat_title(self, chat_id: Union[str, int], title: str) -> bool:
        """
        更新对话标题

        Args:
            chat_id: 对话ID（支持Chat_ID或Chat_UUID）
            title: 新标题

        Returns:
            是否更新成功
        """
        try:
            chat_id_normalized = normalize_id(chat_id)
            query = """
                UPDATE chat_conversation SET Title = %s
                WHERE Chat_UUID = %s OR CAST(Chat_ID AS CHAR) = %s
            """
            self.db.execute_update(query, (title, chat_id_normalized, chat_id_normalized))
            logger.info(f"更新对话标题成功: Chat_ID={chat_id}, Title={title}")
            return True
        except Exception as e:
            logger.error(f"更新对话标题失败: {e}")
            return False

    def update_chat_summary(self, chat_id: Union[str, int], summary: str) -> bool:
        """
        更新对话摘要

        Args:
            chat_id: 对话ID（支持Chat_ID或Chat_UUID）
            summary: 对话摘要

        Returns:
            是否更新成功
        """
        try:
            chat_id_normalized = normalize_id(chat_id)
            query = """
                UPDATE chat_conversation SET Summary = %s
                WHERE Chat_UUID = %s OR CAST(Chat_ID AS CHAR) = %s
            """
            self.db.execute_update(query, (summary, chat_id_normalized, chat_id_normalized))
            logger.info(f"更新对话摘要成功: Chat_ID={chat_id}")
            return True
        except Exception as e:
            logger.error(f"更新对话摘要失败: {e}")
            return False

    def update_chat_status(self, chat_id: Union[str, int], status: str) -> bool:
        """
        更新对话状态

        Args:
            chat_id: 对话ID（支持Chat_ID或Chat_UUID）
            status: 新状态('active'/'archived'/'closed')

        Returns:
            是否更新成功
        """
        try:
            chat_id_normalized = normalize_id(chat_id)
            query = """
                UPDATE chat_conversation SET Status = %s
                WHERE Chat_UUID = %s OR CAST(Chat_ID AS CHAR) = %s
            """
            self.db.execute_update(query, (status, chat_id_normalized, chat_id_normalized))
            logger.info(f"更新对话状态成功: Chat_ID={chat_id}, Status={status}")
            return True
        except Exception as e:
            logger.error(f"更新对话状态失败: {e}")
            return False

    def archive_chat(self, chat_id: Union[str, int]) -> bool:
        """
        归档对话（将状态设置为'archived'）

        Args:
            chat_id: 对话ID（支持Chat_ID或Chat_UUID）

        Returns:
            是否归档成功
        """
        return self.update_chat_status(chat_id, 'archived')

    def close_chat(self, chat_id: Union[str, int]) -> bool:
        """
        关闭对话（将状态设置为'closed'）

        Args:
            chat_id: 对话ID（支持Chat_ID或Chat_UUID）

        Returns:
            是否关闭成功
        """
        return self.update_chat_status(chat_id, 'closed')

    def delete_chat(self, chat_id: Union[str, int]) -> bool:
        """
        删除对话（会级联删除所有相关消息）

        Args:
            chat_id: 对话ID（支持Chat_ID或Chat_UUID）

        Returns:
            是否删除成功
        """
        try:
            chat_id_normalized = normalize_id(chat_id)
            query = """
                DELETE FROM chat_conversation
                WHERE Chat_UUID = %s OR CAST(Chat_ID AS CHAR) = %s
            """
            self.db.execute_update(query, (chat_id_normalized, chat_id_normalized))
            logger.info(f"删除对话成功: Chat_ID={chat_id}")
            return True
        except Exception as e:
            logger.error(f"删除对话失败: {e}")
            return False

    # ==================== 消息管理 ====================

    def save_message(
        self,
        chat_id: Union[str, int],
        message_content: str,
        message_type: str,
        sender_info: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tokens_used: Optional[int] = None
    ) -> Optional[str]:
        """
        保存一条消息到对话中

        Args:
            chat_id: 对话ID（支持Chat_ID或Chat_UUID）
            message_content: 消息内容
            message_type: 消息类型('user' 或 'ai')
            sender_info: 发送者信息(可选)
            context: 消息上下文(字典格式，会转为JSON存储)
            tokens_used: 消耗的token数(可选)

        Returns:
            新创建的Message_UUID，失败返回None
        """
        try:
            # 规范化chat_id并查询Chat_UUID
            chat_id_normalized = normalize_id(chat_id)

            # 查询Chat_UUID
            chat_query = """
                SELECT Chat_ID, Chat_UUID FROM chat_conversation
                WHERE Chat_UUID = %s OR CAST(Chat_ID AS CHAR) = %s
            """
            chat_result = self.db.execute_one(chat_query, (chat_id_normalized, chat_id_normalized))
            if not chat_result:
                logger.error(f"未找到对话: {chat_id}")
                return None

            chat_uuid = chat_result['Chat_UUID']
            chat_id_int = chat_result['Chat_ID']

            # 获取当前对话的最大消息序号
            order_query = """
                SELECT COALESCE(MAX(Message_Order), 0) + 1 as next_order
                FROM chat_message cm
                INNER JOIN chat_conversation cc ON cm.Chat_UUID = cc.Chat_UUID
                WHERE cc.Chat_UUID = %s
            """
            result = self.db.execute_one(order_query, (chat_uuid,))
            next_order = result['next_order'] if result else 1

            # 将context字典转为JSON字符串
            context_json = json.dumps(context, ensure_ascii=False) if context else None

            # 插入消息（使用Chat_ID和Chat_UUID，Chat_ID是必需的）
            insert_query = """
                INSERT INTO chat_message
                (Chat_ID, Chat_UUID, Message_Order, Message_Content, Message_Type, Sender_Info, Context, Tokens_Used)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            message_id = self.db.execute_insert(
                insert_query,
                (chat_id_int, chat_uuid, next_order, message_content, message_type, sender_info, context_json, tokens_used)
            )

            # 查询生成的Message_UUID
            message_uuid_query = "SELECT Message_UUID FROM chat_message WHERE Message_ID = %s"
            message_result = self.db.execute_one(message_uuid_query, (message_id,))
            message_uuid = message_result['Message_UUID'] if message_result else None

            # 更新对话的消息总数
            update_query = """
                UPDATE chat_conversation
                SET Total_Messages = Total_Messages + 1
                WHERE Chat_UUID = %s
            """
            self.db.execute_update(update_query, (chat_uuid,))

            logger.info(f"保存消息成功: Chat_UUID={chat_uuid}, Message_UUID={message_uuid}, Type={message_type}")
            return message_uuid
        except Exception as e:
            logger.error(f"保存消息失败: {e}")
            return None

    def get_chat_messages(
        self,
        chat_id: Union[str, int],
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取对话的所有消息

        Args:
            chat_id: 对话ID（支持Chat_ID或Chat_UUID）
            limit: 返回消息数量限制(None表示所有)
            offset: 偏移量(用于分页)

        Returns:
            消息列表(按Message_Order升序)
        """
        try:
            chat_id_normalized = normalize_id(chat_id)
            base_query = """
                SELECT cm.*, cc.Chat_UUID
                FROM chat_message cm
                INNER JOIN chat_conversation cc ON cm.Chat_UUID = cc.Chat_UUID
                WHERE cc.Chat_UUID = %s OR CAST(cc.Chat_ID AS CHAR) = %s
                ORDER BY cm.Message_Order ASC
            """
            params = [chat_id_normalized, chat_id_normalized]

            if limit is not None:
                base_query += " LIMIT %s OFFSET %s"
                params.extend([limit, offset])

            results = self.db.execute_query(base_query, tuple(params))

            # 将JSON字符串的context转回字典
            for msg in results:
                if msg.get('Context'):
                    try:
                        msg['Context'] = json.loads(msg['Context'])
                    except json.JSONDecodeError:
                        msg['Context'] = None

            logger.info(f"查询到 {len(results)} 条消息: Chat_ID={chat_id}")
            return results
        except Exception as e:
            logger.error(f"查询消息失败: {e}")
            return []

    def get_message_by_id(self, message_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        根据Message_ID或Message_UUID获取单条消息

        Args:
            message_id: 消息ID（支持Message_ID或Message_UUID）

        Returns:
            消息信息字典，未找到返回None
        """
        try:
            message_id_normalized = normalize_id(message_id)
            query = """
                SELECT * FROM chat_message
                WHERE Message_UUID = %s OR CAST(Message_ID AS CHAR) = %s
            """
            result = self.db.execute_one(query, (message_id_normalized, message_id_normalized))

            if result and result.get('Context'):
                try:
                    result['Context'] = json.loads(result['Context'])
                except json.JSONDecodeError:
                    result['Context'] = None

            if result:
                logger.info(f"查询到消息: Message_ID/UUID={message_id}")
            else:
                logger.warning(f"未找到消息: Message_ID/UUID={message_id}")

            return result
        except Exception as e:
            logger.error(f"查询消息失败: {e}")
            return None

    def update_message_content(self, message_id: Union[str, int], new_content: str) -> bool:
        """
        更新消息内容

        Args:
            message_id: 消息ID（支持Message_ID或Message_UUID）
            new_content: 新内容

        Returns:
            是否更新成功
        """
        try:
            message_id_normalized = normalize_id(message_id)
            query = """
                UPDATE chat_message SET Message_Content = %s
                WHERE Message_UUID = %s OR CAST(Message_ID AS CHAR) = %s
            """
            self.db.execute_update(query, (new_content, message_id_normalized, message_id_normalized))
            logger.info(f"更新消息内容成功: Message_ID={message_id}")
            return True
        except Exception as e:
            logger.error(f"更新消息内容失败: {e}")
            return False

    def delete_message(self, message_id: Union[str, int]) -> bool:
        """
        删除单条消息

        Args:
            message_id: 消息ID（支持Message_ID或Message_UUID）

        Returns:
            是否删除成功
        """
        try:
            # 获取消息所属的Chat_UUID
            msg = self.get_message_by_id(message_id)
            if not msg:
                return False

            chat_uuid = msg['Chat_UUID']

            # 删除消息
            message_id_normalized = normalize_id(message_id)
            query = """
                DELETE FROM chat_message
                WHERE Message_UUID = %s OR CAST(Message_ID AS CHAR) = %s
            """
            self.db.execute_update(query, (message_id_normalized, message_id_normalized))

            # 更新对话的消息总数
            update_query = """
                UPDATE chat_conversation
                SET Total_Messages = Total_Messages - 1
                WHERE Chat_UUID = %s AND Total_Messages > 0
            """
            self.db.execute_update(update_query, (chat_uuid,))

            logger.info(f"删除消息成功: Message_ID={message_id}")
            return True
        except Exception as e:
            logger.error(f"删除消息失败: {e}")
            return False

    # ==================== 高级查询 ====================

    def get_recent_chats_with_last_message(
        self,
        user_type: str,
        user_id: Union[str, int],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取用户的最近对话，并包含每个对话的最后一条消息

        Args:
            user_type: 用户类型('patient' 或 'doctor')
            user_id: 用户ID（支持Patient_ID/Patient_UUID或Doctor_ID/Doctor_UUID）
            limit: 返回数量限制

        Returns:
            对话列表，每个对话包含last_message字段
        """
        try:
            chats = self.get_user_chats(user_type, user_id, status='active', limit=limit)

            for chat in chats:
                # 获取最后一条消息
                query = """
                    SELECT cm.* FROM chat_message cm
                    INNER JOIN chat_conversation cc ON cm.Chat_UUID = cc.Chat_UUID
                    WHERE cc.Chat_UUID = %s
                    ORDER BY cm.Message_Order DESC
                    LIMIT 1
                """
                last_msg = self.db.execute_one(query, (chat['Chat_UUID'],))
                if last_msg and last_msg.get('Context'):
                    try:
                        last_msg['Context'] = json.loads(last_msg['Context'])
                    except json.JSONDecodeError:
                        last_msg['Context'] = None

                chat['last_message'] = last_msg

            return chats
        except Exception as e:
            logger.error(f"查询最近对话失败: {e}")
            return []

    def get_chat_statistics(self, chat_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        获取对话的统计信息

        Args:
            chat_id: 对话ID（支持Chat_ID或Chat_UUID）

        Returns:
            统计信息字典
        """
        try:
            chat_id_normalized = normalize_id(chat_id)
            query = """
                SELECT
                    cc.Chat_ID,
                    cc.Chat_UUID,
                    COUNT(*) as total_messages,
                    SUM(CASE WHEN cm.Message_Type = 'user' THEN 1 ELSE 0 END) as user_messages,
                    SUM(CASE WHEN cm.Message_Type = 'ai' THEN 1 ELSE 0 END) as ai_messages,
                    SUM(COALESCE(cm.Tokens_Used, 0)) as total_tokens,
                    MIN(cm.Created_At) as first_message_time,
                    MAX(cm.Created_At) as last_message_time
                FROM chat_message cm
                INNER JOIN chat_conversation cc ON cm.Chat_UUID = cc.Chat_UUID
                WHERE cc.Chat_UUID = %s OR CAST(cc.Chat_ID AS CHAR) = %s
                GROUP BY cc.Chat_ID, cc.Chat_UUID
            """
            result = self.db.execute_one(query, (chat_id_normalized, chat_id_normalized))
            if result:
                logger.info(f"查询对话统计信息成功: Chat_ID={chat_id}")
            return result
        except Exception as e:
            logger.error(f"查询对话统计信息失败: {e}")
            return None

    def search_messages(
        self,
        chat_id: Union[str, int],
        keyword: str,
        message_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        在对话中搜索包含关键词的消息

        Args:
            chat_id: 对话ID（支持Chat_ID或Chat_UUID）
            keyword: 搜索关键词
            message_type: 消息类型过滤('user'/'ai'，None表示所有)

        Returns:
            匹配的消息列表
        """
        try:
            chat_id_normalized = normalize_id(chat_id)
            base_query = """
                SELECT cm.* FROM chat_message cm
                INNER JOIN chat_conversation cc ON cm.Chat_UUID = cc.Chat_UUID
                WHERE (cc.Chat_UUID = %s OR CAST(cc.Chat_ID AS CHAR) = %s)
                AND cm.Message_Content LIKE %s
            """
            params = [chat_id_normalized, chat_id_normalized, f'%{keyword}%']

            if message_type:
                base_query += " AND cm.Message_Type = %s"
                params.append(message_type)

            base_query += " ORDER BY cm.Message_Order ASC"

            results = self.db.execute_query(base_query, tuple(params))

            # 将JSON字符串的context转回字典
            for msg in results:
                if msg.get('Context'):
                    try:
                        msg['Context'] = json.loads(msg['Context'])
                    except json.JSONDecodeError:
                        msg['Context'] = None

            logger.info(f"搜索到 {len(results)} 条消息: Chat_ID={chat_id}, Keyword={keyword}")
            return results
        except Exception as e:
            logger.error(f"搜索消息失败: {e}")
            return []
