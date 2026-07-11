from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from domain.security.principal import CurrentPrincipal


INTERNAL_AUTH_EFFECTIVE_MODE_SCOPE_KEY = "_internal_auth_effective_mode"


class LegacyRouteError(Exception):
    """旧平台路由的稳定公开错误；正文不得携带底层异常。"""

    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code


async def legacy_route_error_handler(
    _request: Request,
    exc: LegacyRouteError,
) -> JSONResponse:
    headers = (
        {"WWW-Authenticate": "Bearer"}
        if exc.status_code == 401
        else None
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code},
        headers=headers,
    )


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


def require_legacy_platform_doctor(
    request: Request,
    doctor_id: str,
    agent_type: str | None = "health",
) -> CurrentPrincipal | None:
    """仅在 effective enforce 下收紧旧路由，保留 off/observe rollout。"""

    effective_mode = request.scope.get(
        INTERNAL_AUTH_EFFECTIVE_MODE_SCOPE_KEY,
        "enforce",
    )
    if effective_mode != "enforce":
        return get_current_principal(request)

    try:
        return require_platform_doctor(request, doctor_id, agent_type)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        code = detail.get("error_code")
        if code not in {
            "PLATFORM_AUTH_REQUIRED",
            "PLATFORM_DOCTOR_FORBIDDEN",
        }:
            code = "PLATFORM_DOCTOR_FORBIDDEN"
        raise LegacyRouteError(exc.status_code, code) from None
