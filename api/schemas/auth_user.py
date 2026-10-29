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
    # Whether they confirmed their email (see auth/service.verify_email)
    email_verified: bool = False

    @property
    def uuid(self) -> UUID:
        return UUID(self.id)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
