from datetime import datetime
from typing import Optional, Protocol

from domain.models.research_dataset import ResearchDatasetMaterialization
from domain.models.research_document import (
    IngestionIdentity,
    ResearchDocumentClaimResult,
    ResearchDocumentIngestionEntity,
    ResearchDocumentSegmentEntity,
)


class ResearchDocumentRepository(Protocol):
    def get_ready(
        self,
        identity: IngestionIdentity,
    ) -> Optional[ResearchDocumentIngestionEntity]: ...

    def claim(
        self,
        identity: IngestionIdentity,
        now: datetime,
        lease_until: datetime,
    ) -> ResearchDocumentClaimResult: ...

    def renew_lease(
        self,
        ingestion_id: str,
        attempt_count: int,
        lease_until: datetime,
    ) -> bool: ...

    def complete(
        self,
        ingestion_id: str,
        attempt_count: int,
        segments: list[ResearchDocumentSegmentEntity],
        dataset: Optional[ResearchDatasetMaterialization] = None,
    ) -> bool: ...

    def fail(
        self,
        ingestion_id: str,
        attempt_count: int,
        error_code: str,
    ) -> bool: ...

    def list_segments(
        self,
        ingestion_ids: list[str],
    ) -> list[ResearchDocumentSegmentEntity]: ...

    def purge(self, doctor_id: str, attachment_id: str) -> int: ...
