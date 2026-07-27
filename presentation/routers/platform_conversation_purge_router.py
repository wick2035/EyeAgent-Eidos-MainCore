from fastapi import APIRouter, Depends, HTTPException, Request, Response

from application.services.platform_conversation_purge_service import (
    PlatformConversationPurgeBusyError,
    PlatformConversationPurgeForbiddenError,
    PlatformConversationPurgeNotFoundError,
    PlatformConversationPurgeService,
    get_platform_conversation_purge_service,
)
from presentation.dependencies.security import (
    require_platform_conversation_write,
    require_platform_doctor_subject,
)
from presentation.schemas.platform_conversation_purge_schemas import (
    PlatformConversationPurgeRequest,
)


router = APIRouter(
    prefix="/api/platform/conversations",
    tags=["platform-conversations"],
)


@router.delete(
    "/{conversationId}/purge",
    status_code=204,
)
async def purge_platform_conversation(
    conversationId: str,
    payload: PlatformConversationPurgeRequest,
    request: Request,
    service: PlatformConversationPurgeService = Depends(
        get_platform_conversation_purge_service
    ),
) -> Response:
    require_platform_doctor_subject(request, payload.doctor_id)
    principal = require_platform_conversation_write(request)
    try:
        service.purge(conversationId, principal.subject)
    except PlatformConversationPurgeNotFoundError as exc:
        raise _http_error(404, exc.code) from exc
    except PlatformConversationPurgeForbiddenError as exc:
        raise _http_error(403, exc.code) from exc
    except PlatformConversationPurgeBusyError as exc:
        raise _http_error(409, exc.code) from exc

    return Response(status_code=204)


def _http_error(status_code: int, error_code: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error_code": error_code},
    )


__all__ = ["router"]
