from fastapi import HTTPException, Request

from domain.security.principal import CurrentPrincipal


def get_current_principal(request: Request) -> CurrentPrincipal | None:
    return getattr(request.state, "internal_principal", None)


def scope_for_platform_agent(agent_type: str | None) -> str:
    if agent_type in (None, "health"):
        return "ai:chat"
    if agent_type == "research":
        return "ai:research"
    raise ValueError("不支持的 platform agent_type")


def require_platform_doctor_subject(
    request: Request,
    doctor_id: str,
) -> CurrentPrincipal:
    principal = get_current_principal(request)
    if principal is None:
        raise HTTPException(
            status_code=401,
            detail={"error_code": "PLATFORM_AUTH_REQUIRED"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if (
        principal.principal_type != "doctor"
        or principal.subject != doctor_id
    ):
        raise HTTPException(
            status_code=403,
            detail={"error_code": "PLATFORM_DOCTOR_FORBIDDEN"},
        )
    return principal


def require_platform_doctor(
    request: Request,
    doctor_id: str,
    agent_type: str | None = "health",
) -> CurrentPrincipal:
    principal = require_platform_doctor_subject(request, doctor_id)
    try:
        required_scope = scope_for_platform_agent(agent_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail={"error_code": "PLATFORM_DOCTOR_FORBIDDEN"},
        ) from exc
    if required_scope not in principal.scopes:
        raise HTTPException(
            status_code=403,
            detail={"error_code": "PLATFORM_DOCTOR_FORBIDDEN"},
        )
    return principal
