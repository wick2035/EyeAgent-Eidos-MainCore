"""
意图识别模块 - 根据对话内容判断使用哪个Agent
"""
from typing import Dict, Any
from utils.llm_config import get_llm


class IntentDetector:
    """意图识别器"""
    
    # Agent1相关关键词（健康咨询、症状、预约）
    HEALTH_KEYWORDS = [
        '症状', '不舒服', '疼', '痛', '难受', '不适', '异常', 
        '眼睛', '视力', '模糊', '红', '肿', '痒', '干涩', '流泪',
        '预约', '挂号', '看病', '就诊', '医生', '门诊',
        '咨询', '问诊', '检查', '治疗', '药物',
        '头晕', '头痛', '恶心', '呕吐', '发热', '发烧'
    ]
    
    # Agent2相关关键词（报告、历史、分析、对比）
    REPORT_KEYWORDS = [
        '报告', '病例', '历史', '记录', '档案',
        '分析', '对比', '比较', '趋势', '变化',
        '上次', '之前', '以前', '过去', '历次',
        '查看', '查询', '查找', '检索',
        '生成', '导出', '下载'
    ]

    # Agent3相关关键词（提醒、复诊、用药）
    REMINDER_KEYWORDS = [
        '提醒', '复诊', '随访', '复查', '定期',
        '用药', '吃药', '服药', '按时', '定时',
        '提示', '通知', '闹钟', '备忘',
        '到期', '过期', '应该', '该去',
        '配置', '设置', '偏好', '免打扰'
    ]
    
    def __init__(self):
        self.llm = get_llm()
    
    def detect_intent(
        self, 
        message: str, 
        role: str = 'patient',
        conversation_history: list = None
    ) -> Dict[str, Any]:
        """
        检测用户意图
        
        Args:
            message: 用户消息
            role: 用户角色（doctor/patient）
            conversation_history: 对话历史
            
        Returns:
            {
                'agent_type': 'health' 或 'report' 或 'reminder',
                'confidence': 置信度 (0-1),
                'reason': 判断原因
            }
        """
        # 1. 基于关键词的快速判断
        health_score = self._calculate_keyword_score(message, self.HEALTH_KEYWORDS)
        report_score = self._calculate_keyword_score(message, self.REPORT_KEYWORDS)
        reminder_score = self._calculate_keyword_score(message, self.REMINDER_KEYWORDS)
        
        # 2. 特殊规则判断
        
        # 规则1：如果是患者且明确提到生成报告，阻止
        if role == 'patient' and any(kw in message for kw in ['生成报告', '生成病例', '创建报告']):
            return {
                'agent_type': 'health',  # 回退到health agent处理拒绝
                'confidence': 1.0,
                'reason': '患者无权生成报告',
                'blocked': True
            }
        
        # 规则2：明确的提醒相关查询（优先级最高）
        reminder_triggers = ['查看提醒', '我的提醒', '提醒列表', '创建提醒', '添加提醒', '取消提醒', '完成提醒', '复诊提醒', '用药提醒']
        if any(trigger in message for trigger in reminder_triggers):
            return {
                'agent_type': 'reminder',
                'confidence': 0.95,
                'reason': f'匹配提醒触发词: {message[:20]}...'
            }

        # 规则3：明确的报告相关查询
        report_triggers = ['查看报告', '历史报告', '历史记录', '病例报告', '分析病情', '对比']
        if any(trigger in message for trigger in report_triggers):
            return {
                'agent_type': 'report',
                'confidence': 0.9,
                'reason': f'匹配报告触发词: {message[:20]}...'
            }

        # 规则4：明确的健康咨询
        health_triggers = ['不舒服', '预约', '挂号', '症状', '疼', '痛']
        if any(trigger in message for trigger in health_triggers):
            return {
                'agent_type': 'health',
                'confidence': 0.9,
                'reason': f'匹配健康咨询触发词: {message[:20]}...'
            }
        
        # 3. 基于评分判断（三方比较）
        max_score = max(health_score, report_score, reminder_score)
        total_score = health_score + report_score + reminder_score + 0.1

        if max_score == reminder_score and reminder_score > 0:
            return {
                'agent_type': 'reminder',
                'confidence': min(reminder_score / total_score, 0.95),
                'reason': f'关键词分析: 提醒={reminder_score:.2f}, 报告={report_score:.2f}, 健康={health_score:.2f}'
            }
        elif max_score == report_score and report_score > health_score * 1.5:
            return {
                'agent_type': 'report',
                'confidence': min(report_score / total_score, 0.95),
                'reason': f'关键词分析: 报告={report_score:.2f}, 健康={health_score:.2f}, 提醒={reminder_score:.2f}'
            }
        elif max_score == health_score and health_score > report_score * 1.5:
            return {
                'agent_type': 'health',
                'confidence': min(health_score / total_score, 0.95),
                'reason': f'关键词分析: 健康={health_score:.2f}, 报告={report_score:.2f}, 提醒={reminder_score:.2f}'
            }
        
        # 4. 使用LLM进行更精确的判断（仅在关键词判断不明确时）
        llm_result = self._llm_detect(message, role, conversation_history)
        return llm_result
    
    def _calculate_keyword_score(self, message: str, keywords: list) -> float:
        """
        计算关键词匹配分数
        
        Args:
            message: 用户消息
            keywords: 关键词列表
            
        Returns:
            匹配分数
        """
        score = 0.0
        message_lower = message.lower()
        
        for keyword in keywords:
            if keyword.lower() in message_lower:
                # 完整词匹配得分更高
                if f' {keyword.lower()} ' in f' {message_lower} ':
                    score += 1.0
                else:
                    score += 0.5
        
        return score
    
    def _llm_detect(
        self, 
        message: str, 
        role: str,
        conversation_history: list = None
    ) -> Dict[str, Any]:
        """
        使用LLM进行意图检测
        
        Args:
            message: 用户消息
            role: 用户角色
            conversation_history: 对话历史
            
        Returns:
            意图检测结果
        """
        # 构建历史上下文
        history_text = ""
        if conversation_history:
            recent_history = conversation_history[-4:]  # 最近4轮对话
            for msg in recent_history:
                role_text = "用户" if msg.get("role") == "user" else "助手"
                history_text += f"{role_text}: {msg.get('content', '')}\n"
        
        prompt = f"""你是一个智能医疗系统的意图识别助手。请判断用户的消息应该由哪个Agent处理。

系统有三个Agent：
1. **健康咨询Agent**：处理健康咨询、症状评估、医生预约等
2. **报告分析Agent**：处理病例报告查看、历史分析、记录对比等
3. **提醒管理Agent**：处理复诊提醒、预约提醒、用药提醒的查看、创建和管理

用户角色：{role}（doctor=医生，patient=患者）
注意：患者不能生成新报告，只能查看和分析现有报告。

最近对话历史：
{history_text if history_text else "无"}

当前用户消息：{message}

请判断应该使用哪个Agent，并给出理由。

请以JSON格式回复（只输出JSON，不要其他文字）：
{{
    "agent_type": "health" 或 "report" 或 "reminder",
    "confidence": 0.0-1.0之间的置信度,
    "reason": "判断原因"
}}
"""
        
        try:
            response = self.llm.predict(prompt)
            
            # 尝试解析JSON
            import json
            # 提取JSON部分
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                result = json.loads(json_str)
                
                # 验证结果
                if result.get('agent_type') in ['health', 'report', 'reminder']:
                    return result
            
            # 如果解析失败，使用默认值
            print(f"[IntentDetector] LLM返回解析失败: {response}")
            
        except Exception as e:
            print(f"[IntentDetector] LLM意图检测失败: {e}")
        
        # 默认返回健康咨询Agent
        return {
            'agent_type': 'health',
            'confidence': 0.5,
            'reason': 'LLM判断失败，使用默认值'
        }
    
    def should_switch_agent(
        self,
        current_agent: str,
        detected_intent: Dict[str, Any],
        threshold: float = 0.7
    ) -> bool:
        """
        判断是否应该切换Agent
        
        Args:
            current_agent: 当前使用的agent
            detected_intent: 检测到的意图
            threshold: 置信度阈值
            
        Returns:
            是否应该切换
        """
        # 如果置信度低于阈值，不切换
        if detected_intent.get('confidence', 0) < threshold:
            return False
        
        # 如果检测到的agent与当前agent不同，且置信度足够高，则切换
        detected_agent = detected_intent.get('agent_type')
        if detected_agent and detected_agent != current_agent:
            return True
        
        return False


# 全局单例
_intent_detector = None


def get_intent_detector() -> IntentDetector:
    """获取意图识别器单例"""
    global _intent_detector
    if _intent_detector is None:
        _intent_detector = IntentDetector()
    return _intent_detector

