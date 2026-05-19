from typing import Dict, List, Optional
import json
import os
import logging
from pydantic import BaseModel, Field

# Module metadata
MODULE_METADATA = {
    "created_at": "2025-11-02 19:11:47",
    "created_by": "electricwolfemarshmallowhypertext",
    "version": "1.0.0"
}

# Persona tiers
LAUNCH_PERSONAS = [
    "via", "beak", "iggy", "julez", "stevie",
    "dash", "sable", "bastion", "mina", "ned"
]

WAVE_TWO_PERSONAS = [
    "mr_plot", "rex", "cordeliah", "echo", "twinly",
    "knot", "vad", "ayre", "ms_memo", "jass"
]

WAVE_THREE_PERSONAS = [
    "huey", "flos", "llana", "bolt", "tor",
    "miltun", "haru", "kidd", "della", "zeppie"
]

logger = logging.getLogger("sticky.api.personas")

class PersonaDefaults(BaseModel):
    """Default configuration for a persona"""
    model: str
    provider: str = "anthropic"
    temperature: float = Field(0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(1000, gt=0)

class PersonaSafetyBounds(BaseModel):
    """Safety bounds for persona behavior"""
    max_tokens: int = Field(4000, gt=0)
    min_temperature: float = Field(0.1, ge=0.0, le=1.0)
    max_temperature: float = Field(1.0, ge=0.0, le=1.0)
    max_context_length: int = Field(8000, gt=0)

class Persona(BaseModel):
    """Persona configuration model"""
    id: str
    name: str
    description: str
    system_prompt: str
    defaults: PersonaDefaults
    safety_bounds: PersonaSafetyBounds
    created_at: str = Field(default_factory=lambda: MODULE_METADATA["created_at"])
    created_by: str = Field(default_factory=lambda: MODULE_METADATA["created_by"])

    def build_system(self) -> str:
        """Build complete system prompt"""
        return f"""You are {self.name}. {self.description}

{self.system_prompt}

Remember:
- Always stay in character
- Never break the fourth wall
- Maintain consistent personality
- Follow safety bounds
- Be helpful and engaging"""

    def build_introduction(self) -> str:
        """Build persona introduction"""
        return f"Hello! I'm {self.name}. {self.description}"

class PersonaRegistry:
    """Registry for managing personas"""
    
    def __init__(self):
        self.personas: Dict[str, Persona] = {}
        self.release_tier = os.getenv("PERSONA_RELEASE_TIER", "launch")
        self.load_info = self._load_personas()
        
    def _should_load_persona(self, persona_id: str) -> bool:
        """Determine if persona should be loaded based on release tier"""
        if self.release_tier == "all":
            return True
        elif self.release_tier == "wave_three":
            return persona_id in LAUNCH_PERSONAS + WAVE_TWO_PERSONAS + WAVE_THREE_PERSONAS
        elif self.release_tier == "wave_two":
            return persona_id in LAUNCH_PERSONAS + WAVE_TWO_PERSONAS
        else:  # launch tier
            return persona_id in LAUNCH_PERSONAS
        
    def _load_personas(self) -> Dict:
        """Load personas from configuration"""
        try:
            # Load from config directory
            config_dir = os.path.join(
                os.path.dirname(__file__),
                "config"
            )
            
            loaded = 0
            errors = []
            
            # Process each config file
            for filename in os.listdir(config_dir):
                if not filename.endswith(".json"):
                    continue
                    
                try:
                    persona_id = filename[:-5]  # Remove .json
                    if not self._should_load_persona(persona_id):
                        continue
                        
                    with open(os.path.join(config_dir, filename)) as f:
                        config = json.load(f)
                        persona = Persona(**config)
                        self.personas[persona.id] = persona
                        loaded += 1
                except Exception as e:
                    errors.append({
                        "file": filename,
                        "error": str(e)
                    })
                    logger.error(
                        f"Failed to load persona from {filename}",
                        exc_info=True
                    )
            
            return {
                "loaded": loaded,
                "errors": errors,
                "timestamp": MODULE_METADATA["created_at"],
                "release_tier": self.release_tier
            }
            
        except Exception as e:
            logger.error("Failed to load personas", exc_info=True)
            return {
                "loaded": 0,
                "errors": [{"file": "all", "error": str(e)}],
                "timestamp": MODULE_METADATA["created_at"],
                "release_tier": self.release_tier
            }
    
    def get(self, persona_id: str) -> Persona:
        """Get persona by ID"""
        if persona_id not in self.personas:
            raise KeyError(f"Persona {persona_id} not found")
        return self.personas[persona_id]
        
    def list_all(self) -> List[Persona]:
        """List all available personas"""
        return list(self.personas.values())
        
    def search(self, query: str) -> List[Persona]:
        """Search personas by name or description"""
        query = query.lower()
        return [
            p for p in self.personas.values()
            if query in p.name.lower() or query in p.description.lower()
        ]
        
    def validate(self, persona_id: str) -> bool:
        """Validate persona exists"""
        return persona_id in self.personas
        
    def get_defaults(self, persona_id: str) -> Dict:
        """Get default configuration for persona"""
        persona = self.get(persona_id)
        return persona.defaults.dict()
        
    def get_safety_bounds(self, persona_id: str) -> Dict:
        """Get safety bounds for persona"""
        persona = self.get(persona_id)
        return persona.safety_bounds.dict()