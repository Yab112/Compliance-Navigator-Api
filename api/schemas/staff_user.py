"""The staff member behind an admin request (a different realm from public users)."""

from dataclasses import dataclass, field


@dataclass
class StaffActor:
    id: str
    email: str
    fullname: str = ""
    session_id: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)
    must_change_password: bool = False
    # Older admin code reads these from the public AuthUser; staff always pass them
    role: str = "staff"
    is_admin: bool = True

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    has = can

    @property
    def name(self) -> str:
        return self.fullname or self.email
