from fastapi import Request

from domain.security.principal import CurrentPrincipal


def get_current_principal(request: Request) -> CurrentPrincipal | None:
    return getattr(request.state, "internal_principal", None)
