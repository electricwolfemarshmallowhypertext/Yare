import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.middleware.rate_limit import RateLimitMiddleware
import redis
import time

# Test metadata
TEST_METADATA = {
    "created_at": "2025-11-02 18:21:05",
    "created_by": "electricwolfemarshmallowhypertext",
    "test_suite": "rate_limit_middleware"
}

@pytest.fixture
def test_app():
    """Create test FastAPI app with rate limit middleware"""
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        redis_url="redis://localhost:6379/1",
        window_seconds=60,
        default_limit=10,
        created_at=TEST_METADATA["created_at"],
        created_by=TEST_METADATA["created_by"]
    )
    
    @app.get("/test")
    async def test_route():
        return {"status": "success"}
        
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}
    
    return app

@pytest.fixture
def test_client(test_app):
    """Create test client with rate limit middleware"""
    return TestClient(test_app)

@pytest.fixture
def redis_client():
    """Create Redis test client"""
    client = redis.from_url("redis://localhost:6379/1")
    client.flushdb()  # Clear test database
    return client

def test_rate_limit_headers(test_client):
    """Test rate limit headers are present"""
    response = test_client.get("/test")
    assert response.status_code == 200
    
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers

def test_rate_limit_counting(test_client, redis_client):
    """Test rate limit counter increments"""
    # Make several requests
    for i in range(5):
        response = test_client.get("/test")
        assert response.status_code == 200
        
        limit = int(response.headers["X-RateLimit-Limit"])
        remaining = int(response.headers["X-RateLimit-Remaining"])
        
        assert limit == 10  # Default limit
        assert remaining == 10 - (i + 1)

def test_rate_limit_exceeded(test_client, redis_client):
    """Test rate limit enforcement"""
    # Exceed rate limit
    for i in range(10):
        response = test_client.get("/test")
        assert response.status_code == 200
    
    # Next request should fail
    response = test_client.get("/test")
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["detail"]["error"]

def test_rate_limit_by_user(test_client, redis_client):
    """Test rate limits are user-specific"""
    # User 1 requests
    for _ in range(5):
        response = test_client.get(
            "/test",
            headers={"X-User-ID": "user1"}
        )
        assert response.status_code == 200
    
    # User 2 should have full quota
    response = test_client.get(
        "/test",
        headers={"X-User-ID": "user2"}
    )
    assert response.status_code == 200
    assert int(response.headers["X-RateLimit-Remaining"]) == 9

def test_health_check_bypass(test_client):
    """Test health check endpoint bypasses rate limit"""
    # Make many requests to health check
    for _ in range(20):
        response = test_client.get("/health")
        assert response.status_code == 200

def test_rate_limit_window_reset(test_client, redis_client):
    """Test rate limit window reset"""
    # Make some requests
    for _ in range(5):
        response = test_client.get("/test")
        assert response.status_code == 200
    
    # Simulate window expiration
    time.sleep(1)  # Ensure new timestamp
    redis_client.flushdb()
    
    # Should have fresh quota
    response = test_client.get("/test")
    assert response.status_code == 200
    assert int(response.headers["X-RateLimit-Remaining"]) == 9

def test_rate_limit_tiers(test_client):
    """Test different rate limits by user tier"""
    # Free tier
    response = test_client.get(
        "/test",
        headers={"X-User-Tier": "free"}
    )
    assert response.status_code == 200
    assert int(response.headers["X-RateLimit-Limit"]) == 10
    
    # Pro tier
    response = test_client.get(
        "/test",
        headers={"X-User-Tier": "pro"}
    )
    assert response.status_code == 200
    assert int(response.headers["X-RateLimit-Limit"]) == 100
    
    # Premium tier
    response = test_client.get(
        "/test",
        headers={"X-User-Tier": "premium"}
    )
    assert response.status_code == 200
    assert int(response.headers["X-RateLimit-Limit"]) == 1000

def test_rate_limit_error_response(test_client, redis_client):
    """Test rate limit error response format"""
    # Exceed limit
    for _ in range(11):
        response = test_client.get("/test")
    
    assert response.status_code == 429
    error = response.json()["detail"]
    
    assert "error" in error
    assert "limit" in error
    assert "reset_in_seconds" in error
    assert "tier" in error