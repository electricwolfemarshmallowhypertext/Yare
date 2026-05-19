"""
Chat Router Implementation
Created: 2025-11-02 19:40:15
Author: electricwolfemarshmallowhypertext
Version: 1.1.0
"""

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, AsyncGenerator
from datetime import datetime
import logging
import asyncio
from contextlib import asynccontextmanager
import structlog
from prometheus_client import Counter, Histogram

from ..providers import get_provider, Provider
from ..personas import get_persona, Persona
from ..memory import get_memory, MemoryEngine
from ..auth import get_current_user, User
from ..cache import get_cache
from ..rate_limit import RateLimiter
from ..monitoring import get_metrics
from ..validation import validate_content

# Metrics
CHAT_REQUESTS = Counter(
    "chat_requests_total",
    "Total chat requests",
    ["user_id", "persona_id", "status"]
)
CHAT_LATENCY = Histogram(
    "chat_request_duration_seconds",
    "Chat request duration",
    ["user_id", "persona_id"]
)

logger = structlog.get_logger("sticky.api.chat")
router = APIRouter()

class ChatRequest(BaseModel):
    """Chat request model with validation"""
    thread_id: str = Field(..., description="Unique thread identifier")
    persona_id: str = Field(..., description="Persona identifier")
    message: str = Field(..., min_length=1, max_length=4096)
    include_memory: bool = Field(True, description="Whether to include memory context")
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0)
    model: Optional[str] = None
    stream: bool = Field(False, description="Enable response streaming")
    
    @validator("message")
    def validate_message(cls, v):
        """Validate message content"""
        return validate_content(v)

class ChatResponse(BaseModel):
    """Chat response model"""
    reply: str
    usage: Dict[str, int]
    memory_events: Optional[List[str]] = None
    thread_id: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    persona_id: str
    request_id: str

class PersonaSwitchRequest(BaseModel):
    """Persona switch request model"""
    from_persona_id: str
    to_persona_id: str
    thread_id: str
    retain_context: bool = True

@asynccontextmanager
async def chat_session(
    user: User,
    thread_id: str,
    persona_id: str,
    request_id: str,
    memory: MemoryEngine
):
    """Manage chat session context"""
    try:
        # Acquire session lock
        async with memory.get_session_lock(thread_id):
            yield
    except Exception as e:
        logger.error("Session error", 
            user_id=user.id,
            thread_id=thread_id,
            persona_id=persona_id,
            request_id=request_id,
            error=str(e)
        )
        raise

@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    req: Request,
    background_tasks: BackgroundTasks,
    provider: Provider = Depends(get_provider),
    persona: Persona = Depends(get_persona),
    memory: MemoryEngine = Depends(get_memory),
    user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    cache = Depends(get_cache),
    metrics = Depends(get_metrics)
):
    """Process chat request and generate response"""
    
    request_id = req.state.request_id
    
    # Check rate limits
    await rate_limiter.check_limit(user.id, "chat")
    
    async with chat_session(user, request.thread_id, request.persona_id, request_id, memory):
        try:
            with CHAT_LATENCY.labels(user.id, request.persona_id).time():
                # Build context with memory
                context = await memory.build_context(
                    user.id,
                    request.thread_id,
                    request.persona_id,
                    request.message,
                    include_memory=request.include_memory
                )
                
                # Check cache
                cache_key = f"chat:{user.id}:{request.thread_id}:{hash(request.message)}"
                if cached := await cache.get(cache_key):
                    CHAT_REQUESTS.labels(user.id, request.persona_id, "cache_hit").inc()
                    return ChatResponse(**cached)
                
                # Generate response
                response = await provider.complete(
                    system=persona.build_system(),
                    messages=context["messages"],
                    model=request.model or persona.defaults["model"],
                    temperature=request.temperature or persona.defaults["temperature"],
                    max_tokens=persona.safety_bounds["max_tokens"],
                    stream=request.stream
                )
                
                if request.stream:
                    return StreamingResponse(
                        stream_response(response, user, request, memory, background_tasks),
                        media_type="text/event-stream"
                    )
                
                # Process memories in background
                background_tasks.add_task(
                    process_memories,
                    user,
                    request,
                    response,
                    memory
                )
                
                # Store conversation
                await memory.append_turn(
                    user.id,
                    request.thread_id,
                    request.persona_id,
                    request.message,
                    response["text"]
                )
                
                # Cache response
                chat_response = ChatResponse(
                    reply=response["text"],
                    usage=response["usage"],
                    thread_id=request.thread_id,
                    persona_id=request.persona_id,
                    request_id=request_id
                )
                await cache.set(cache_key, chat_response.dict(), expire=300)
                
                CHAT_REQUESTS.labels(user.id, request.persona_id, "success").inc()
                return chat_response
                
        except Exception as e:
            CHAT_REQUESTS.labels(user.id, request.persona_id, "error").inc()
            logger.error("Chat failed",
                user_id=user.id,
                thread_id=request.thread_id,
                persona_id=request.persona_id,
                request_id=request_id,
                error=str(e)
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Chat request failed",
                    "detail": str(e),
                    "request_id": request_id
                }
            )

@router.post("/switch-persona", response_model=Dict)
async def switch_persona(
    request: PersonaSwitchRequest,
    req: Request,
    memory: MemoryEngine = Depends(get_memory),
    user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """Switch conversation between personas with context retention"""
    
    request_id = req.state.request_id
    
    await rate_limiter.check_limit(user.id, "persona_switch")
    
    try:
        # Get current context
        context = await memory.build_context(
            user.id,
            request.thread_id,
            request.from_persona_id,
            include_memory=request.retain_context
        )
        
        if request.retain_context:
            # Transfer relevant memories
            transferred = await memory.transfer_context(
                user.id,
                request.from_persona_id,
                request.to_persona_id,
                context["messages"][-1]["content"] if context["messages"] else ""
            )
            
            # Build new context
            new_context = await memory.build_context(
                user.id,
                request.thread_id,
                request.to_persona_id,
                include_memory=True
            )
            
            return {
                "status": "success",
                "transferred_memories": len(transferred),
                "new_context": new_context,
                "request_id": request_id
            }
        
        return {
            "status": "success",
            "transferred_memories": 0,
            "new_context": {
                "messages": [],
                "memory": []
            },
            "request_id": request_id
        }
        
    except Exception as e:
        logger.error("Persona switch failed",
            user_id=user.id,
            thread_id=request.thread_id,
            from_persona=request.from_persona_id,
            to_persona=request.to_persona_id,
            request_id=request_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to switch persona",
                "detail": str(e),
                "request_id": request_id
            }
        )

@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    req: Request,
    memory: MemoryEngine = Depends(get_memory),
    user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """Retrieve chat thread history"""
    
    request_id = req.state.request_id
    
    await rate_limiter.check_limit(user.id, "thread_retrieve")
    
    try:
        thread = await memory.load_session(user.id, thread_id)
        
        if not thread:
            raise HTTPException(
                status_code=404,
                detail=f"Thread {thread_id} not found"
            )
            
        return {
            "thread_id": thread_id,
            "messages": thread["messages"],
            "created_at": thread["created_at"],
            "request_id": request_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Thread retrieval failed",
            thread_id=thread_id,
            user_id=user.id,
            request_id=request_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to retrieve thread",
                "detail": str(e),
                "request_id": request_id
            }
        )

async def stream_response(
    response: AsyncGenerator,
    user: User,
    request: ChatRequest,
    memory: MemoryEngine,
    background_tasks: BackgroundTasks
) -> AsyncGenerator:
    """Stream chat response with proper memory handling"""
    full_response = []
    
    try:
        async for chunk in response:
            full_response.append(chunk["text"])
            yield f"data: {chunk['text']}\n\n"
            
        # Process memories after stream completes
        complete_response = "".join(full_response)
        background_tasks.add_task(
            process_memories,
            user,
            request,
            {"text": complete_response},
            memory
        )
        
    except Exception as e:
        logger.error("Stream failed",
            user_id=user.id,
            thread_id=request.thread_id,
            error=str(e)
        )
        yield f"error: {str(e)}\n\n"

async def process_memories(
    user: User,
    request: ChatRequest,
    response: Dict,
    memory: MemoryEngine
):
    """Process and store chat memories"""
    try:
        if request.include_memory:
            await memory.extract_and_store_memories(
                user.id,
                request.thread_id,
                request.persona_id,
                request.message + "\n" + response["text"]
            )
    except Exception as e:
        logger.error("Memory processing failed",
            user_id=user.id,
            thread_id=request.thread_id,
            error=str(e)
        )