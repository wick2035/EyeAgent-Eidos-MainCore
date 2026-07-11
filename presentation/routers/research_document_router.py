"""平台科研文档删除接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response

from infrastructure.database.mysql_connection import get_db_connection
from infrastructure.repositories.research_document_repository_impl import (
    get_research_document_repository as _get_research_document_repository,
)
from presentation.dependencies.security import require_platform_doctor
from presentation.schemas.research_document_schemas import (
    PurgeResearchDocumentRequest,
    UUID_PATTERN,
)


router = APIRouter(
    prefix="/api/platform/research-documents",
    tags=["platform-research-documents"],
)


def get_research_document_db():
    return get_db_connection()


def get_research_document_repository():
    return _get_research_document_repository()


@router.delete(
    "/{attachment_id}",
    status_code=204,
    response_class=Response,
)
async def purge_research_document(
    attachment_id: Annotated[
        str,
        Path(strict=True, pattern=UUID_PATTERN),
    ],
    payload: PurgeResearchDocumentRequest,
    request: Request,
    db=Depends(get_research_document_db),
    repository=Depends(get_research_document_repository),
) -> Response:
    principal = require_platform_doctor(
        request,
        payload.doctor_id,
        "research",
    )
    with db.transaction():
        repository.purge(principal.subject, attachment_id)
    return Response(status_code=204)


__all__ = [
    "get_research_document_db",
    "get_research_document_repository",
    "router",
]
