from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis
from datetime import datetime, timedelta
import logging
import time
from typing import Optional, Dict, Set

# Middleware metadata
MIDDLEWARE_METADATA = {
    "created_at": "2025-11-02 18:39:25",
    "created_by": "electricwolfemarshmallowhypertext",
    "version": "1.0.0"
}

logger = logging.getLogger("sticky.api.middleware.rate_limit")

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis"""
    
    def __init__(
        self,
        app,
        redis_url: str,
        window_seconds: int = 60,
        default_limit: int = 50,
        exclude_paths: Optional[Set[str]] = None,
        created_at: str = MIDDLEWARE_METADATA["created_at"],
        created_by: str = MIDDLEWARE_METADATA["created_by"]
    ):
        super().__init__(app)
        self.redis = redis.from_url(redis_url)
        self.window_seconds = window_seconds
        self.default_limit = default_limit
        self.exclude_paths = exclude_paths or {"/health"}
        self._created_at = created_at
        self._created_by = created_by
        
        # Configure tier limits
        self.tier_limits = {
            "free": default_limit,
            "pro": default_limit * 10,
            "premium": default_limit * 20
        }
        
    async def dispatch(
        self,
        request: Request,
        call_next
    ):
        """Process request and apply rate limiting"""
        start_time = time.time()
        
        try:
            # Skip rate limiting for excluded paths
            if request.url.path in self.exclude_paths:
                response = await call_next(request)
                return response
                
            # Get user info from state
            user = getattr(request.state, "user", None)
            user_id = user["uid"] if user else "anonymous"
            tier = user["tier"] if user else "free"
            
            # Check rate limit
            current_window = self._get_current_window()
            rate_limit_key = f"rl:{user_id}:{current_window}"
            
            # Get current count and limit
            current_count = int(self.redis.get(rate_limit_key) or 0)
            rate_limit = self.tier_limits.get(tier, self.default_limit)
            
            if current_count >= rate_limit:
                # Rate limit exceeded
                reset_time = self._get_window_reset()
                
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "user_id": user_id,
                        "tier": tier,
                        "path": request.url.path,
                        "count": current_count,
                        "limit": rate_limit,
                        "request_id": request.state.request_id
                    }
                )
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": rate_limit,
                        "reset_in_seconds": reset_time,
                        "tier": tier
                    }
                )
                
            # Increment counter
            pipe = self.redis.pipeline()
            pipe.incr(rate_limit_key)
            pipe.expire(rate_limit_key, self.window_seconds)
            pipe.execute()
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            remaining = rate_limit - (current_count + 1)
            response.headers["X-RateLimit-Limit"] = str(rate_limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
            response.headers["X-RateLimit-Reset"] = str(self._get_window_reset())
            
            # Log success
            duration = time.time() - start_time
            logger.info(
                "Rate limit check successful",
                extra={
                    "user_id": user_id,
                    "tier": tier,
                    "path": request.url.path,
                    "count": current_count + 1,
                    "limit": rate_limit,
                    "duration_ms": round(duration * 1000, 2),
                    "request_id": request.state.request_id
                }
            )
            
            return response
            
        except HTTPException:
            raise
            
        except Exception as e:
            # Log unexpected errors
            duration = time.time() - start_time
            logger.error(
                "Rate limit error",
                extra={
                    "path": request.url.path,
                    "error": str(e),
                    "duration_ms": round(duration * 1000, 2),
                    "request_id": request.state.request_id
                },
                exc_info=True
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Rate limiting system error",
                    "detail": str(e),
                    "request_id": request.state.request_id
                }
            )
            
    def _get_current_window(self) -> str:
        """Get current time window key"""
        now = datetime.utcnow()
        window = now.replace(
            second=0,
            microsecond=0
        )
        return window.strftime("%Y%m%d%H%M")
        
    def _get_window_reset(self) -> int:
        """Get seconds until window reset"""
        now = datetime.utcnow()
        next_window = now.replace(
            second=0,
            microsecond=0
        ) + timedelta(minutes=1)
        return int((next_window - now).total_seconds())
        
    async def check_rate_limit(
        self,
        user_id: str,
        tier: str = "free"
    ) -> Dict:
        """Check rate limit for user"""
        try:
            current_window = self._get_current_window()
            rate_limit_key = f"rl:{user_id}:{current_window}"
            
            current_count = int(self.redis.get(rate_limit_key) or 0)
            rate_limit = self.tier_limits.get(tier, self.default_limit)
            
            return {
                "current": current_count,
                "limit": rate_limit,
                "remaining": max(0, rate_limit - current_count),
                "reset_in": self._get_window_reset()
            }
            
        except Exception as e:
            logger.error(
                "Rate limit check failed",
                extra={
                    "user_id": user_id,
                    "tier": tier,
                    "error": str(e)
                },
                exc_info=True
            )
            raise