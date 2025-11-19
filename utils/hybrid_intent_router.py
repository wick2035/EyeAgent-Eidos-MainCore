"""
混合意图路由器 - 零训练的高性能方案
结合规则引擎 + 轻量级LLM，独立API配置
"""
from typing import Dict, Any, List
from utils.enhanced_rules import EnhancedRuleEngine
from utils.llm_router import LightweightLLMRouter


class HybridIntentRouter:
    """
    混合意图路由器（零训练方案）

    路由策略：
    1. 规则引擎（90%流量，<1ms延迟）- 快速精确匹配
    2. 轻量级LLM（10%流量，~100ms延迟）- 处理复杂语义
    3. 结果融合 - 综合判断，提高准确率
    """

    def __init__(self):
        # 第一层：增强型规则引擎
        self.rule_engine = EnhancedRuleEngine()

        # 第二层：轻量级LLM路由器（独立API）
        self.llm_router = LightweightLLMRouter()

        # 配置参数
        self.config = {
            'rule_high_confidence_threshold': 0.85,  # 规则高置信度阈值
            'rule_medium_confidence_threshold': 0.6,  # 规则中等置信度阈值
            'llm_enabled': True,  # 是否启用LLM路由
            'fusion_mode': 'weighted',  # 融合模式: weighted / override
        }

        # 性能统计
        self.stats = {
            'total_requests': 0,
            'rule_direct_hits': 0,  # 规则直接命中
            'llm_calls': 0,  # LLM调用次数
            'fusion_decisions': 0,  # 融合决策次数
        }

    def route(
        self,
        message: str,
        role: str = 'patient',
        conversation_history: List[Dict] = None,
        current_agent: str = None,
        current_stage: str = None
    ) -> Dict[str, Any]:
        """
        智能路由决策

        Args:
            message: 用户消息
            role: 用户角色（doctor/patient）
            conversation_history: 对话历史
            current_agent: 当前agent类型
            current_stage: 当前对话阶段

        Returns:
            {
                'agent_type': str,  # health/report/reminder
                'confidence': float,  # 0-1
                'reason': str,  # 判断原因
                'strategy': str,  # 使用的策略
                'debug_info': dict  # 调试信息（可选）
            }
        """
        self.stats['total_requests'] += 1

        # 构建上下文
        context = {
            'role': role,
            'conversation_history': conversation_history or [],
            'current_agent': current_agent,
            'current_stage': current_stage,
        }

        # ===== 第一层：规则引擎快速匹配 =====
        rule_result = self.rule_engine.match(message, context)

        # 调试信息
        debug_info = {
            'rule_result': rule_result,
            'llm_result': None,
            'fusion_applied': False
        }

        # 情况1: 规则高置信度 -> 直接返回（90%流量）
        if rule_result['confidence'] >= self.config['rule_high_confidence_threshold']:
            self.stats['rule_direct_hits'] += 1
            return {
                **rule_result,
                'debug_info': debug_info
            }

        # 情况2: 规则低置信度 -> 使用LLM路由（10%流量）
        if not self.config['llm_enabled']:
            # LLM未启用，直接返回规则结果
            return {
                **rule_result,
                'debug_info': debug_info
            }

        # ===== 第二层：轻量级LLM路由 =====
        try:
            self.stats['llm_calls'] += 1
            llm_result = self.llm_router.route(message, context)
            debug_info['llm_result'] = llm_result

            # 情况3: 规则中等置信度 -> 融合决策
            if rule_result['confidence'] >= self.config['rule_medium_confidence_threshold']:
                self.stats['fusion_decisions'] += 1
                final_result = self._fuse_results(rule_result, llm_result)
                debug_info['fusion_applied'] = True
                return {
                    **final_result,
                    'debug_info': debug_info
                }

            # 情况4: 规则很低置信度 -> LLM结果为准
            return {
                **llm_result,
                'debug_info': debug_info
            }

        except Exception as e:
            # LLM失败降级
            print(f"[HybridRouter] LLM路由失败，降级到规则: {e}")
            return {
                **rule_result,
                'reason': f'LLM失败降级: {rule_result["reason"]}',
                'debug_info': debug_info
            }

    def _fuse_results(
        self,
        rule_result: Dict[str, Any],
        llm_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        融合规则和LLM结果

        策略：
        - 如果两者一致 -> 提升置信度
        - 如果不一致 -> 根据权重加权
        """
        rule_agent = rule_result['agent_type']
        llm_agent = llm_result['agent_type']

        # 一致性检查
        if rule_agent == llm_agent:
            # 结果一致，取较高置信度并加成
            max_confidence = max(rule_result['confidence'], llm_result['confidence'])
            boosted_confidence = min(max_confidence * 1.1, 0.98)

            return {
                'agent_type': rule_agent,
                'confidence': boosted_confidence,
                'reason': f'规则+LLM一致: {rule_agent}',
                'strategy': 'fusion_consistent'
            }

        # 结果不一致，加权融合
        if self.config['fusion_mode'] == 'weighted':
            # 根据置信度加权选择
            rule_weight = rule_result['confidence']
            llm_weight = llm_result['confidence']

            if rule_weight > llm_weight * 1.2:
                # 规则更可信
                return {
                    'agent_type': rule_agent,
                    'confidence': rule_result['confidence'] * 0.9,
                    'reason': f'规则优先: {rule_result["reason"]}',
                    'strategy': 'fusion_rule_priority'
                }
            elif llm_weight > rule_weight * 1.2:
                # LLM更可信
                return {
                    'agent_type': llm_agent,
                    'confidence': llm_result['confidence'] * 0.9,
                    'reason': f'LLM优先: {llm_result["reason"]}',
                    'strategy': 'fusion_llm_priority'
                }
            else:
                # 不确定，选择规则结果但降低置信度
                return {
                    'agent_type': rule_agent,
                    'confidence': min(rule_result['confidence'], llm_result['confidence']) * 0.8,
                    'reason': f'规则LLM冲突，保守选择: {rule_agent}',
                    'strategy': 'fusion_conflict'
                }

        else:  # override mode
            # LLM覆盖规则
            return {
                **llm_result,
                'strategy': 'fusion_llm_override'
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
            current_agent: 当前agent类型
            detected_intent: 检测到的意图
            threshold: 切换置信度阈值

        Returns:
            是否应该切换
        """
        # 置信度不足，不切换
        if detected_intent.get('confidence', 0) < threshold:
            return False

        # 检测到不同的agent且置信度足够
        detected_agent = detected_intent.get('agent_type')
        if detected_agent and detected_agent != current_agent:
            return True

        return False

    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        total = self.stats['total_requests']
        if total == 0:
            return self.stats

        return {
            **self.stats,
            'rule_hit_rate': f"{self.stats['rule_direct_hits'] / total * 100:.1f}%",
            'llm_call_rate': f"{self.stats['llm_calls'] / total * 100:.1f}%",
            'fusion_rate': f"{self.stats['fusion_decisions'] / total * 100:.1f}%",
        }

    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_requests': 0,
            'rule_direct_hits': 0,
            'llm_calls': 0,
            'fusion_decisions': 0,
        }

    def configure(self, **kwargs):
        """动态配置路由器参数"""
        self.config.update(kwargs)
        print(f"[HybridRouter] 配置已更新: {self.config}")


# 全局单例
_hybrid_router = None


def get_hybrid_router() -> HybridIntentRouter:
    """获取混合路由器单例"""
    global _hybrid_router
    if _hybrid_router is None:
        _hybrid_router = HybridIntentRouter()
    return _hybrid_router
