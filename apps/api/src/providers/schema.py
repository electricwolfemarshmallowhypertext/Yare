from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class PersonaSafetyBounds(BaseModel):
    allow_code: bool = True
    allow_links: bool = True
    max_tokens: int = Field(default=800, ge=1, le=4000)

class PersonaMemoryPolicy(BaseModel):
    use_long_term: bool = True
    salience_threshold: float = Field(default=0.65, ge=0, le=1.0)
    max_items: int = Field(default=200, ge=1, le=1000)

class PersonaDefaults(BaseModel):
    model: str
    temperature: float = Field(default=0.3, ge=0, le=1.0)

class Persona(BaseModel):
    id: str
    name: str
    category: str
    version: str
    description: str
    system_prompt: str
    style_rules: List[str]
    response_template: Optional[str] = None
    safety_bounds: PersonaSafetyBounds
    memory_policy: PersonaMemoryPolicy
    defaults: PersonaDefaults
    
    def build_system(self) -> str:
        """Builds complete system prompt with style rules"""
        rules = "\n".join(f"- {rule}" for rule in self.style_rules)
        return f"{self.system_prompt}\n\nStyle Rules:\n{rules}"