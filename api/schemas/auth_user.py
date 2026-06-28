"""Authenticated user from Supabase Auth (not Neo4j)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class AuthUser:
    id: str
    email: str
    fullname: str = ""

    @property
    def uuid(self) -> UUID:
        return UUID(self.id)
