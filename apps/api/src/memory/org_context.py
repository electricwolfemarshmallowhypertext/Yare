from __future__ import annotations

from typing import Optional, Dict, Any, Set, Callable
from fastapi import Header, HTTPException, status, Depends

def get_org_id(x_org_id: Optional[str] = Header(None, alias="X-Org-Id")) -> str:
    if not x_org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Org-Id header required")
    return x_org_id

def require_org_permission(permission: str, authorizer, get_api_info: Callable):
    async def dep(org_id: str = Depends(get_org_id), info: Dict[str, Any] = Depends(get_api_info)):
        roles: Set[str] = set(info.get("roles") or [])
        # Optionally enforce org binding on the key: info may include allowed_org_id
        key_org = info.get("org_id")
        if key_org and key_org != org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Key not permitted for org")
        if not roles or not authorizer.is_allowed(roles, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        info["org_id"] = org_id
        return info
    return dep