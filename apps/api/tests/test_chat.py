import pytest
from fastapi.testclient import TestClient
from datetime import datetime

# Test metadata
TEST_METADATA = {
    "created_at": "2025-11-02 18:14:02",
    "created_by": "electricwolfemarshmallowhypertext",
    "test_suite": "chat_endpoints"
}

def test_chat_requires_auth(test_client: TestClient):
    """Test that chat endpoint requires authentication"""
    response = test_client.post("/chat", json={
        "thread_id": "test_thread",
        "persona_id": "via",
        "message": "Test message"
    })
    assert response.status_code == 401

def test_chat_validates_request(test_client: TestClient, auth_headers):
    """Test chat endpoint request validation"""
    # Missing required fields
    response = test_client.post("/chat", 
        headers=auth_headers,
        json={}
    )
    assert response.status_code == 422
    
    # Invalid persona ID
    response = test_client.post("/chat",
        headers=auth_headers,
        json={
            "thread_id": "test_thread",
            "persona_id": "invalid",
            "message": "Test message"
        }
    )
    assert response.status_code == 404

def test_chat_successful_response(
    test_client: TestClient,
    auth_headers,
    mock_provider,
    memory_engine
):
    """Test successful chat response"""
    message = "Test message"
    response = test_client.post("/chat",
        headers=auth_headers,
        json={
            "thread_id": f"thread_{datetime.now().timestamp()}",
            "persona_id": "via",
            "message": message,
            "include_memory": True
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "reply" in data
    assert "usage" in data
    assert "memory_events" in data
    
    # Verify usage stats
    assert "input_tokens" in data["usage"]
    assert "output_tokens" in data["usage"]
    
    # Verify headers
    assert "X-Request-ID" in response.headers
    assert "X-Response-Time" in response.headers

def test_chat_rate_limiting(
    test_client: TestClient,
    auth_headers,
    redis_client
):
    """Test chat endpoint rate limiting"""
    # Clear any existing rate limit data
    redis_client.flushdb()
    
    # Make requests up to limit
    for i in range(50):  # Free tier limit
        response = test_client.post("/chat",
            headers=auth_headers,
            json={
                "thread_id": f"thread_{datetime.now().timestamp()}",
                "persona_id": "via",
                "message": f"Test message {i}"
            }
        )
        assert response.status_code == 200
        
    # Verify rate limit headers
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers
    
    # Verify rate limit exceeded
    response = test_client.post("/chat",
        headers=auth_headers,
        json={
            "thread_id": f"thread_{datetime.now().timestamp()}",
            "persona_id": "via",
            "message": "Rate limit test"
        }
    )
    assert response.status_code == 429

def test_chat_memory_integration(
    test_client: TestClient,
    auth_headers,
    memory_engine
):
    """Test chat memory integration"""
    thread_id = f"thread_{datetime.now().timestamp()}"
    
    # First message
    response1 = test_client.post("/chat",
        headers=auth_headers,
        json={
            "thread_id": thread_id,
            "persona_id": "via",
            "message": "My name is Test User"
        }
    )
    assert response1.status_code == 200
    
    # Second message should have memory context
    response2 = test_client.post("/chat",
        headers=auth_headers,
        json={
            "thread_id": thread_id,
            "persona_id": "via",
            "message": "What's my name?"
        }
    )
    assert response2.status_code == 200
    data = response2.json()
    
    # Verify memory events
    assert data["memory_events"] is not None
    assert len(data["memory_events"]) > 0

def test_chat_persona_config(
    test_client: TestClient,
    auth_headers,
    personas
):
    """Test chat respects persona configuration"""
    persona = personas.get("via")
    
    response = test_client.post("/chat",
        headers=auth_headers,
        json={
            "thread_id": f"thread_{datetime.now().timestamp()}",
            "persona_id": "via",
            "message": "Test message",
            "temperature": 0.8  # Override default
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response aligns with persona config
    assert len(data["reply"]) <= persona.safety_bounds.max_tokens