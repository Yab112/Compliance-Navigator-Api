"""The signed-in user behind a request."""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class AuthUser:
    id: str
    email: str
    fullname: str = ""
    role: str = "user"
    session_id: str | None = None

    @property
    def uuid(self) -> UUID:
        return UUID(self.id)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
