from typing import Protocol

from domain.models.research_dataset import ResearchDatasetMaterialization
from domain.models.research_dataset_query import ResearchDatasetAccessScope


class ResearchDatasetQueryRepository(Protocol):
    def load_authorized(
        self,
        scope: ResearchDatasetAccessScope,
    ) -> ResearchDatasetMaterialization | None: ...
