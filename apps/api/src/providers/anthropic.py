from typing import Dict, List
from anthropic import Anthropic
from .base import Provider

class AnthropicProvider(Provider):
    name = "anthropic"
    
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    def complete(self, 
                system: str, 
                messages: List[Dict[str, str]], 
                model: str, 
                temperature: float, 
                max_tokens: int) -> Dict:
        """
        Complete using Anthropic Claude
        
        Args:
            system: System prompt
            messages: List of message dicts with role and content 
            model: Model identifier (e.g. "claude-3-haiku-20240307")
            temperature: Temperature parameter (0-1)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Dict with generated text and usage statistics
        """
        response = self.client.messages.create(
            model=model,
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return {
            "text": response.content[0].text,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }