from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime
import logging

from ..memory import get_memory, MemoryEngine
from ..deps import get_current_user

# Router metadata
ROUTER_METADATA = {
    "created_at": "2025-11-02 18:31:45",
    "created_by": "electricwolfemarshmallowhypertext",
    "version": "1.0.0"
}

# Configure logging
logger = logging.getLogger("sticky.api.memory")

router = APIRouter()

class MemoryEvent(BaseModel):
    """Memory event model"""
    text: str
    salience: float = Field(ge=0.0, le=1.0)
    type: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class MemoryRequest(BaseModel):
    """Memory creation/update request"""
    thread_id: str
    text: str
    type: str = "fact"
    salience: float = Field(0.5, ge=0.0, le=1.0)

class MemoryResponse(BaseModel):
    """Memory response model"""
    events: List[MemoryEvent]
    thread_id: str
    request_id: str

@router.get("/threads/{thread_id}")
async def get_memories(
    thread_id: str,
    req: Request,
    memory: MemoryEngine = Depends(get_memory),
    user: Dict = Depends(get_current_user)
):
    """
    Retrieve memories for a specific thread
    """
    try:
        # Load memories
        events = await memory._load_memories(
            user["uid"],
            thread_id
        )
        
        return MemoryResponse(
            events=[MemoryEvent(**event) for event in events],
            thread_id=thread_id,
            request_id=req.state.request_id
        )
        
    except Exception as e:
        logger.error(
            "Failed to retrieve memories",
            extra={
                "thread_id": thread_id,
                "user_id": user["uid"],
                "request_id": req.state.request_id,
                "error": str(e)
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to retrieve memories",
                "detail": str(e),
                "request_id": req.state.request_id
            }
        )

@router.post("/threads/{thread_id}")
async def create_memory(
    thread_id: str,
    request: MemoryRequest,
    req: Request,
    memory: MemoryEngine = Depends(get_memory),
    user: Dict = Depends(get_current_user)
):
    """
    Create a new memory event
    """
    try:
        # Store memory
        event = await memory.store_memory(
            user["uid"],
            thread_id,
            text=request.text,
            type=request.type,
            salience=request.salience
        )
        
        logger.info(
            "Memory created",
            extra={
                "thread_id": thread_id,
                "user_id": user["uid"],
                "request_id": req.state.request_id,
                "memory_type": request.type
            }
        )
        
        return MemoryEvent(**event)
        
    except Exception as e:
        logger.error(
            "Failed to create memory",
            extra={
                "thread_id": thread_id,
                "user_id": user["uid"],
                "request_id": req.state.request_id,
                "error": str(e)
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to create memory",
                "detail": str(e),
                "request_id": req.state.request_id
            }
        )

@router.delete("/threads/{thread_id}")
async def clear_memories(
    thread_id: str,
    req: Request,
    memory: MemoryEngine = Depends(get_memory),
    user: Dict = Depends(get_current_user)
):
    """
    Clear all memories for a thread
    """
    try:
        await memory.clear_memories(
            user["uid"],
            thread_id
        )
        
        logger.info(
            "Memories cleared",
            extra={
                "thread_id": thread_id,
                "user_id": user["uid"],
                "request_id": req.state.request_id
            }
        )
        
        return {
            "status": "success",
            "thread_id": thread_id,
            "request_id": req.state.request_id
        }
        
    except Exception as e:
        logger.error(
            "Failed to clear memories",
            extra={
                "thread_id": thread_id,
                "user_id": user["uid"],
                "request_id": req.state.request_id,
                "error": str(e)
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to clear memories",
                "detail": str(e),
                "request_id": req.state.request_id
            }
        )

@router.get("/search")
async def search_memories(
    query: str,
    req: Request,
    memory: MemoryEngine = Depends(get_memory),
    user: Dict = Depends(get_current_user),
    thread_id: Optional[str] = None,
    limit: int = 10
):
    """
    Search through memories
    """
    try:
        results = await memory.search_memories(
            user["uid"],
            query,
            thread_id=thread_id,
            limit=limit
        )
        
        return {
            "results": [MemoryEvent(**event) for event in results],
            "query": query,
            "thread_id": thread_id,
            "request_id": req.state.request_id
        }
        
    except Exception as e:
        logger.error(
            "Failed to search memories",
            extra={
                "user_id": user["uid"],
                "query": query,
                "thread_id": thread_id,
                "request_id": req.state.request_id,
                "error": str(e)
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to search memories",
                "detail": str(e),
                "request_id": req.state.request_id
            }
        )