"""
混合路由器测试脚本
测试零训练方案的准确性和性能
"""
from utils.intent_detector_v2 import get_intent_detector
import time


def test_case(detector, message, expected_agent, role='patient', description=''):
    """测试单个case"""
    print(f"\n{'='*60}")
    print(f"测试: {description}")
    print(f"消息: {message}")
    print(f"期望: {expected_agent}")

    start_time = time.time()
    result = detector.detect_intent(message, role=role)
    elapsed = (time.time() - start_time) * 1000  # ms

    print(f"结果: {result['agent_type']}")
    print(f"置信度: {result['confidence']:.2f}")
    print(f"原因: {result['reason']}")
    print(f"耗时: {elapsed:.1f}ms")

    # 判断是否正确
    is_correct = result['agent_type'] == expected_agent
    status = "[OK] 正确" if is_correct else "[FAIL] 错误"
    print(f"状态: {status}")

    return is_correct, elapsed


def main():
    print("="*60)
    print("混合意图路由器测试")
    print("="*60)

    detector = get_intent_detector()

    # 测试用例集合
    test_cases = [
        # ===== Health Agent 测试 =====
        {
            'message': '我眼睛最近有点模糊',
            'expected': 'health',
            'role': 'patient',
            'description': '症状描述'
        },
        {
            'message': '我要预约明天的门诊',
            'expected': 'health',
            'role': 'patient',
            'description': '预约意图'
        },
        {
            'message': '头晕头痛，想看看医生',
            'expected': 'health',
            'role': 'patient',
            'description': '症状+预约'
        },
        {
            'message': '眼睛红肿该怎么治疗',
            'expected': 'health',
            'role': 'patient',
            'description': '症状+咨询'
        },

        # ===== Report Agent 测试 =====
        {
            'message': '帮我查看一下历史报告',
            'expected': 'report',
            'role': 'patient',
            'description': '查看报告'
        },
        {
            'message': '我想看看之前的病例记录',
            'expected': 'report',
            'role': 'patient',
            'description': '查看病例'
        },
        {
            'message': '对比一下这次和上次的检查结果',
            'expected': 'report',
            'role': 'patient',
            'description': '病情对比'
        },
        {
            'message': '生成一份医疗报告',
            'expected': 'report',
            'role': 'doctor',
            'description': '医生生成报告'
        },
        {
            'message': '生成报告',
            'expected': 'health',  # 患者会被阻止
            'role': 'patient',
            'description': '患者生成报告（应被阻止）'
        },

        # ===== Reminder Agent 测试 =====
        {
            'message': '查看我的复诊提醒',
            'expected': 'reminder',
            'role': 'patient',
            'description': '查看提醒'
        },
        {
            'message': '帮我设置一个用药提醒',
            'expected': 'reminder',
            'role': 'patient',
            'description': '创建提醒'
        },
        {
            'message': '我的提醒列表',
            'expected': 'reminder',
            'role': 'patient',
            'description': '提醒列表'
        },
        {
            'message': '取消之前的复诊提醒',
            'expected': 'reminder',
            'role': 'patient',
            'description': '取消提醒'
        },

        # ===== 模糊/复杂case测试 =====
        {
            'message': '我想看看之前眼睛的情况',
            'expected': 'report',  # 应该路由到report（查看历史）
            'role': 'patient',
            'description': '模糊意图-历史查询'
        },
        {
            'message': '上次检查说要复查，怎么约',
            'expected': 'health',  # 应该路由到health（预约）
            'role': 'patient',
            'description': '模糊意图-预约复查'
        },
        {
            'message': '我需要定期复诊，能提醒我吗',
            'expected': 'reminder',  # 应该路由到reminder
            'role': 'patient',
            'description': '模糊意图-设置提醒'
        },
        {
            'message': '帮我看看病历上的处方',
            'expected': 'report',  # 应该路由到report（查看处方）
            'role': 'patient',
            'description': '模糊意图-查看处方'
        },
    ]

    # 执行测试
    total = len(test_cases)
    correct = 0
    total_time = 0

    for case in test_cases:
        is_correct, elapsed = test_case(
            detector,
            case['message'],
            case['expected'],
            case['role'],
            case['description']
        )

        if is_correct:
            correct += 1
        total_time += elapsed

    # 统计结果
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")
    print(f"总测试数: {total}")
    print(f"正确数: {correct}")
    print(f"错误数: {total - correct}")
    print(f"准确率: {correct/total*100:.1f}%")
    print(f"平均耗时: {total_time/total:.1f}ms")
    print(f"总耗时: {total_time:.1f}ms")

    # 性能统计
    print(f"\n{'='*60}")
    print("性能统计")
    print(f"{'='*60}")
    stats = detector.get_performance_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")

    print(f"\n{'='*60}")
    print("测试完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
