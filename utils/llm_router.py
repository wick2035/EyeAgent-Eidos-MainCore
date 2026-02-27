"""
轻量级LLM路由器 - 独立API配置，零训练方案
"""
import json
from typing import Dict, Any, List
from utils.router_config import get_router_llm


class LightweightLLMRouter:
    """轻量级LLM路由器（第二层智能路由）"""

    def __init__(self):
        # 使用独立的轻量级LLM（不影响业务Agent）
        self.llm = get_router_llm()

        # 典型意图模板（零训练，用于prompt engineering）
        self.intent_templates = {
            'health': [
                "我眼睛有点模糊，看东西不清楚",
                "最近头晕，想预约个医生看看",
                "想挂个眼科的号",
                "眼睛红肿，该怎么治疗",
                "需要做什么检查吗",
            ],
            'report': [
                "帮我查看一下历史报告",
                "我想看看之前的病例记录",
                "对比一下这次和上次的检查结果",
                "生成一份医疗报告",
                "查看我的处方记录",
            ],
            'reminder': [
                "查看我的复诊提醒",
                "帮我设置一个用药提醒",
                "我的提醒列表有哪些",
                "取消之前的复诊提醒",
                "创建一个定期检查的提醒",
            ],
            'compliance': [
                "帮我审查一下这个处方是否合规",
                "检查这个诊断是否符合临床指南",
                "审核一下患者病历的规范性",
                "这个处方的用药剂量是否合理",
                "对这次诊疗做一个合规性审查",
            ],
            'recommendation': [
                "推荐一些治疗干眼症的药品",
                "我想买点眼药水",
                "根据这个诊断推荐合适的药物",
                "有什么适合近视防控的产品",
                "帮我给患者开一些药",
            ]
        }

    def route(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        使用轻量级LLM进行路由判断（仅处理规则低置信度case）

        Args:
            message: 用户消息
            context: 上下文信息（包括对话历史、当前agent等）

        Returns:
            {
                'agent_type': str,
                'confidence': float,
                'reason': str,
                'strategy': str
            }
        """
        context = context or {}

        # 构建上下文信息
        history_text = self._build_history_context(context.get('conversation_history', []))
        role = context.get('role', 'patient')

        # 构建精简的prompt（专为1.5B模型优化）
        prompt = self._build_routing_prompt(message, history_text, role)

        try:
            # 调用轻量级LLM（独立API）
            response = self.llm.invoke(prompt).content

            # 解析JSON结果
            result = self._parse_llm_response(response)

            # 添加策略标记
            result['strategy'] = 'llm_routing'

            return result

        except Exception as e:
            print(f"[LLMRouter] LLM路由失败: {e}")
            # 降级到默认值
            return {
                'agent_type': 'health',
                'confidence': 0.5,
                'reason': f'LLM路由失败: {str(e)}',
                'strategy': 'llm_fallback'
            }

    def _build_routing_prompt(self, message: str, history: str, role: str) -> str:
        """构建路由prompt（为1.5B小模型优化）"""

        # 构建示例（few-shot learning，零训练）
        examples = []
        for agent_type, templates in self.intent_templates.items():
            examples.append(f"## {agent_type}示例:")
            for i, template in enumerate(templates[:2], 1):  # 每个只取2个示例
                examples.append(f"{i}. {template}")

        examples_text = "\n".join(examples)

        prompt = f"""你是医疗系统智能路由器。根据用户消息判断应使用哪个Agent。

**系统Agent:**
1. health - 健康咨询、症状评估、预约挂号
2. report - 查看报告、病史分析、处方记录
3. reminder - 复诊提醒、用药提醒管理
4. compliance - 合规性审查（仅医生可用）：处方审查、诊断审查、病历规范审查
5. recommendation - 医药产品推荐：药品推荐、购药咨询、处方药/非处方药/医疗器械推荐

**意图示例:**
{examples_text}

**用户信息:**
角色: {role}
{history if history else '(首次对话)'}

**当前消息:** {message}

**要求:**
1. 只输出JSON，格式: {{"agent":"health/report/reminder/compliance/recommendation","confidence":0.0-1.0,"reason":"原因"}}
2. confidence范围: 0.0-1.0
3. 不确定时选health，confidence设为0.5-0.7

输出:"""

        # 添加历史前缀
        if history:
            prompt = prompt.replace(history, f'最近对话:\n{history}')

        return prompt

    def _build_history_context(self, history: List[Dict]) -> str:
        """构建对话历史上下文（最近3轮）"""
        if not history:
            return ""

        recent = history[-6:]  # 最近3轮对话（6条消息）
        context_lines = []

        for msg in recent:
            role_text = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")[:50]  # 截断长消息
            context_lines.append(f"{role_text}: {content}")

        return "\n".join(context_lines)

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM返回的JSON"""
        try:
            # 提取JSON部分
            start = response.find('{')
            end = response.rfind('}') + 1

            if start == -1 or end <= start:
                raise ValueError("未找到JSON格式")

            json_str = response[start:end]
            result = json.loads(json_str)

            # 验证必要字段
            agent_type = result.get('agent', result.get('agent_type', 'health'))
            if agent_type not in ['health', 'report', 'reminder', 'compliance', 'recommendation']:
                agent_type = 'health'

            confidence = float(result.get('confidence', 0.6))
            confidence = max(0.0, min(1.0, confidence))  # 限制在0-1范围

            reason = result.get('reason', 'LLM判断')

            return {
                'agent_type': agent_type,
                'confidence': confidence,
                'reason': reason
            }

        except Exception as e:
            print(f"[LLMRouter] JSON解析失败: {response}, 错误: {e}")
            # 尝试关键词兜底
            return self._fallback_parse(response)

    def _fallback_parse(self, response: str) -> Dict[str, Any]:
        """兜底解析（从文本中提取agent类型）"""
        response_lower = response.lower()

        # 简单关键词检测
        if 'recommendation' in response_lower or '推荐' in response or '买药' in response or '购药' in response:
            return {'agent_type': 'recommendation', 'confidence': 0.6, 'reason': '文本兜底'}
        elif 'compliance' in response_lower or '合规' in response or '审查' in response:
            return {'agent_type': 'compliance', 'confidence': 0.6, 'reason': '文本兜底'}
        elif 'reminder' in response_lower or '提醒' in response:
            return {'agent_type': 'reminder', 'confidence': 0.6, 'reason': '文本兜底'}
        elif 'report' in response_lower or '报告' in response:
            return {'agent_type': 'report', 'confidence': 0.6, 'reason': '文本兜底'}
        else:
            return {'agent_type': 'health', 'confidence': 0.5, 'reason': '默认值'}
