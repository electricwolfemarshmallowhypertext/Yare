import pytest
import json
import logging
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.middleware.logging import LoggingMiddleware

# Test metadata
TEST_METADATA = {
    "created_at": "2025-11-02 18:21:51",
    "created_by": "electricwolfemarshmallowhypertext",
    "test_suite": "logging_middleware"
}

class TestLogHandler(logging.Handler):
    """Custom log handler for testing"""
    def __init__(self):
        super().__init__()
        self.logs = []
        
    def emit(self, record):
        self.logs.append(json.loads(record.msg))
        
    def clear(self):
        self.logs = []

@pytest.fixture
def log_handler():
    """Create and configure test log handler"""
    handler = TestLogHandler()
    logger = logging.getLogger("sticky.api.test")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return handler

@pytest.fixture
def test_app(log_handler):
    """Create test FastAPI app with logging middleware"""
    app = FastAPI()
    app.add_middleware(
        LoggingMiddleware,
        logger_name="sticky.api.test",
        log_level="INFO",
        created_at=TEST_METADATA["created_at"],
        created_by=TEST_METADATA["created_by"]
    )
    
    @app.get("/test")
    async def test_route():
        return {"status": "success"}
        
    @app.get("/error")
    async def error_route():
        raise ValueError("Test error")
    
    return app

@pytest.fixture
def test_client(test_app):
    """Create test client with logging middleware"""
    return TestClient(test_app)

def test_successful_request_logging(test_client, log_handler):
    """Test logging of successful requests"""
    log_handler.clear()
    response = test_client.get("/test")
    
    assert response.status_code == 200
    assert len(log_handler.logs) == 2  # Start and complete logs
    
    start_log = log_handler.logs[0]
    complete_log = log_handler.logs[1]
    
    # Verify start log
    assert start_log["event"] == "request_start"
    assert "timestamp" in start_log
    assert "request" in start_log
    assert start_log["request"]["method"] == "GET"
    assert start_log["request"]["path"] == "/test"
    
    # Verify complete log
    assert complete_log["event"] == "request_complete"
    assert "timestamp" in complete_log
    assert "response" in complete_log
    assert complete_log["response"]["status_code"] == 200
    assert "duration_ms" in complete_log["response"]

def test_error_request_logging(test_client, log_handler):
    """Test logging of failed requests"""
    log_handler.clear()
    
    with pytest.raises(ValueError):
        test_client.get("/error")
    
    assert len(log_handler.logs) == 2  # Start and error logs
    
    start_log = log_handler.logs[0]
    error_log = log_handler.logs[1]
    
    # Verify error log
    assert error_log["event"] == "request_error"
    assert "timestamp" in error_log
    assert "error" in error_log
    assert error_log["error"]["type"] == "ValueError"
    assert error_log["error"]["message"] == "Test error"
    assert "duration_ms" in error_log["error"]

def test_request_metadata_logging(test_client, log_handler):
    """Test logging of request metadata"""
    log_handler.clear()
    
    headers = {
        "User-Agent": "TestClient",
        "X-Request-ID": "test-123",
        "X-User-ID": "test-user"
    }
    
    response = test_client.get("/test", headers=headers)
    assert response.status_code == 200
    
    request_log = log_handler.logs[0]
    assert request_log["request"]["user_agent"] == "TestClient"
    assert request_log["request"]["user_id"] == "test-user"

def test_response_timing_logging(test_client, log_handler):
    """Test logging of response timing"""
    log_handler.clear()
    response = test_client.get("/test")
    
    complete_log = log_handler.logs[1]
    assert "duration_ms" in complete_log["response"]
    assert complete_log["response"]["duration_ms"] >= 0

def test_query_params_logging(test_client, log_handler):
    """Test logging of query parameters"""
    log_handler.clear()
    response = test_client.get("/test?param1=value1&param2=value2")
    
    request_log = log_handler.logs[0]
    assert request_log["request"]["query_params"] == {
        "param1": "value1",
        "param2": "value2"
    }

def test_log_sanitization(test_client, log_handler):
    """Test sanitization of sensitive data in logs"""
    log_handler.clear()
    
    headers = {
        "Authorization": "Bearer secret-token",
        "X-API-Key": "secret-key"
    }
    
    response = test_client.get("/test", headers=headers)
    
    request_log = log_handler.logs[0]
    assert "Authorization" not in str(request_log)
    assert "secret-token" not in str(request_log)
    assert "X-API-Key" not in str(request_log)
    assert "secret-key" not in str(request_log)