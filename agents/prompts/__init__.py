"""
Agent 提示词模块

集中管理各 Agent 的系统提示词、阶段提示词和上下文构建。
从原有 Agent 类中提取，便于维护和复用。

模块结构：
- health_prompts: HealthAgent 提示词
- report_prompts: ReportAgent 提示词
- reminder_prompts: ReminderAgent 提示词
- research_prompts: ResearchAgent 提示词
"""

from agents.prompts.health_prompts import (
    get_health_system_prompt,
    get_health_stage_prompt,
    build_health_context,
)
from agents.prompts.report_prompts import (
    get_report_system_prompt,
    get_report_stage_prompt,
    build_report_context,
)
from agents.prompts.reminder_prompts import (
    get_reminder_system_prompt,
    get_reminder_stage_prompt,
    build_reminder_context,
)
from agents.prompts.research_prompts import (
    get_research_system_prompt,
    get_research_stage_prompt,
    build_research_context,
)

__all__ = [
    # Health
    "get_health_system_prompt",
    "get_health_stage_prompt",
    "build_health_context",
    # Report
    "get_report_system_prompt",
    "get_report_stage_prompt",
    "build_report_context",
    # Reminder
    "get_reminder_system_prompt",
    "get_reminder_stage_prompt",
    "build_reminder_context",
    # Research
    "get_research_system_prompt",
    "get_research_stage_prompt",
    "build_research_context",
]
