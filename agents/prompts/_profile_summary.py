"""
患者综合画像摘要 helper（跨 Agent 共享）

从 state.patient_full_data（由 GraphManager 在每轮请求前调用
patient-comprehensive-profile 接口注入）提炼简短文字摘要，
用于个性化 prompt context 拼接。
"""
from typing import Any, Dict


def build_patient_profile_summary(
    state: Dict[str, Any],
    max_records: int = 2,
    max_checks: int = 2,
    max_prescriptions: int = 2,
) -> str:
    """从 state.patient_full_data 提炼简短画像摘要。

    Args:
        state: MedicalState
        max_records: 最多展示几条最近病历
        max_checks: 最多展示几条最近检查
        max_prescriptions: 最多展示几条最近处方

    Returns:
        摘要字符串；若 patient_full_data 缺失或全为空，返回空串。
    """
    pfd = state.get("patient_full_data") if isinstance(state, dict) else None
    if not pfd:
        return ""

    parts = []

    # 1) 最近病历
    records = pfd.get("medical_records") or []
    if records:
        parts.append("【最近病历】")
        for r in records[:max_records]:
            visit = r.get("visitDate") or r.get("visit_date") or ""
            dept = r.get("department") or ""
            diag = r.get("diagnosis") or r.get("aiDiagnosis") or "待诊断"
            visit_short = visit[:10] if isinstance(visit, str) else ""
            parts.append(f"- {visit_short} {dept} | 诊断：{diag}")

    # 2) 最近检查
    checks = pfd.get("check_history") or []
    if checks:
        parts.append("【最近检查】")
        for c in checks[:max_checks]:
            report = c.get("reportNumber") or ""
            va_od = c.get("vaOd")
            va_os = c.get("vaOs")
            myopia = c.get("myopiaRisk")
            ai_diag = c.get("aiDiagnosis") or c.get("resultContent") or ""
            line = f"- {report}"
            if va_od is not None or va_os is not None:
                line += f" 视力 OD/OS={va_od}/{va_os}"
            if myopia is not None:
                line += f" 近视风险={myopia}"
            if ai_diag:
                ai_diag_str = str(ai_diag)
                line += f" | {ai_diag_str[:40]}"
            parts.append(line)

    # 3) 最近处方（仅摘要，不展开明细）
    prescriptions = pfd.get("prescriptions") or []
    if prescriptions:
        parts.append("【近期处方】")
        for p in prescriptions[:max_prescriptions]:
            pres = p.get("prescription") or {}
            num = pres.get("prescriptionNumber") or ""
            pid = pres.get("id") or ""
            status = pres.get("prescriptionStatus") or ""
            details = p.get("details") or []
            drug_names = [d.get("drugName", "") for d in details[:3] if d.get("drugName")]
            line = f"- {num} [{status}]"
            if drug_names:
                line += f" 含: {', '.join(drug_names)}"
            if pid:
                line += f" (prescriptionId={pid})"
            parts.append(line)

    if not parts:
        return ""
    return "\n".join(parts)
