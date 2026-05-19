import pytest
import redis
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, auth
from fastapi.testclient import TestClient

# Test metadata
TEST_METADATA = {
    "created_at": "2025-11-02 18:50:08",
    "created_by": "electricwolfemarshmallowhypertext",
    "test_suite": "fixtures"
}

@pytest.fixture(scope="session")
def redis_client():
    """Create Redis test client"""
    client = redis.from_url("redis://localhost:6379/1")
    client.flushdb()  # Clear test database
    yield client
    client.flushdb()  # Cleanup after tests

@pytest.fixture(scope="session")
def mock_firebase():
    """Initialize Firebase with test credentials"""
    try:
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(
            os.getenv("FIREBASE_TEST_CREDENTIALS", "test-credentials.json")
        )
        firebase_admin.initialize_app(cred)
    return firebase_admin

@pytest.fixture
async def test_user(mock_firebase):
    """Create test user in Firebase"""
    user = await auth.create_user(
        email="test@example.com",
        password="testpassword123",
        display_name="Test User"
    )
    
    # Set custom claims
    await auth.set_custom_user_claims(
        user.uid,
        {
            "premium": True,
            "test_user": True
        }
    )
    
    yield user
    
    # Cleanup
    await auth.delete_user(user.uid)

@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers"""
    token = auth.create_custom_token(test_user.uid)
    return {
        "Authorization": f"Bearer {token}",
        "X-User-ID": test_user.uid,
        "X-Request-ID": f"test-{datetime.utcnow().timestamp()}"
    }

@pytest.fixture
def memory_engine(redis_client):
    """Create memory engine instance"""
    from src.memory import MemoryEngine
    return MemoryEngine(
        redis_url="redis://localhost:6379/1",
        redis_ttl=60,
        timestamp=TEST_METADATA["created_at"],
        user=TEST_METADATA["created_by"]
    )

@pytest.fixture
def provider():
    """Create test provider instance"""
    from src.providers import AnthropicProvider
    return AnthropicProvider(api_key="test-key")

@pytest.fixture
def personas():
    """Create test persona registry"""
    from src.personas import PersonaRegistry
    return PersonaRegistry()

@pytest.fixture
def test_app(redis_client, mock_firebase):
    """Create test FastAPI application"""
    from src.main import create_app
    app = create_app()
    return app

@pytest.fixture
def test_client(test_app):
    """Create test client"""
    return TestClient(test_app)

@pytest.fixture
async def test_thread(memory_engine, test_user):
    """Create test conversation thread"""
    thread_id = f"test-thread-{datetime.utcnow().timestamp()}"
    
    # Initialize thread
    await memory_engine.append_turn(
        test_user.uid,
        thread_id,
        "via",
        "Test message",
        "Test reply"
    )
    
    yield thread_id
    
    # Cleanup
    await memory_engine.clear_memories(test_user.uid, thread_id)

@pytest.fixture
def mock_provider_response():
    """Create mock provider response"""
    return {
        "text": "Test response",
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "provider": "test"
        }
    }

@pytest.fixture
def mock_memory_event():
    """Create mock memory event"""
    return {
        "text": "Test memory",
        "type": "fact",
        "salience": 0.8,
        "created_at": TEST_METADATA["created_at"]
    }

@pytest.fixture(autouse=True)
def env_setup():
    """Set up test environment variables"""
    os.environ["ENVIRONMENT"] = "test"
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"
    os.environ["LOG_LEVEL"] = "DEBUG"
    yield
    os.environ.pop("ENVIRONMENT", None)