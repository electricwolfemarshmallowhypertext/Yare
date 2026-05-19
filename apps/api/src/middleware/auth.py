from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from firebase_admin import auth
from typing import Dict, Optional, Set
import logging
import time

# Middleware metadata
MIDDLEWARE_METADATA = {
    "created_at": "2025-11-02 18:37:33",
    "created_by": "electricwolfemarshmallowhypertext",
    "version": "1.0.0"
}

logger = logging.getLogger("sticky.api.middleware.auth")

class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware using Firebase"""
    
    def __init__(
        self,
        app,
        exclude_paths: Optional[Set[str]] = None,
        created_at: str = MIDDLEWARE_METADATA["created_at"],
        created_by: str = MIDDLEWARE_METADATA["created_by"]
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or set()
        self._created_at = created_at
        self._created_by = created_by
        
    async def dispatch(
        self,
        request: Request,
        call_next
    ):
        """Process request and handle authentication"""
        start_time = time.time()
        
        try:
            # Skip authentication for excluded paths
            if request.url.path in self.exclude_paths:
                response = await call_next(request)
                return response
                
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
                
            # Add user data to request state
            request.state.user = {
                "uid": user.uid,
                "email": user.email,
                "tier": tier,
                "claims": claims
            }
            
            # Process request
            response = await call_next(request)
            
            # Add user tier to response headers
            response.headers["X-User-Tier"] = tier
            
            # Log success
            duration = time.time() - start_time
            logger.info(
                "Authentication successful",
                extra={
                    "user_id": user.uid,
                    "tier": tier,
                    "path": request.url.path,
                    "duration_ms": round(duration * 1000, 2),
                    "request_id": request.state.request_id
                }
            )
            
            return response
            
        except HTTPException as e:
            # Log authentication failure
            duration = time.time() - start_time
            logger.warning(
                "Authentication failed",
                extra={
                    "path": request.url.path,
                    "error": str(e.detail),
                    "duration_ms": round(duration * 1000, 2),
                    "request_id": request.state.request_id
                }
            )
            raise
            
        except Exception as e:
            # Log unexpected errors
            duration = time.time() - start_time
            logger.error(
                "Authentication error",
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
                    "error": "Authentication system error",
                    "detail": str(e),
                    "request_id": request.state.request_id
                }
            )
            
    async def authenticate_token(self, token: str) -> Dict:
        """Verify and decode Firebase token"""
        try:
            decoded_token = auth.verify_id_token(token)
            user = auth.get_user(decoded_token["uid"])
            
            claims = user.custom_claims or {}
            tier = "premium" if claims.get("premium") else "pro" if claims.get("pro") else "free"
            
            return {
                "uid": user.uid,
                "email": user.email,
                "tier": tier,
                "claims": claims
            }
            
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
        except auth.UserNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        except Exception as e:
            logger.error(
                "Token authentication failed",
                extra={"error": str(e)},
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication system error"
            )