from typing import Dict, List
from abc import ABC, abstractmethod

class Provider(ABC):
    name: str
    
    @abstractmethod
    def complete(self, 
                system: str, 
                messages: List[Dict[str, str]], 
                model: str, 
                temperature: float, 
                max_tokens: int) -> Dict:
        """
        Base provider interface for LLM completion
        
        Args:
            system: System prompt
            messages: List of message dicts with role and content
            model: Model identifier
            temperature: Temperature parameter (0-1)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Dict with text response and usage statistics
        """
        raise NotImplementedError