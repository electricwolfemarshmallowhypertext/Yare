import pytest
import os
from src.personas.persona_registry import PersonaRegistry, LAUNCH_PERSONAS, WAVE_TWO_PERSONAS, WAVE_THREE_PERSONAS

# Test metadata
TEST_METADATA = {
    "created_at": "2025-11-02 19:14:52",
    "created_by": "electricwolfemarshmallowhypertext",
    "test_suite": "personas"
}

@pytest.fixture
def registry():
    """Create fresh persona registry for each test"""
    return PersonaRegistry()

def test_launch_personas_loading(registry):
    """Test loading of launch tier personas"""
    os.environ["PERSONA_RELEASE_TIER"] = "launch"
    registry = PersonaRegistry()
    
    # Verify only launch personas are loaded
    loaded_personas = registry.list_all()
    loaded_ids = {p.id for p in loaded_personas}
    
    assert all(p_id in loaded_ids for p_id in LAUNCH_PERSONAS)
    assert not any(p_id in loaded_ids for p_id in WAVE_TWO_PERSONAS)
    assert not any(p_id in loaded_ids for p_id in WAVE_THREE_PERSONAS)

def test_wave_two_personas_loading(registry):
    """Test loading of wave two tier personas"""
    os.environ["PERSONA_RELEASE_TIER"] = "wave_two"
    registry = PersonaRegistry()
    
    loaded_personas = registry.list_all()
    loaded_ids = {p.id for p in loaded_personas}
    
    # Should include launch and wave two
    assert all(p_id in loaded_ids for p_id in LAUNCH_PERSONAS)
    assert all(p_id in loaded_ids for p_id in WAVE_TWO_PERSONAS)
    assert not any(p_id in loaded_ids for p_id in WAVE_THREE_PERSONAS)

def test_wave_three_personas_loading(registry):
    """Test loading of wave three tier personas"""
    os.environ["PERSONA_RELEASE_TIER"] = "wave_three"
    registry = PersonaRegistry()
    
    loaded_personas = registry.list_all()
    loaded_ids = {p.id for p in loaded_personas}
    
    # Should include all personas
    assert all(p_id in loaded_ids for p_id in LAUNCH_PERSONAS)
    assert all(p_id in loaded_ids for p_id in WAVE_TWO_PERSONAS)
    assert all(p_id in loaded_ids for p_id in WAVE_THREE_PERSONAS)

def test_all_personas_loading(registry):
    """Test loading all personas"""
    os.environ["PERSONA_RELEASE_TIER"] = "all"
    registry = PersonaRegistry()
    
    loaded_personas = registry.list_all()
    loaded_ids = {p.id for p in loaded_personas}
    
    all_personas = set(LAUNCH_PERSONAS + WAVE_TWO_PERSONAS + WAVE_THREE_PERSONAS)
    assert loaded_ids == all_personas

def test_persona_config_validation(registry):
    """Test each persona's configuration"""
    os.environ["PERSONA_RELEASE_TIER"] = "all"
    registry = PersonaRegistry()
    
    for persona in registry.list_all():
        # Basic attributes
        assert persona.id
        assert persona.name
        assert persona.description
        assert persona.system_prompt
        
        # Defaults validation
        assert persona.defaults.model
        assert 0 <= persona.defaults.temperature <= 1
        assert persona.defaults.max_tokens > 0
        
        # Safety bounds validation
        assert persona.safety_bounds.max_tokens > 0
        assert 0 <= persona.safety_bounds.min_temperature <= persona.safety_bounds.max_temperature <= 1
        assert persona.safety_bounds.max_context_length > 0

def test_persona_search(registry):
    """Test persona search functionality"""
    os.environ["PERSONA_RELEASE_TIER"] = "all"
    registry = PersonaRegistry()
    
    # Search by name
    via_results = registry.search("Via")
    assert any(p.id == "via" for p in via_results)
    
    # Search by description
    helper_results = registry.search("help")
    assert len(helper_results) > 0

def test_persona_system_prompt(registry):
    """Test system prompt generation"""
    persona = registry.get("via")
    system_prompt = persona.build_system()
    
    assert persona.name in system_prompt
    assert persona.description in system_prompt
    assert persona.system_prompt in system_prompt
    assert "Remember:" in system_prompt

def test_persona_introduction(registry):
    """Test introduction generation"""
    persona = registry.get("via")
    intro = persona.build_introduction()
    
    assert persona.name in intro
    assert persona.description in intro
    assert intro.startswith("Hello!")

def test_tier_transition_handling(registry):
    """Test handling of tier transitions"""
    # Start with launch tier
    os.environ["PERSONA_RELEASE_TIER"] = "launch"
    registry = PersonaRegistry()
    launch_count = len(registry.list_all())
    
    # Transition to wave two
    os.environ["PERSONA_RELEASE_TIER"] = "wave_two"
    registry = PersonaRegistry()
    wave_two_count = len(registry.list_all())
    assert wave_two_count > launch_count
    
    # Transition to wave three
    os.environ["PERSONA_RELEASE_TIER"] = "wave_three"
    registry = PersonaRegistry()
    wave_three_count = len(registry.list_all())
    assert wave_three_count > wave_two_count

def test_invalid_persona_access(registry):
    """Test access to invalid or unauthorized personas"""
    os.environ["PERSONA_RELEASE_TIER"] = "launch"
    registry = PersonaRegistry()
    
    # Try to access wave two persona in launch tier
    with pytest.raises(KeyError):
        registry.get("mr_plot")  # Wave two persona
        
    # Try to access non-existent persona
    with pytest.raises(KeyError):
        registry.get("invalid_persona")

def test_metadata_consistency(registry):
    """Test persona metadata consistency"""
    for persona in registry.list_all():
        assert persona.created_at == TEST_METADATA["created_at"]
        assert persona.created_by == TEST_METADATA["created_by"]