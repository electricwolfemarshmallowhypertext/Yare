import pytest
from fastapi.testclient import TestClient
import redis
import time
from src.main import app

# Test metadata
TEST_METADATA = {
    "created_at": "2025-11-02 18:23:53",
    "created_by": "electricwolfemarshmallowhypertext",
    "test_suite": "end_to_end"
}

@pytest.fixture
def test_client():
    """Create test client for end-to-end tests"""
    return TestClient(app)

@pytest.fixture
def redis_client():
    """Create Redis test client"""
    client = redis.from_url("redis://localhost:6379/1")
    client.flushdb()  # Clear test database
    yield client
    client.flushdb()  # Cleanup

@pytest.fixture
def auth_headers():
    """Create test authentication headers"""
    return {
        "Authorization": "Bearer test_token",
        "X-User-ID": "test_user",
        "X-User-Tier": "premium"
    }

def test_complete_chat_flow(test_client, auth_headers, redis_client):
    """Test complete chat interaction flow"""
    # Start new conversation
    thread_id = f"thread_{time.time()}"
    
    # First message
    response1 = test_client.post(
        "/chat",
        headers=auth_headers,
        json={
            "thread_id": thread_id,
            "persona_id": "via",
            "message": "Hello, I'm starting a new conversation.",
            "include_memory": True
        }
    )
    
    assert response1.status_code == 200
    data1 = response1.json()
    assert "reply" in data1
    assert "usage" in data1
    assert "memory_events" in data1
    
    # Follow-up message
    response2 = test_client.post(
        "/chat",
        headers=auth_headers,
        json={
            "thread_id": thread_id,
            "persona_id": "via",
            "message": "What did I say in my first message?",
            "include_memory": True
        }
    )
    
    assert response2.status_code == 200
    data2 = response2.json()
    assert "conversation" in data2["reply"].lower()

def test_rate_limiting_flow(test_client, auth_headers):
    """Test rate limiting across multiple requests"""
    responses = []
    
    # Make requests up to limit
    for i in range(55):  # Premium tier limit test
        response = test_client.post(
            "/chat",
            headers=auth_headers,
            json={
                "thread_id": f"thread_{time.time()}",
                "persona_id": "via",
                "message": f"Test message {i}",
                "include_memory": False
            }
        )
        responses.append(response)
        
        if response.status_code == 429:
            break
            
        assert "X-RateLimit-Remaining" in response.headers
    
    # Verify rate limit was enforced
    assert any(r.status_code == 429 for r in responses)
    
    # Wait for rate limit window
    time.sleep(2)
    
    # Verify can make requests again
    response = test_client.post(
        "/chat",
        headers=auth_headers,
        json={
            "thread_id": f"thread_{time.time()}",
            "persona_id": "via",
            "message": "Test after rate limit",
            "include_memory": False
        }
    )
    assert response.status_code == 200

def test_error_handling_flow(test_client, auth_headers):
    """Test error handling in different scenarios"""
    # Missing required field
    response1 = test_client.post(
        "/chat",
        headers=auth_headers,
        json={
            "thread_id": "test_thread"
            # Missing message and persona_id
        }
    )
    assert response1.status_code == 422
    
    # Invalid persona
    response2 = test_client.post(
        "/chat",
        headers=auth_headers,
        json={
            "thread_id": "test_thread",
            "persona_id": "invalid_persona",
            "message": "Test message"
        }
    )
    assert response2.status_code == 404
    
    # Invalid authentication
    response3 = test_client.post(
        "/chat",
        headers={"Authorization": "Invalid"},
        json={
            "thread_id": "test_thread",
            "persona_id": "via",
            "message": "Test message"
        }
    )
    assert response3.status_code == 401

def test_memory_persistence_flow(test_client, auth_headers, redis_client):
    """Test memory persistence across multiple sessions"""
    thread_id = f"thread_{time.time()}"
    
    # First session
    response1 = test_client.post(
        "/chat",
        headers=auth_headers,
        json={
            "thread_id": thread_id,
            "persona_id": "via",
            "message": "My favorite color is blue",
            "include_memory": True
        }
    )
    assert response1.status_code == 200
    
    # Verify memory storage
    memory_key = f"mem:test_user:{thread_id}"
    assert redis_client.exists(memory_key)
    
    # Second session
    response2 = test_client.post(
        "/chat",
        headers=auth_headers,
        json={
            "thread_id": thread_id,
            "persona_id": "via",
            "message": "What's my favorite color?",
            "include_memory": True
        }
    )
    assert response2.status_code == 200
    assert "blue" in response2.json()["reply"].lower()

def test_persona_consistency_flow(test_client, auth_headers):
    """Test persona consistency across interactions"""
    thread_id = f"thread_{time.time()}"
    
    # Multiple interactions with same persona
    messages = [
        "Hello, who are you?",
        "What's your role?",
        "How do you help users?"
    ]
    
    previous_reply = None
    for message in messages:
        response = test_client.post(
            "/chat",
            headers=auth_headers,
            json={
                "thread_id": thread_id,
                "persona_id": "via",
                "message": message,
                "include_memory": True
            }
        )
        
        assert response.status_code == 200
        current_reply = response.json()["reply"]
        
        if previous_reply:
            # Verify consistent persona traits
            assert "via" in current_reply.lower()
        
        previous_reply = current_reply

def test_concurrent_requests_flow(test_client, auth_headers):
    """Test handling of concurrent requests"""
    import asyncio
    import httpx
    
    async def make_request(message):
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/chat",
                headers=auth_headers,
                json={
                    "thread_id": f"thread_{time.time()}",
                    "persona_id": "via",
                    "message": message,
                    "include_memory": False
                }
            )
            return response
    
    # Make multiple concurrent requests
    messages = [f"Concurrent message {i}" for i in range(5)]
    
    responses = asyncio.run(asyncio.gather(
        *[make_request(msg) for msg in messages]
    ))
    
    # Verify all requests succeeded
    assert all(r.status_code == 200 for r in responses)
    
    # Verify unique responses
    replies = [r.json()["reply"] for r in responses]
    assert len(set(replies)) == len(replies)