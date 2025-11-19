"""
意图识别模块 V2 - 使用混合路由器（零训练方案）
完全兼容旧版IntentDetector的接口
"""
from typing import Dict, Any, List
from utils.hybrid_intent_router import get_hybrid_router


class IntentDetectorV2:
    """
    意图识别器 V2（混合路由方案）

    升级点：
    1. 零训练 - 无需训练数据，开箱即用
    2. 独立API - 使用轻量级LLM（Qwen2.5-1.5B），不影响业务Agent
    3. 高性能 - 90%流量走规则（<1ms），10%走LLM（~100ms）
    4. 高准确率 - 规则+LLM融合，比单纯关键词更智能
    5. 可监控 - 提供性能统计和调试信息
    """

    def __init__(self):
        # 使用混合路由器
        self.router = get_hybrid_router()

    def detect_intent(
        self,
        message: str,
        role: str = 'patient',
        conversation_history: list = None,
        current_agent: str = None,
        current_stage: str = None
    ) -> Dict[str, Any]:
        """
        检测用户意图（兼容旧版接口）

        Args:
            message: 用户消息
            role: 用户角色（doctor/patient）
            conversation_history: 对话历史
            current_agent: 当前使用的agent类型
            current_stage: 当前agent的对话阶段

        Returns:
            {
                'agent_type': 'health' 或 'report' 或 'reminder',
                'confidence': 置信度 (0-1),
                'reason': 判断原因,
                'blocked': 是否被阻止（可选）
            }
        """
        # 权限检查：患者尝试生成报告
        if role == 'patient' and any(kw in message for kw in ['生成报告', '生成病例', '创建报告']):
            return {
                'agent_type': 'health',
                'confidence': 1.0,
                'reason': '患者无权生成报告',
                'blocked': True
            }

        # 调用混合路由器
        result = self.router.route(
            message=message,
            role=role,
            conversation_history=conversation_history,
            current_agent=current_agent,
            current_stage=current_stage
        )

        # 返回结果（移除debug_info，避免日志过长）
        return {
            'agent_type': result['agent_type'],
            'confidence': result['confidence'],
            'reason': result['reason']
        }

    def should_switch_agent(
        self,
        current_agent: str,
        detected_intent: Dict[str, Any],
        threshold: float = 0.7
    ) -> bool:
        """
        判断是否应该切换Agent（兼容旧版接口）

        Args:
            current_agent: 当前使用的agent
            detected_intent: 检测到的意图
            threshold: 置信度阈值

        Returns:
            是否应该切换
        """
        return self.router.should_switch_agent(
            current_agent=current_agent,
            detected_intent=detected_intent,
            threshold=threshold
        )

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计（新增功能）

        Returns:
            {
                'total_requests': int,
                'rule_hit_rate': str,  # 例如 "92.3%"
                'llm_call_rate': str,  # 例如 "7.7%"
                'fusion_rate': str,    # 例如 "3.2%"
            }
        """
        return self.router.get_stats()

    def reset_stats(self):
        """重置性能统计"""
        self.router.reset_stats()

    def configure(self, **kwargs):
        """
        动态配置路由器（新增功能）

        可配置参数：
        - rule_high_confidence_threshold: float (默认0.85)
        - rule_medium_confidence_threshold: float (默认0.6)
        - llm_enabled: bool (默认True)
        - fusion_mode: str ('weighted' 或 'override')
        """
        self.router.configure(**kwargs)


# 全局单例
_intent_detector_v2 = None


def get_intent_detector() -> IntentDetectorV2:
    """获取意图识别器单例（V2版本）"""
    global _intent_detector_v2
    if _intent_detector_v2 is None:
        _intent_detector_v2 = IntentDetectorV2()
    return _intent_detector_v2
