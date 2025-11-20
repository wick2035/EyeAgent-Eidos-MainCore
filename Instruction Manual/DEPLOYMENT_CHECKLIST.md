# 🚀 混合路由器部署检查清单

## 部署前检查

### ✅ 环境准备

- [ ] Python 3.8+ 已安装
- [ ] 所有依赖已安装 (`pip install -r requirements.txt`)
- [ ] `.env` 文件已配置，包含：
  ```bash
  SILICONFLOW_API_KEY=your_key_here
  SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
  MODEL_NAME=Qwen/Qwen2.5-32B-Instruct
  ```
- [ ] API密钥有效且有足够额度

### ✅ 文件检查

确认以下文件存在：

- [ ] `utils/router_config.py` - 路由器配置
- [ ] `utils/llm_config.py` - 业务LLM配置（已更新为32B）
- [ ] `utils/enhanced_rules.py` - 增强规则引擎
- [ ] `utils/llm_router.py` - LLM路由器
- [ ] `utils/hybrid_intent_router.py` - 混合路由器主逻辑
- [ ] `utils/intent_detector_v2.py` - V2接口
- [ ] `test_hybrid_router.py` - 测试脚本

### ✅ 功能测试

```bash
# 运行完整测试
python test_hybrid_router.py
```

**验证点**:
- [ ] 所有测试通过（17/17）
- [ ] 准确率 ≥ 95%
- [ ] 平均延迟 < 200ms
- [ ] 无异常或错误

**预期输出**:
```
准确率: 100.0%
平均耗时: 176.8ms
rule_hit_rate: 87.5%
llm_call_rate: 12.5%
```

---

## 部署步骤

### 步骤1: 备份旧版

```bash
# 备份当前的intent_detector（可选）
cp utils/intent_detector.py utils/intent_detector_backup.py
```

### 步骤2: 切换到新版

编辑 `main.py`:

```python
# 找到这一行
from utils.intent_detector import get_intent_detector

# 替换为
from utils.intent_detector_v2 import get_intent_detector
```

### 步骤3: 重启服务

```bash
# 停止旧服务
# Ctrl+C 或 kill -9 <pid>

# 启动新服务
python main.py
```

### 步骤4: 验证运行

- [ ] 服务成功启动
- [ ] 无启动错误
- [ ] 日志中显示路由器初始化成功

---

## 部署后验证

### ✅ 功能验证

**测试Case 1: 症状咨询**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我眼睛最近有点模糊",
    "phone_number": "13800000000",
    "role": "patient"
  }'
```

**期望**: 路由到 `health` agent

---

**测试Case 2: 查看报告**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "帮我查看一下历史报告",
    "phone_number": "13800000000",
    "role": "patient"
  }'
```

**期望**: 路由到 `report` agent

---

**测试Case 3: 提醒管理**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "查看我的复诊提醒",
    "phone_number": "13800000000",
    "role": "patient"
  }'
```

**期望**: 路由到 `reminder` agent

### ✅ 性能监控

在代码中添加监控（可选）:

```python
# 在main.py中添加
from utils.intent_detector_v2 import get_intent_detector

@app.get("/api/stats")
def get_router_stats():
    """获取路由器性能统计"""
    detector = get_intent_detector()
    return detector.get_performance_stats()
```

访问 `http://localhost:8000/api/stats` 查看统计。

---

## 监控指标

### 🎯 关键指标

每天检查以下指标：

| 指标 | 健康范围 | 告警阈值 |
|------|----------|----------|
| **准确率** | 95-100% | <90% |
| **rule_hit_rate** | 80-95% | <70% 或 >98% |
| **llm_call_rate** | 5-20% | >30% |
| **平均延迟** | <100ms | >300ms |
| **错误率** | <1% | >5% |

### 📊 日志监控

关注以下日志：

```python
# 正常日志
[IntentDetector] Agent类型: health, 置信度: 0.92, 原因: 模式匹配
[HybridRouter] 规则直接命中

# 需要关注的日志
[LLMRouter] LLM路由失败: ...  # LLM调用失败
[HybridRouter] 融合决策: ...   # 规则和LLM结果不一致
```

### 🔔 告警设置

建议设置以下告警：

1. **准确率下降** - 当准确率 < 90% 时
2. **LLM调用过多** - 当 llm_call_rate > 30% 时
3. **延迟过高** - 当平均延迟 > 300ms 时
4. **错误率过高** - 当错误率 > 5% 时

---

## 故障排查

### 问题1: 路由不准确

**现象**: 用户消息路由到错误的agent

**排查步骤**:
1. 查看日志中的置信度和原因
2. 检查是否匹配了错误的规则
3. 运行测试脚本验证
4. 查看性能统计，确认LLM是否正常工作

**解决方案**:
```python
# 方案1: 调整规则阈值
detector.configure(rule_high_confidence_threshold=0.90)

# 方案2: 临时禁用规则，全部走LLM
detector.configure(llm_enabled=True, rule_high_confidence_threshold=1.0)

# 方案3: 添加更精确的规则
# 编辑 utils/enhanced_rules.py
```

---

### 问题2: LLM调用失败

**现象**: 日志显示 "LLM路由失败"

**排查步骤**:
1. 检查API密钥是否有效
2. 检查网络连接
3. 检查API额度是否充足
4. 确认模型名称正确（Qwen/Qwen2.5-14B-Instruct）

**解决方案**:
```bash
# 测试API连接
curl -X POST https://api.siliconflow.cn/v1/chat/completions \
  -H "Authorization: Bearer $SILICONFLOW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-14B-Instruct",
    "messages": [{"role": "user", "content": "test"}]
  }'
```

如果API失败，临时禁用LLM：
```python
detector.configure(llm_enabled=False)
```

---

### 问题3: 延迟过高

**现象**: 平均延迟 > 300ms

**排查步骤**:
1. 查看 `llm_call_rate` - 是否过高（>30%）
2. 检查网络延迟
3. 查看API服务状态

**解决方案**:
```python
# 优化规则，减少LLM调用
detector.configure(rule_high_confidence_threshold=0.80)

# 或降低LLM超时时间（在router_config.py中）
ROUTER_TIMEOUT = 2  # 从3秒降到2秒
```

---

### 问题4: 规则命中率过高（>95%）

**现象**: 几乎不调用LLM，可能遗漏复杂case

**排查步骤**:
1. 检查是否有边界case路由错误
2. 查看规则是否过于宽泛

**解决方案**:
```python
# 提高规则阈值，让更多case走LLM
detector.configure(rule_high_confidence_threshold=0.90)
```

---

## 回滚流程

### 快速回滚

如果新版出现严重问题，快速回滚：

**步骤1**: 修改 `main.py`
```python
from utils.intent_detector import get_intent_detector  # 恢复旧版
# from utils.intent_detector_v2 import get_intent_detector
```

**步骤2**: 重启服务
```bash
# 重启
python main.py
```

**步骤3**: 验证
```bash
# 测试旧版是否正常
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "测试", "phone_number": "13800000000"}'
```

---

## 优化建议

### 第1周: 观察期

- [ ] 每天查看性能统计
- [ ] 记录badcase（路由错误的case）
- [ ] 监控错误率和延迟
- [ ] 不做大改动

### 第2周: 微调期

- [ ] 根据badcase优化规则
- [ ] 调整置信度阈值
- [ ] 测试不同配置

### 第1个月: 稳定期

- [ ] 整理常见问题文档
- [ ] 完善规则库
- [ ] 考虑A/B测试更激进配置

---

## 联系支持

如遇到无法解决的问题：

1. 查看 `docs/HYBRID_ROUTER_GUIDE.md` 详细指南
2. 运行 `python test_hybrid_router.py` 诊断
3. 收集日志和错误信息
4. 检查GitHub issues

---

**部署完成！祝运行顺利！** 🎉
