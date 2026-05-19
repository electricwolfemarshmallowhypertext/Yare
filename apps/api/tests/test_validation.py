"""
Memory Validation Tests (aligned with V2 validation/models)
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.memory.validation import (
    MemoryEvent,
    MemoryQuery,
    MemoryTransfer,
    MemoryType,
    MemoryState,
    validate_memory_input,
    validate_query_input,
    validate_transfer_input,
    sanitize_memory_output
)


@pytest.fixture
def test_memory_data():
    """Create test memory data"""
    return {
        "text": "Test memory content",
        "thread_id": "thread123",
        "user_id": "user123",
        "persona_id": "persona123",
        "type": MemoryType.FACT,
        "salience": 0.8,
        "created_at": datetime.utcnow(),
        "embedding": [0.1] * 1024,
        "metadata": {
            "source": "test",
            "confidence": 0.9,
            "tags": ["test", "validation"],
            "state": MemoryState.ACTIVE
        }
    }


def test_memory_event_validation(test_memory_data):
    event = MemoryEvent(**test_memory_data)
    assert event.id  # auto-generated
    assert event.text == test_memory_data["text"]
    assert event.type == MemoryType.FACT
    assert event.metadata.state == MemoryState.ACTIVE

    with pytest.raises(ValidationError):
        MemoryEvent(**{**test_memory_data, "text": ""})

    with pytest.raises(ValidationError):
        MemoryEvent(**{**test_memory_data, "salience": 1.5})

    with pytest.raises(ValidationError):
        MemoryEvent(**{**test_memory_data, "embedding": [0.1] * 100})

    with pytest.raises(ValidationError):
        MemoryEvent(**{**test_memory_data, "metadata": {"confidence": 1.5}})


def test_memory_query_validation():
    valid_query = {
        "user_id": "user123",
        "thread_id": "thread123",
        "persona_id": "persona123",
        "query": "Test query",
        "include_memory": True,
        "top_k": 5
    }

    query = MemoryQuery(**valid_query)
    assert query.query == "Test query"
    assert query.top_k == 5

    with pytest.raises(ValidationError):
        MemoryQuery(**{**valid_query, "query": ""})

    with pytest.raises(ValidationError):
        MemoryQuery(**{**valid_query, "top_k": 0})

    with pytest.raises(ValidationError):
        MemoryQuery(query="Test")


def test_memory_transfer_validation():
    valid_transfer = {
        "user_id": "user123",
        "from_persona": "persona1",
        "to_persona": "persona2",
        "query": "Test transfer"
    }

    transfer = MemoryTransfer(**valid_transfer)
    assert transfer.query == "Test transfer"

    with pytest.raises(ValidationError):
        MemoryTransfer(**{**valid_transfer, "to_persona": valid_transfer["from_persona"]})

    with pytest.raises(ValidationError):
        MemoryTransfer(**{**valid_transfer, "from_persona": ""})


def test_validate_memory_input(test_memory_data):
    result = validate_memory_input(
        text=test_memory_data["text"],
        thread_id=test_memory_data["thread_id"],
        user_id=test_memory_data["user_id"],
        persona_id=test_memory_data["persona_id"],
        type=MemoryType.FACT,
        salience=0.8
    )
    assert result["text"] == test_memory_data["text"]
    assert result["type"] == MemoryType.FACT

    with pytest.raises(ValidationError):
        MemoryEvent(
            text="",
            thread_id="thread123",
            user_id="user123",
            persona_id="persona123",
            type=MemoryType.FACT,
            salience=0.5,
            created_at=datetime.utcnow(),
        )


def test_validate_query_input():
    result = validate_query_input(
        user_id="user123",
        thread_id="thread123",
        persona_id="persona123",
        query="Test query",
        top_k=5
    )
    assert result["query"] == "Test query"
    assert result["top_k"] == 5

    with pytest.raises(ValidationError):
        MemoryQuery(
            user_id="user123",
            thread_id="thread123",
            persona_id="persona123",
            query="",
            top_k=5
        )


def test_validate_transfer_input():
    result = validate_transfer_input(
        user_id="user123",
        from_persona="persona1",
        to_persona="persona2",
        query="Test transfer"
    )
    assert result["query"] == "Test transfer"

    with pytest.raises(ValidationError):
        MemoryTransfer(
            user_id="user123",
            from_persona="persona1",
            to_persona="persona1",
            query="Test"
        )


def test_sanitize_memory_output(test_memory_data):
    memory = MemoryEvent(**test_memory_data).dict()

    sanitized = sanitize_memory_output(memory)
    assert "text" in sanitized
    assert "embedding" not in sanitized
    assert "_internal" not in sanitized.get("metadata", {})

    sanitized2 = sanitize_memory_output(memory, include_embedding=True)
    assert "embedding" in sanitized2
    assert len(sanitized2["embedding"]) == 1024

    memory["metadata"]["_internal"] = "secret"
    sanitized3 = sanitize_memory_output(memory)
    assert "_internal" not in sanitized3.get("metadata", {})


def test_memory_type_validation():
    assert MemoryType.FACT == "fact"
    assert MemoryType.INTERACTION == "interaction"
    assert MemoryType("fact") == MemoryType.FACT
    with pytest.raises(ValueError):
        MemoryType("invalid")


def test_memory_state_validation():
    assert MemoryState.ACTIVE == "active"
    assert MemoryState.ARCHIVED == "archived"
    assert MemoryState("active") == MemoryState.ACTIVE
    with pytest.raises(ValueError):
        MemoryState("invalid")


def test_large_content_validation(test_memory_data):
    large_text = "x" * 5000
    with pytest.raises(ValidationError):
        MemoryEvent(**{**test_memory_data, "text": large_text})

    large_metadata = {"data": "x" * 10000}
    with pytest.raises(ValidationError):
        MemoryEvent(**{**test_memory_data, "metadata": large_metadata})