"""
增强型规则引擎 - 零训练的高性能意图识别
"""
import re
from typing import Dict, Any, List, Tuple


class EnhancedRuleEngine:
    """增强型规则引擎 - 第一层快速匹配"""

    def __init__(self):
        # 精确模式匹配（优先级最高）
        self.exact_patterns = {
            'health': [
                # 症状相关
                r'(眼睛|视力|眼|眼部).*(不舒服|模糊|疼|痛|红|肿|痒|干|流泪|异常)',
                r'(头|头部).*(晕|痛|疼)',
                r'(恶心|呕吐|发热|发烧)',

                # 预约相关（强意图）
                r'(我要|我想|帮我|给我).*(约|预约|挂号)',
                r'(约|预约).*(医生|门诊|专家|眼科)',
                r'^(预约|挂号|看病|就诊)',

                # 咨询相关
                r'(什么|怎么|如何).*(治疗|检查|处理)',
                r'(需要|应该).*(看|检查|治疗)',
            ],

            'report': [
                # 报告查询（强意图）
                r'(查看|看|查|找).*(报告|病例|记录|档案)',
                r'(我的|历史|过往).*(报告|病例|记录)',
                r'(生成|创建|导出).*(报告|病例)',

                # 历史分析（注意：排除预约意图）
                r'(对比|比较|分析).*(病情|历史|之前)',
                r'(上次|之前|以前|过去).*(检查|就诊|看病)(?!.*[约预挂])',  # 负向前瞻：排除预约

                # 处方相关
                r'(查看|看|查).*(处方|药方)',
                r'(生成|开).*(处方|药)',
            ],

            'reminder': [
                # 提醒管理（强意图）
                r'(查看|看|管理).*(提醒|待办)',
                r'(我的|所有).*(提醒|待办)',
                r'(创建|添加|设置|新增).*(提醒|闹钟)',
                r'(取消|删除|完成).*(提醒)',

                # 复诊/用药提醒
                r'(复诊|复查|随访).*(提醒|通知)',
                r'(用药|吃药|服药).*(提醒|时间)',
                r'(提醒.*)(复诊|用药|吃药)',
            ]
        }

        # 关键词权重表（用于模糊匹配）
        self.keyword_weights = {
            'health': {
                # 症状类（高权重）
                '症状': 2.0, '不舒服': 2.0, '疼': 1.5, '痛': 1.5, '难受': 1.5,
                '眼睛': 1.5, '视力': 1.5, '模糊': 1.5, '红': 1.0, '肿': 1.0, '痒': 1.0,
                '头晕': 2.0, '头痛': 2.0, '恶心': 1.5, '呕吐': 1.5,

                # 预约类（高权重）
                '预约': 2.5, '挂号': 2.5, '约医生': 3.0, '看病': 1.5, '就诊': 1.5,
                '门诊': 1.0, '专家': 1.0, '医生': 1.0,

                # 咨询类
                '咨询': 1.0, '问诊': 1.5, '治疗': 1.0, '检查': 1.0,
            },

            'report': {
                # 报告类（高权重）
                '报告': 2.5, '病例': 2.0, '记录': 1.5, '档案': 1.5,
                '查看报告': 3.5, '我的报告': 3.5, '历史报告': 3.5,

                # 分析类
                '分析': 2.0, '对比': 2.0, '比较': 2.0, '趋势': 1.5, '变化': 1.5,

                # 历史相关
                '历史': 1.5, '上次': 1.5, '之前': 1.5, '以前': 1.5, '过去': 1.5,
                '历次': 2.0, '过往': 1.5,

                # 生成类
                '生成报告': 3.0, '导出': 2.0, '下载': 1.5,

                # 处方相关
                '处方': 2.0, '药方': 2.0, '开药': 1.5,
            },

            'reminder': {
                # 提醒管理（高权重）
                '提醒': 3.0, '待办': 2.5, '任务': 1.5,
                '查看提醒': 4.0, '我的提醒': 4.0, '提醒列表': 4.0,

                # 操作类
                '创建提醒': 3.5, '添加提醒': 3.5, '设置提醒': 3.5,
                '取消提醒': 3.5, '删除提醒': 3.5, '完成提醒': 3.5,

                # 类型相关
                '复诊': 2.0, '复查': 2.0, '随访': 2.0,
                '用药': 2.0, '吃药': 2.0, '服药': 2.0,
                '复诊提醒': 3.0, '用药提醒': 3.0,

                # 时间相关
                '定期': 1.5, '按时': 1.5, '定时': 1.5, '到期': 1.5,
            }
        }

        # 排除关键词（出现这些词时降低置信度）
        self.exclusion_keywords = {
            'health': ['报告', '历史', '记录', '之前', '对比', '提醒'],
            'report': ['预约', '挂号', '提醒', '创建提醒'],
            'reminder': ['症状', '不舒服', '疼', '痛', '预约医生', '报告分析']
        }

    def match(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        规则匹配（第一层快速路由）

        Returns:
            {
                'agent_type': str,
                'confidence': float (0-1),
                'reason': str,
                'matched_pattern': str (可选)
            }
        """
        context = context or {}
        current_agent = context.get('current_agent')
        current_stage = context.get('current_stage')

        # 1. 检查对话状态保持（最高优先级）
        if current_agent and current_stage:
            critical_stages = [
                'symptom_assessment', 'appointment_inquiry',
                'patient_info_collection', 'ophthalmology_triage',
                'medical_history', 'appointment_booking'
            ]

            if current_stage in critical_stages:
                # 检查是否明确要求切换
                if not self._has_explicit_switch_intent(message):
                    return {
                        'agent_type': current_agent,
                        'confidence': 0.95,
                        'reason': f'对话状态保持: {current_stage}',
                        'strategy': 'state_preservation'
                    }

        # 2. 精确模式匹配（高置信度）
        pattern_result = self._pattern_match(message)
        if pattern_result['confidence'] >= 0.9:
            return pattern_result

        # 3. 关键词加权匹配（中等置信度）
        keyword_result = self._keyword_weighted_match(message, context)
        if keyword_result['confidence'] >= 0.7:
            return keyword_result

        # 4. 返回低置信度结果（需要LLM兜底）
        return {
            'agent_type': keyword_result.get('agent_type', 'health'),
            'confidence': keyword_result.get('confidence', 0.3),
            'reason': '规则置信度低，建议使用LLM判断',
            'strategy': 'low_confidence'
        }

    def _pattern_match(self, message: str) -> Dict[str, Any]:
        """精确模式匹配"""
        scores = {'health': 0, 'report': 0, 'reminder': 0}
        matched_patterns = {'health': [], 'report': [], 'reminder': []}

        for agent_type, patterns in self.exact_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    scores[agent_type] += 1
                    matched_patterns[agent_type].append(pattern)

        # 找到最高分
        if max(scores.values()) == 0:
            return {'agent_type': 'health', 'confidence': 0.0, 'reason': '无模式匹配'}

        max_agent = max(scores, key=scores.get)
        max_score = scores[max_agent]

        # 计算置信度（有模式匹配即高置信度）
        confidence = min(0.9 + max_score * 0.02, 0.98)

        return {
            'agent_type': max_agent,
            'confidence': confidence,
            'reason': f'模式匹配: {matched_patterns[max_agent][0][:30]}...',
            'strategy': 'pattern_match',
            'matched_patterns': matched_patterns[max_agent]
        }

    def _keyword_weighted_match(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """关键词加权匹配"""
        scores = {'health': 0.0, 'report': 0.0, 'reminder': 0.0}
        matched_keywords = {'health': [], 'report': [], 'reminder': []}

        # 计算每个agent的加权分数
        for agent_type, keywords in self.keyword_weights.items():
            for keyword, weight in keywords.items():
                if keyword in message:
                    scores[agent_type] += weight
                    matched_keywords[agent_type].append(keyword)

            # 应用排除关键词惩罚
            for exclude_kw in self.exclusion_keywords[agent_type]:
                if exclude_kw in message:
                    scores[agent_type] -= 1.0

        # 找到最高分
        if max(scores.values()) <= 0:
            return {'agent_type': 'health', 'confidence': 0.0, 'reason': '无关键词匹配'}

        max_agent = max(scores, key=scores.get)
        max_score = scores[max_agent]
        total_score = sum(scores.values()) + 0.1

        # 计算置信度（归一化）
        confidence = min(max_score / total_score, 0.95)

        # 如果最高分与第二高分差距不大，降低置信度
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[0] < sorted_scores[1] * 1.5:
            confidence *= 0.7

        return {
            'agent_type': max_agent,
            'confidence': confidence,
            'reason': f'关键词匹配: {", ".join(matched_keywords[max_agent][:3])}',
            'strategy': 'keyword_weighted',
            'scores': scores,
            'matched_keywords': matched_keywords[max_agent]
        }

    def _has_explicit_switch_intent(self, message: str) -> bool:
        """检查是否有明确的切换意图"""
        switch_patterns = [
            r'查看.*报告', r'看.*报告', r'我要.*报告',
            r'查看.*提醒', r'看.*提醒', r'我的.*提醒',
            r'创建.*提醒', r'添加.*提醒'
        ]

        for pattern in switch_patterns:
            if re.search(pattern, message):
                return True
        return False
