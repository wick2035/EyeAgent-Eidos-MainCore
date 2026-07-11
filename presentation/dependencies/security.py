from fastapi import HTTPException, Request

from domain.security.principal import CurrentPrincipal


def get_current_principal(request: Request) -> CurrentPrincipal | None:
    return getattr(request.state, "internal_principal", None)


def require_platform_doctor(
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
        or "ai:chat" not in principal.scopes
        or principal.subject != doctor_id
    ):
        raise HTTPException(
            status_code=403,
            detail={"error_code": "PLATFORM_DOCTOR_FORBIDDEN"},
        )
    return principal
