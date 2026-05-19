from fastapi import Depends, HTTPException, Request, status
from firebase_admin import auth
from typing import Dict, Optional
import os
import redis
from functools import lru_cache

from .providers import ProviderRegistry
from .personas import PersonaRegistry
from .memory import MemoryEngine

# Module metadata
MODULE_METADATA = {
    "created_at": "2025-11-02 18:33:18",
    "created_by": "electricwolfemarshmallowhypertext",
    "version": "1.0.0"
}

@lru_cache()
def get_redis_client() -> redis.Redis:
    """
    Get Redis client singleton
    """
    return redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True
    )

@lru_cache()
def get_providers() -> ProviderRegistry:
    """
    Get provider registry singleton
    """
    return ProviderRegistry()

@lru_cache()
def get_personas() -> PersonaRegistry:
    """
    Get persona registry singleton
    """
    return PersonaRegistry()

@lru_cache()
def get_memory() -> MemoryEngine:
    """
    Get memory engine singleton
    """
    return MemoryEngine(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        redis_ttl=int(os.getenv("MEMORY_TTL", 3600)),
        timestamp=MODULE_METADATA["created_at"],
        user=MODULE_METADATA["created_by"]
    )

def get_provider(persona_id: Optional[str] = None):
    """
    Get appropriate provider based on persona
    """
    registry = get_providers()
    if persona_id:
        persona = get_personas().get(persona_id)
        return registry.get(persona.defaults["provider"])
    return registry.default_provider

async def get_current_user(request: Request) -> Dict:
    """
    Get current authenticated user from request
    """
    try:
        # Get token from header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header"
            )
            
        token = auth_header.split(" ")[1]
        
        # Verify token
        try:
            decoded_token = auth.verify_id_token(token)
        except auth.InvalidIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        except auth.RevokedIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked"
            )
            
        # Get user data
        try:
            user = auth.get_user(decoded_token["uid"])
        except auth.UserNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
            
        # Determine user tier
        claims = user.custom_claims or {}
        if claims.get("premium"):
            tier = "premium"
        elif claims.get("pro"):
            tier = "pro"
        else:
            tier = "free"
            
        # Return user data
        return {
            "uid": user.uid,
            "email": user.email,
            "tier": tier,
            "claims": claims
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )

def get_rate_limit(user: Dict = Depends(get_current_user)) -> int:
    """
    Get rate limit based on user tier
    """
    limits = {
        "free": int(os.getenv("RATE_LIMIT_FREE", 50)),
        "pro": int(os.getenv("RATE_LIMIT_PRO", 500)),
        "premium": int(os.getenv("RATE_LIMIT_PREMIUM", 2000))
    }
    return limits.get(user["tier"], limits["free"])

def get_token_limit(user: Dict = Depends(get_current_user)) -> int:
    """
    Get token limit based on user tier
    """
    limits = {
        "free": int(os.getenv("TOKEN_LIMIT_FREE", 1000)),
        "pro": int(os.getenv("TOKEN_LIMIT_PRO", 4000)),
        "premium": int(os.getenv("TOKEN_LIMIT_PREMIUM", 8000))
    }
    return limits.get(user["tier"], limits["free"])

def get_memory_ttl(user: Dict = Depends(get_current_user)) -> int:
    """
    Get memory TTL based on user tier
    """
    ttls = {
        "free": int(os.getenv("MEMORY_TTL_FREE", 3600)),
        "pro": int(os.getenv("MEMORY_TTL_PRO", 86400)),
        "premium": int(os.getenv("MEMORY_TTL_PREMIUM", 604800))
    }
    return ttls.get(user["tier"], ttls["free"])