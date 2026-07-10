from dataclasses import dataclass
from typing import FrozenSet, Optional


@dataclass(frozen=True, slots=True)
class CurrentPrincipal:
    issuer: str
    subject: str
    principal_type: str
    roles: FrozenSet[str]
    scopes: FrozenSet[str]
    institution_id: Optional[str]
    tenant_id: Optional[str]
    authorized_party: str
    schema_version: int
    token_id: str
    issued_at: int
    not_before: int
    expires_at: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", frozenset(self.roles))
        object.__setattr__(self, "scopes", frozenset(self.scopes))
