"""Organization and user domain models (multi-tenant, auth-ready)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


# Roles supported by the users table CHECK constraint.
USER_ROLES = ("admin", "scientist", "guardian", "viewer")


@dataclass
class Organization:
    """A tenant in the Genovate platform."""

    id: UUID
    name: str
    created_at: datetime

    @classmethod
    def from_row(cls, row) -> "Organization":
        return cls(id=row["id"], name=row["name"], created_at=row["created_at"])


@dataclass
class User:
    """A user belonging to an organization."""

    id: UUID
    email: str
    organization_id: UUID
    role: str
    created_at: datetime

    def __post_init__(self) -> None:
        if self.role not in USER_ROLES:
            raise ValueError(
                f"Invalid role {self.role!r}; must be one of {USER_ROLES}"
            )

    @classmethod
    def from_row(cls, row) -> "User":
        return cls(
            id=row["id"],
            email=row["email"],
            organization_id=row["organization_id"],
            role=row["role"],
            created_at=row["created_at"],
        )
