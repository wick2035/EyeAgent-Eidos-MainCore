import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from application.services.chat_turn_execution_registry import (
    ChatTurnExecutionRegistry,
    get_chat_turn_execution_registry,
)
from application.services.platform_chat_turn_execution_service import (
    PlatformChatTurnExecutionService,
    get_platform_chat_turn_execution_service,
)
from application.services.platform_chat_turn_service import (
    ChatTurnNotFoundError,
    InvalidTurnStateError,
    PlatformChatTurnService,
    RequestIdempotencyConflictError,
    TurnAlreadyCompletedError,
)
from domain.security.principal import CurrentPrincipal
from presentation.dependencies.security import (
    get_current_principal,
    require_platform_doctor,
    require_platform_doctor_subject,
)
from presentation.schemas.platform_chat_turn_schemas import (
    AbortPlatformChatTurnRequest,
    AbortPlatformChatTurnResponse,
    ExecutePlatformChatTurnRequest,
    PlatformChatTurnStatusResponse,
    PreparePlatformChatTurnRequest,
    PreparePlatformChatTurnResponse,
)


router = APIRouter(prefix="/api/platform/chat/turns", tags=["platform-chat-turns"])


def get_platform_chat_turn_service() -> PlatformChatTurnService:
    return PlatformChatTurnService()


def _require_subject(
    request: Request,
    doctor_id: str | None = None,
) -> CurrentPrincipal:
    principal = get_current_principal(request)
    if principal is None:
        # 复用统一的 401 错误结构。
        return require_platform_doctor_subject(request, doctor_id or "")
    return require_platform_doctor_subject(
        request,
        doctor_id or principal.subject,
    )


def _require_principal(
    request: Request,
    doctor_id: str | None = None,
    agent_type: str | None = "health",
) -> CurrentPrincipal:
    principal = _require_subject(request, doctor_id)
    return require_platform_doctor(
        request,
        doctor_id or principal.subject,
        agent_type,
    )


@router.post("/prepare", response_model=PreparePlatformChatTurnResponse)
async def prepare_platform_chat_turn(
    payload: PreparePlatformChatTurnRequest,
    request: Request,
    service: PlatformChatTurnService = Depends(get_platform_chat_turn_service),
) -> PreparePlatformChatTurnResponse:
    _require_principal(
        request,
        payload.doctor_id,
        payload.agent_type or "health",
    )
    try:
        return service.prepare(payload)
    except ChatTurnNotFoundError as exc:
        raise _http_error(404, exc.code) from exc
    except RequestIdempotencyConflictError as exc:
        raise _http_error(409, exc.code) from exc
    except ValueError as exc:
        raise _http_error(400, "PLATFORM_TURN_PREPARE_REJECTED") from exc


@router.post("/execute")
async def execute_platform_chat_turn(
    payload: ExecutePlatformChatTurnRequest,
    request: Request,
    service: PlatformChatTurnExecutionService = Depends(
        get_platform_chat_turn_execution_service
    ),
) -> StreamingResponse:
    principal = _require_principal(
        request,
        payload.doctor_id,
        payload.agent_type or "health",
    )

    async def stream_sse() -> AsyncGenerator[str, None]:
        execution = service.stream(payload, principal)
        try:
            async for event in execution:
                yield "data: " + json.dumps(
                    event,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ) + "\n\n"
        finally:
            await execution.aclose()

    return StreamingResponse(
        stream_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{request_id}", response_model=PlatformChatTurnStatusResponse)
async def get_platform_chat_turn_status(
    request_id: str,
    request: Request,
    service: PlatformChatTurnService = Depends(get_platform_chat_turn_service),
) -> PlatformChatTurnStatusResponse:
    principal = _require_subject(request)
    try:
        entity = service.assert_turn_conversation(
            principal.subject,
            request_id,
            None,
        )
        _require_principal(request, principal.subject, entity.agent_type)
        return service.status(principal.subject, request_id)
    except ChatTurnNotFoundError as exc:
        raise _http_error(404, exc.code) from exc


@router.post("/{request_id}/abort", response_model=AbortPlatformChatTurnResponse)
async def abort_platform_chat_turn(
    request_id: str,
    payload: AbortPlatformChatTurnRequest,
    request: Request,
    service: PlatformChatTurnService = Depends(get_platform_chat_turn_service),
    registry: ChatTurnExecutionRegistry = Depends(get_chat_turn_execution_registry),
) -> AbortPlatformChatTurnResponse:
    principal = _require_subject(request, payload.doctor_id)
    try:
        # 先用 principal subject + conversation 做完整归属校验，成功后才发进程内信号。
        entity = service.assert_turn_conversation(
            principal.subject,
            request_id,
            payload.conversation_id,
        )
        _require_principal(request, principal.subject, entity.agent_type)
        registry.signal(principal.subject, request_id)
        result = service.abort(
            principal.subject,
            request_id,
            payload.conversation_id,
        )
        if not isinstance(result, AbortPlatformChatTurnResponse):
            raise InvalidTurnStateError()
        return result
    except ChatTurnNotFoundError as exc:
        raise _http_error(404, exc.code) from exc
    except TurnAlreadyCompletedError as exc:
        raise _http_error(409, exc.code) from exc
    except InvalidTurnStateError as exc:
        raise _http_error(409, exc.code) from exc


def _http_error(status_code: int, error_code: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error_code": error_code},
    )


__all__ = ["router"]
