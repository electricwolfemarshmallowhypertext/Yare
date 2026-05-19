import pytest
from typing import Dict
from src.providers.base import Provider
from src.providers.anthropic import AnthropicProvider

# Test metadata
TEST_METADATA = {
    "created_at": "2025-11-02 18:22:27",
    "created_by": "electricwolfemarshmallowhypertext",
    "test_suite": "providers"
}

class MockProvider(Provider):
    """Mock provider for testing"""
    name = "mock"
    
    async def complete(
        self,
        system: str,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int
    ) -> Dict:
        return {
            "text": "Mock response",
            "usage": {
                "input_tokens": len(str(messages)),
                "output_tokens": 12,
                "provider": self.name
            }
        }

@pytest.fixture
def mock_provider():
    """Create mock provider instance"""
    return MockProvider()

@pytest.fixture
def anthropic_provider():
    """Create Anthropic provider with test key"""
    return AnthropicProvider(api_key="test_key")

def test_provider_base_class():
    """Test Provider base class"""
    class TestProvider(Provider):
        name = "test"
    
    provider = TestProvider()
    assert provider.name == "test"
    
    with pytest.raises(NotImplementedError):
        await provider.complete("", [], "", 0.0, 100)

async def test_mock_provider_complete(mock_provider):
    """Test mock provider completion"""
    response = await mock_provider.complete(
        system="Test system",
        messages=[{"role": "user", "content": "Hello"}],
        model="mock-model",
        temperature=0.7,
        max_tokens=100
    )
    
    assert "text" in response
    assert "usage" in response
    assert response["usage"]["provider"] == "mock"

async def test_anthropic_provider_validation(anthropic_provider):
    """Test Anthropic provider input validation"""
    with pytest.raises(ValueError):
        await anthropic_provider.complete(
            system="Test",
            messages=[],  # Empty messages
            model="claude-2",
            temperature=0.7,
            max_tokens=100
        )
        
    with pytest.raises(ValueError):
        await anthropic_provider.complete(
            system="Test",
            messages=[{"role": "user", "content": "Hello"}],
            model="invalid-model",  # Invalid model
            temperature=0.7,
            max_tokens=100
        )
        
    with pytest.raises(ValueError):
        await anthropic_provider.complete(
            system="Test",
            messages=[{"role": "user", "content": "Hello"}],
            model="claude-2",
            temperature=2.0,  # Invalid temperature
            max_tokens=100
        )

def test_provider_message_formatting(mock_provider):
    """Test message formatting"""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "How are you?"}
    ]
    
    formatted = mock_provider.format_messages(messages)
    assert isinstance(formatted, str)
    assert "Hello" in formatted
    assert "Hi" in formatted
    assert "How are you?" in formatted

def test_provider_token_counting(mock_provider):
    """Test token counting methods"""
    text = "This is a test message with multiple tokens."
    count = mock_provider.count_tokens(text)
    assert isinstance(count, int)
    assert count > 0

async def test_provider_error_handling(mock_provider):
    """Test provider error handling"""
    class ErrorProvider(MockProvider):
        async def complete(self, *args, **kwargs):
            raise Exception("API Error")
    
    provider = ErrorProvider()
    
    with pytest.raises(Exception) as exc:
        await provider.complete(
            system="Test",
            messages=[{"role": "user", "content": "Hello"}],
            model="test-model",
            temperature=0.7,
            max_tokens=100
        )
    assert "API Error" in str(exc.value)

def test_provider_safety_bounds():
    """Test provider safety bounds"""
    class SafeProvider(MockProvider):
        max_system_length = 100
        max_message_length = 50
        
    provider = SafeProvider()
    
    # Test system length validation
    with pytest.raises(ValueError):
        long_system = "x" * 101
        await provider.complete(
            system=long_system,
            messages=[{"role": "user", "content": "Hello"}],
            model="test-model",
            temperature=0.7,
            max_tokens=100
        )
        
    # Test message length validation
    with pytest.raises(ValueError):
        long_message = "x" * 51
        await provider.complete(
            system="Test",
            messages=[{"role": "user", "content": long_message}],
            model="test-model",
            temperature=0.7,
            max_tokens=100
        )

def test_provider_metadata():
    """Test provider metadata"""
    provider = MockProvider()
    
    assert hasattr(provider, "_created_at")
    assert provider._created_at == TEST_METADATA["created_at"]
    assert hasattr(provider, "_created_by")
    assert provider._created_by == TEST_METADATA["created_by"]