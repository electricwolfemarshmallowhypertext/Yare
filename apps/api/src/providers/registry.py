import json
from pathlib import Path
from typing import Dict
from .schema import Persona

CATALOG_PATH = Path("../../packages/personas/index.json")
PERSONA_DIR = Path("../../packages/personas")

class PersonaRegistry:
    def __init__(self):
        """Initialize the persona registry"""
        self._personas: Dict[str, Persona] = {}
        self._load_timestamp = "2025-11-02 18:04:34"
        self._loaded_by = "electricwolfemarshmallowhypertext"
        self.reload()
    
    def reload(self) -> None:
        """Load all personas from disk"""
        try:
            catalog = json.loads(CATALOG_PATH.read_text())
            personas = {}
            
            for persona_id in catalog["personas"]:
                persona_path = PERSONA_DIR / f"{persona_id}.json"
                if not persona_path.exists():
                    continue
                    
                data = json.loads(persona_path.read_text())
                personas[persona_id] = Persona(**data)
                
            self._personas = personas
            
        except Exception as e:
            raise RuntimeError(f"Failed to load personas: {str(e)}")
    
    def get(self, persona_id: str) -> Persona:
        """Get a persona by ID"""
        if persona_id not in self._personas:
            raise KeyError(f"Persona {persona_id} not found")
        return self._personas[persona_id]
    
    def list_all(self) -> Dict[str, Persona]:
        """Get all loaded personas"""
        return self._personas.copy()
    
    @property
    def load_info(self) -> Dict:
        """Get registry load information"""
        return {
            "timestamp": self._load_timestamp,
            "loaded_by": self._loaded_by,
            "count": len(self._personas)
        }