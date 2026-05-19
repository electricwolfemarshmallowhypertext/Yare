"""
Minimal security controls:
- API key auth
- Simple role-based authorization
- Audit logging hook
"""

from typing import Optional, Dict, Any, Set
import hashlib
import structlog

from .metrics import AUTH_DECISIONS

logger = structlog.get_logger("memory.security")


class ApiKeyAuth:
    def __init__(self, keys_to_roles: Dict[str, Set[str]]) -> None:
        # keys_to_roles maps api_key_hash -> set(roles)
        self._keys = keys_to_roles

    @staticmethod
    def hash_key(api_key: str) -> str:
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    def authenticate(self, api_key: Optional[str]) -> Optional[Set[str]]:
        if not api_key:
            AUTH_DECISIONS.labels(decision="deny", reason="missing_key").inc()
            return None
        key_hash = self.hash_key(api_key)
        roles = self._keys.get(key_hash)
        if roles is None:
            AUTH_DECISIONS.labels(decision="deny", reason="invalid_key").inc()
            return None
        AUTH_DECISIONS.labels(decision="allow", reason="valid_key").inc()
        return roles


class Authorizer:
    def __init__(self, role_permissions: Dict[str, Set[str]]) -> None:
        # role_permissions maps role -> set(permissions)
        self._role_perms = role_permissions

    def is_allowed(self, roles: Set[str], permission: str) -> bool:
        for r in roles:
            perms = self._role_perms.get(r, set())
            if permission in perms or "*" in perms:
                AUTH_DECISIONS.labels(decision="allow", reason=f"role:{r}").inc()
                return True
        AUTH_DECISIONS.labels(decision="deny", reason="insufficient_role").inc()
        return False


def audit_log(event: str, **kwargs: Any) -> None:
    # Hook for audit logging
    logger.info("audit", event=event, **kwargs)