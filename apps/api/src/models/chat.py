from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ChatRequest(BaseModel):
    thread_id: str
    persona_id: str
    message: str
    temperature: Optional[float] = Field(default=None, ge=0, le=1)
    model: Optional[str] = None
    include_memory: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "th_abc123",
                "persona_id": "via",
                "message": "Draft a 3-step onboarding checklist.",
                "temperature": 0.3,
                "model": "anthropic:haiku-4.5",
                "include_memory": True
            }
        }
        
        schema_extra = {
            "created_at": "2025-11-02 18:05:49",
            "created_by": "electricwolfemarshmallowhypertext"
        }

class UsageStats(BaseModel):
    input_tokens: int
    output_tokens: int
    provider: Optional[str] = None

class MemoryEvent(BaseModel):
    type: str
    status: str
    id: str

class ChatResponse(BaseModel):
    reply: str
    usage: UsageStats
    memory_events: Optional[List[MemoryEvent]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "reply": "1. Create account and verify email\n2. Configure API keys\n3. Set up billing information",
                "usage": {
                    "input_tokens": 210,
                    "output_tokens": 180,
                    "provider": "anthropic:haiku-4.5"
                },
                "memory_events": [
                    {"type": "fact", "status": "stored", "id": "mem_xyz789"}
                ]
            }
        }