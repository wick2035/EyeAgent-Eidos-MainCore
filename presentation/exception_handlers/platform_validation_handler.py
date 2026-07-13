import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response


logger = logging.getLogger(__name__)

_ERROR_CODE = "INVALID_PLATFORM_REQUEST"
_PLATFORM_ROUTE_TEMPLATES = frozenset(
    {
        ("DELETE", "/api/platform/research-documents/{attachment_id}"),
        ("POST", "/api/platform/chat/turns/prepare"),
        ("POST", "/api/platform/chat/turns/execute"),
        ("GET", "/api/platform/chat/turns/{request_id}"),
        ("POST", "/api/platform/chat/turns/{request_id}/abort"),
    }
)


def _route_matches(path: str, route_template: str) -> bool:
    path_segments = path.split("/")
    template_segments = route_template.split("/")
    if len(path_segments) != len(template_segments):
        return False
    return all(
        bool(path_segment)
        if template_segment.startswith("{") and template_segment.endswith("}")
        else path_segment == template_segment
        for path_segment, template_segment in zip(
            path_segments,
            template_segments,
            strict=True,
        )
    )


def _platform_route_template(request: Request) -> str | None:
    method = request.method.upper()
    path = request.url.path
    for candidate_method, route_template in _PLATFORM_ROUTE_TEMPLATES:
        if candidate_method == method and _route_matches(path, route_template):
            return route_template
    return None


async def platform_request_validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> Response:
    route_template = _platform_route_template(request)
    if route_template is None:
        return await request_validation_exception_handler(request, exc)

    logger.warning(
        "platform_validation_failed method=%s path=%s error_code=%s",
        request.method.upper(),
        route_template,
        _ERROR_CODE,
        exc_info=None,
    )
    return JSONResponse(
        status_code=422,
        content={"error_code": _ERROR_CODE},
    )


def install_platform_validation_handler(app: FastAPI) -> None:
    app.add_exception_handler(
        RequestValidationError,
        platform_request_validation_handler,
    )
