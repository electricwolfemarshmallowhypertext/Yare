import pytest
import redis
from fastapi.testclient import TestClient
from datetime import datetime
from src.main import app
from src.providers.anthropic import AnthropicProvider
from src.memory.memory_engine import MemoryEngine
from src.personas.registry import PersonaRegistry

# Test metadata
TEST_METADATA = {
    "created_at": "2025-11-02 18:24:38",
    "created_by": "electricwolfemarshmallowhypertext",
    "test_suite": "integration"
}

@pytest.fixture
def test_client():
    """Create test client"""
    return TestClient(app)

@pytest.fixture
def redis_client():
    """Create Redis test client"""
    client = redis.from_url("redis://localhost:6379/1")
    client.flushdb()  # Clear test database
    yield client
    client.flushdb()  # Cleanup

@pytest.fixture
def memory_engine(redis_client):
    """Create memory engine instance"""
    return MemoryEngine(
        redis_url="redis://localhost:6379/1",
        redis_ttl=60,
        timestamp=TEST_METADATA["created_at"],
        user=TEST_METADATA["created_by"]
    )

@pytest.fixture
def provider():
    """Create provider instance"""
    return AnthropicProvider(api_key="test_key")

@pytest.fixture
def personas():
    """Create persona registry"""
    return PersonaRegistry()

def test_provider_memory_integration(provider, memory_engine):
    """Test integration between provider and memory"""
    thread_id = f"thread_{datetime.now().timestamp()}"
    user_id = "test_user"
    
    # Store initial memory
    memory_engine.append_turn(
        user_id,
        thread_id,
        "via",
        "My name is Alice",
        "Nice to meet you, Alice!"
    )
    
    # Build context with memory
    context = memory_engine.build_context(
        user_id,
        thread_id,
        include_memory=True
    )
    
    # Generate response with context
    response = provider.complete(
        system="You are a helpful assistant",
        messages=context["messages"] + [
            {"role": "user", "content": "What's my name?"}
        ],
        model="claude-2",
        temperature=0.7,
        max_tokens=100
    )
    
    assert "Alice" in response["text"]

def test_persona_provider_integration(provider, personas):
    """Test integration between personas and provider"""
    persona = personas.get("via")
    
    # Generate response using persona config
    response = provider.complete(
        system=persona.build_system(),
        messages=[
            {"role": "user", "content": "Who are you?"}
        ],
        model=persona.defaults["model"],
        temperature=persona.defaults["temperature"],
        max_tokens=persona.safety_bounds["max_tokens"]
    )
    
    assert "via" in response["text"].lower()
    assert len(response["text"]) <= persona.safety_bounds["max_tokens"]

def test_memory_persona_integration(memory_engine, personas):
    """Test integration between memory and personas"""
    thread_id = f"thread_{datetime.now().timestamp()}"
    user_id = "test_user"
    persona = personas.get("via")
    
    # Store memory with persona context
    memory_engine.append_turn(
        user_id,
        thread_id,
        persona.id,
        "Tell me about yourself",
        persona.build_introduction()
    )
    
    # Retrieve context
    context = memory_engine.build_context(
        user_id,
        thread_id,
        persona,
        include_memory=True
    )
    
    assert any("via" in msg["content"].lower() 
              for msg in context["messages"])

def test_full_chat_integration(
    test_client,
    redis_client,
    provider,
    memory_engine,
    personas
):
    """Test full integration of all components"""
    headers = {
        "Authorization": "Bearer test_token",
        "X-User-ID": "test_user"
    }
    
    thread_id = f"thread_{datetime.now().timestamp()}"
    
    # First message
    response1 = test_client.post(
        "/chat",
        headers=headers,
        json={
            "thread_id": thread_id,
            "persona_id": "via",
            "message": "Remember that I like pizza",
            "include_memory": True
        }
    )
    
    assert response1.status_code == 200
    
    # Verify memory storage
    memory_key = f"mem:test_user:{thread_id}"
    assert redis_client.exists(memory_key)
    
    # Follow-up message
    response2 = test_client.post(
        "/chat",
        headers=headers,
        json={
            "thread_id": thread_id,
            "persona_id": "via",
            "message": "What food do I like?",
            "include_memory": True
        }
    )
    
    assert response2.status_code == 200
    assert "pizza" in response2.json()["reply"].lower()

def test_error_propagation(test_client, redis_client):
    """Test error handling across components"""
    headers = {
        "Authorization": "Bearer test_token",
        "X-User-ID": "test_user"
    }
    
    # Break Redis connection
    redis_client.connection_pool.disconnect()
    
    response = test_client.post(
        "/chat",
        headers=headers,
        json={
            "thread_id": "test_thread",
            "persona_id": "via",
            "message": "Test message",
            "include_memory": True
        }
    )
    
    assert response.status_code == 500
    assert "error" in response.json()
    
    # Reconnect for cleanup
    redis_client.ping()

def test_concurrent_component_access(
    test_client,
    redis_client,
    memory_engine
):
    """Test concurrent access to components"""
    import asyncio
    import httpx
    
    async def make_request(thread_id):
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            return await client.post(
                "/chat",
                headers={
                    "Authorization": "Bearer test_token",
                    "X-User-ID": "test_user"
                },
                json={
                    "thread_id": thread_id,
                    "persona_id": "via",
                    "message": "Test message",
                    "include_memory": True
                }
            )
    
    # Make concurrent requests with same thread ID
    thread_id = f"thread_{datetime.now().timestamp()}"
    responses = asyncio.run(asyncio.gather(
        *[make_request(thread_id) for _ in range(3)]
    ))
    
    # Verify all requests succeeded
    assert all(r.status_code == 200 for r in responses)
    
    # Verify memory consistency
    memory_key = f"mem:test_user:{thread_id}"
    stored_data = redis_client.get(memory_key)
    assert stored_data is not None