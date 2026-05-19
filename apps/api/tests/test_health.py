import pytest
from fastapi.testclient import TestClient
import redis
import time
from firebase_admin import auth
from src.routers.health import router

# Test metadata
TEST_METADATA = {
    "created_at": "2025-11-02 18:23:10",
    "created_by": "electricwolfemarshmallowhypertext",
    "test_suite": "health_routes"
}

@pytest.fixture
def test_app(redis_client, mock_firebase):
    """Create test FastAPI app with health routes"""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return app

@pytest.fixture
def test_client(test_app):
    """Create test client"""
    return TestClient(test_app)

@pytest.fixture
def redis_client():
    """Create Redis test client"""
    client = redis.from_url("redis://localhost:6379/1")
    client.flushdb()  # Clear test database
    yield client
    client.flushdb()  # Cleanup

def test_health_check_success(test_client):
    """Test successful health check"""
    response = test_client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "build" in data
    assert "components" in data
    assert "environment" in data
    
    # Verify build info
    assert data["build"]["timestamp"] == TEST_METADATA["created_at"]
    assert data["build"]["author"] == TEST_METADATA["created_by"]
    assert data["build"]["version"] == "1.0.0"
    
    # Verify components
    components = data["components"]
    assert "redis" in components
    assert "firebase" in components
    assert "personas" in components
    assert "providers" in components

def test_redis_health_check(test_client, redis_client):
    """Test Redis-specific health check"""
    response = test_client.get("/health/redis")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert "latency_ms" in data
    
    # Test Redis failure scenario
    redis_client.connection_pool.disconnect()
    response = test_client.get("/health/redis")
    assert response.status_code == 200
    assert data["status"] == "healthy"
    
    # Reconnect for cleanup
    redis_client.ping()

def test_firebase_health_check(test_client, mock_firebase):
    """Test Firebase-specific health check"""
    response = test_client.get("/health/firebase")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] in ["healthy", "configured"]
    
    # Test with non-existent user
    try:
        auth.delete_user("test_health_user")
    except:
        pass
    
    response = test_client.get("/health/firebase")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_health_check_response_time(test_client):
    """Test health check response time"""
    start_time = time.time()
    response = test_client.get("/health")
    end_time = time.time()
    
    assert response.status_code == 200
    assert end_time - start_time < 1.0  # Should respond within 1 second

def test_health_check_components(test_client):
    """Test detailed component status"""
    response = test_client.get("/health")
    assert response.status_code == 200
    
    components = response.json()["components"]
    
    # Redis checks
    assert "status" in components["redis"]
    assert "latency_ms" in components["redis"]
    
    # Firebase checks
    assert "status" in components["firebase"]
    
    # Personas checks
    assert "count" in components["personas"]
    assert "load_info" in components["personas"]
    
    # Providers checks
    assert "available" in components["providers"]
    assert isinstance(components["providers"]["available"], list)

def test_health_check_headers(test_client):
    """Test health check response headers"""
    response = test_client.get("/health")
    assert response.status_code == 200
    
    headers = response.headers
    assert "X-Request-ID" in headers
    assert "X-Response-Time" in headers
    assert "Content-Type" == "application/json"

def test_health_check_caching(test_client):
    """Test health check caching behavior"""
    # First request
    response1 = test_client.get("/health")
    assert response1.status_code == 200
    etag1 = response1.headers.get("ETag")
    
    # Second request with ETag
    headers = {"If-None-Match": etag1} if etag1 else {}
    response2 = test_client.get("/health", headers=headers)
    
    # Should always return fresh data
    assert response2.status_code == 200

def test_component_isolation(test_client, redis_client):
    """Test component failure isolation"""
    # Break Redis connection
    redis_client.connection_pool.disconnect()
    
    # Health check should still work
    response = test_client.get("/health")
    assert response.status_code == 200
    
    # Redis component should show unhealthy
    components = response.json()["components"]
    assert components["redis"]["status"] == "unhealthy"
    
    # Other components should still be checked
    assert "status" in components["firebase"]
    assert "count" in components["personas"]
    
    # Reconnect for cleanup
    redis_client.ping()