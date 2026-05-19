from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import logging
import redis
import os
from firebase_admin import auth

from ..deps import get_memory, get_personas, get_providers

# Router metadata
ROUTER_METADATA = {
    "created_at": "2025-11-02 18:32:31",
    "created_by": "electricwolfemarshmallowhypertext",
    "version": "1.0.0"
}

# Configure logging
logger = logging.getLogger("sticky.api.health")

router = APIRouter()

class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    timestamp: str
    build: Dict[str, str]
    components: Dict[str, Dict]
    environment: str

async def _check_redis() -> Dict:
    """Test Redis connection and functionality"""
    try:
        client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        start_time = datetime.now()
        client.ping()
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2)
        }
    except Exception as e:
        logger.error("Redis health check failed", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e)
        }

async def _check_firebase() -> Dict:
    """Test Firebase connection and functionality"""
    try:
        # Try to get a test user (will fail with UserNotFoundError)
        try:
            auth.get_user('test_health_check')
        except auth.UserNotFoundError:
            # Expected error - service is working
            return {"status": "healthy"}
        
        return {"status": "configured"}
    except Exception as e:
        logger.error("Firebase health check failed", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/health", response_model=HealthResponse)
async def health_check(
    request: Request,
    memory = Depends(get_memory),
    personas = Depends(get_personas),
    providers = Depends(get_providers)
) -> Dict:
    """
    Comprehensive health check endpoint
    Tests all system components and returns detailed status
    """
    try:
        # Component checks
        redis_status = await _check_redis()
        firebase_status = await _check_firebase()
        
        # Build response
        response = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "build": {
                "timestamp": ROUTER_METADATA["created_at"],
                "author": ROUTER_METADATA["created_by"],
                "version": ROUTER_METADATA["version"]
            },
            "components": {
                "redis": redis_status,
                "firebase": firebase_status,
                "personas": {
                    "count": len(personas.list_all()),
                    "load_info": personas.load_info
                },
                "providers": {
                    "available": list(providers.keys()),
                    "default": providers.default_provider
                },
                "memory": {
                    "status": "configured",
                    "backend": memory.backend_type
                }
            },
            "environment": os.getenv("ENVIRONMENT", "production")
        }
        
        # Determine overall status
        component_statuses = [
            redis_status["status"],
            firebase_status["status"]
        ]
        if any(status == "unhealthy" for status in component_statuses):
            response["status"] = "degraded"
            
        logger.info(
            "Health check completed",
            extra={
                "status": response["status"],
                "request_id": request.state.request_id,
                "components": response["components"]
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "Health check failed",
            extra={
                "request_id": request.state.request_id,
                "error": str(e)
            },
            exc_info=True
        )
        
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "build": {
                "timestamp": ROUTER_METADATA["created_at"],
                "author": ROUTER_METADATA["created_by"],
                "version": ROUTER_METADATA["version"]
            },
            "components": {
                "error": str(e)
            },
            "environment": os.getenv("ENVIRONMENT", "production")
        }

@router.get("/health/redis")
async def redis_health() -> Dict:
    """
    Redis-specific health check
    Tests Redis connection and basic operations
    """
    return await _check_redis()

@router.get("/health/firebase")
async def firebase_health() -> Dict:
    """
    Firebase-specific health check
    Tests Firebase Authentication service
    """
    return await _check_firebase()