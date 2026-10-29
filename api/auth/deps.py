"""Re-export for backward compatibility, prefer core.deps in new code."""

from core.deps import get_current_user

__all__ = ["get_current_user"]
