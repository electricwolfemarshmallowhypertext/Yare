from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from datetime import datetime

from .routers import chat, health, memory
from .middleware.auth import AuthMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.logging import LoggingMiddleware
from .providers import setup_providers
from .personas import setup_personas
from .memory import setup_memory

# Application metadata
APP_METADATA = {
    "created_at": "2025-11-02 18:28:13",
    "created_by": "electricwolfemarshmallowhypertext",
    "version": "1.0.0"
}

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sticky.api")

def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    app = FastAPI(
        title="Sticky API",
        description="Modular AI Persona Runtime",
        version=APP_METADATA["version"],
        docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware
    app.add_middleware(
        AuthMiddleware,
        exclude_paths={"/health", "/health/redis", "/health/firebase"}
    )
    app.add_middleware(
        RateLimitMiddleware,
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    app.add_middleware(
        LoggingMiddleware,
        logger_name="sticky.api"
    )
    
    # Initialize components
    setup_providers(app)
    setup_personas(app)
    setup_memory(app)
    
    # Register routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(chat.router, prefix="/chat", tags=["Chat"])
    app.include_router(memory.router, prefix="/memory", tags=["Memory"])
    
    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler"""
        logger.error(
            f"Unhandled exception",
            extra={
                "path": request.url.path,
                "method": request.method,
                "error": str(exc)
            },
            exc_info=True
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if os.getenv("ENVIRONMENT") != "production" else None,
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": request.state.request_id
            }
        )
    
    # Startup and shutdown events
    @app.on_event("startup")
    async def startup_event():
        """Application startup handler"""
        logger.info(
            "Application starting",
            extra={
                "version": APP_METADATA["version"],
                "environment": os.getenv("ENVIRONMENT", "production")
            }
        )
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown handler"""
        logger.info("Application shutting down")
    
    return app

# Create application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8080)),
        reload=os.getenv("ENVIRONMENT") == "development"
    )