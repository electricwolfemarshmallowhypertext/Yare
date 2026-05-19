from typing import Dict, Optional, Any
import os
import logging
from anthropic import Anthropic
from openai import OpenAI
from google.cloud import aiplatform

# Module metadata
MODULE_METADATA = {
    "created_at": "2025-11-02 18:35:53",
    "created_by": "electricwolfemarshmallowhypertext",
    "version": "1.0.0"
}

logger = logging.getLogger("sticky.api.providers")

class Provider:
    """Base provider class"""
    name: str = "base"
    
    def __init__(self):
        self._created_at = MODULE_METADATA["created_at"]
        self._created_by = MODULE_METADATA["created_by"]
        
    async def complete(
        self,
        system: str,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Generate completion from messages"""
        raise NotImplementedError

class AnthropicProvider(Provider):
    """Anthropic Claude provider"""
    name = "anthropic"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.client = Anthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
        )
        self.models = ["claude-2", "claude-instant-1"]
        
    async def complete(
        self,
        system: str,
        messages: list,
        model: str = "claude-2",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Generate completion using Claude"""
        try:
            # Validate inputs
            if not messages:
                raise ValueError("Messages list cannot be empty")
                
            if model not in self.models:
                raise ValueError(f"Invalid model: {model}")
                
            if not 0 <= temperature <= 1:
                raise ValueError("Temperature must be between 0 and 1")
            
            # Format messages
            formatted_messages = []
            for msg in messages:
                if msg["role"] == "user":
                    formatted_messages.append({
                        "role": "user",
                        "content": msg["content"]
                    })
                elif msg["role"] == "assistant":
                    formatted_messages.append({
                        "role": "assistant",
                        "content": msg["content"]
                    })
            
            # Make API call
            response = await self.client.messages.create(
                model=model,
                system=system,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Format response
            return {
                "text": response.content[0].text,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "provider": self.name
                }
            }
            
        except Exception as e:
            logger.error(
                "Anthropic completion failed",
                extra={
                    "model": model,
                    "error": str(e)
                },
                exc_info=True
            )
            raise

class OpenAIProvider(Provider):
    """OpenAI provider"""
    name = "openai"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY")
        )
        self.models = ["gpt-4", "gpt-3.5-turbo"]
        
    async def complete(
        self,
        system: str,
        messages: list,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Generate completion using OpenAI"""
        try:
            # Validate inputs
            if not messages:
                raise ValueError("Messages list cannot be empty")
                
            if model not in self.models:
                raise ValueError(f"Invalid model: {model}")
                
            if not 0 <= temperature <= 1:
                raise ValueError("Temperature must be between 0 and 1")
            
            # Format messages
            formatted_messages = [{"role": "system", "content": system}]
            formatted_messages.extend(messages)
            
            # Make API call
            response = await self.client.chat.completions.create(
                model=model,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Format response
            return {
                "text": response.choices[0].message.content,
                "usage": {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "provider": self.name
                }
            }
            
        except Exception as e:
            logger.error(
                "OpenAI completion failed",
                extra={
                    "model": model,
                    "error": str(e)
                },
                exc_info=True
            )
            raise

class VertexAIProvider(Provider):
    """Google Vertex AI provider"""
    name = "vertexai"
    
    def __init__(self, project_id: Optional[str] = None):
        super().__init__()
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        aiplatform.init(project=self.project_id)
        self.models = ["text-bison", "chat-bison"]
        
    async def complete(
        self,
        system: str,
        messages: list,
        model: str = "chat-bison",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Generate completion using Vertex AI"""
        try:
            # Validate inputs
            if not messages:
                raise ValueError("Messages list cannot be empty")
                
            if model not in self.models:
                raise ValueError(f"Invalid model: {model}")
                
            if not 0 <= temperature <= 1:
                raise ValueError("Temperature must be between 0 and 1")
            
            # Format messages for Vertex AI
            chat = aiplatform.ChatModel.from_pretrained(model)
            parameters = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "system_content": system
            }
            
            # Make API call
            response = chat.predict(
                messages=[msg["content"] for msg in messages],
                **parameters
            )
            
            # Format response
            return {
                "text": response.text,
                "usage": {
                    "input_tokens": len(" ".join([msg["content"] for msg in messages])),
                    "output_tokens": len(response.text),
                    "provider": self.name
                }
            }
            
        except Exception as e:
            logger.error(
                "Vertex AI completion failed",
                extra={
                    "model": model,
                    "error": str(e)
                },
                exc_info=True
            )
            raise

class ProviderRegistry:
    """Registry for managing providers"""
    
    def __init__(self):
        self.providers: Dict[str, Provider] = {}
        self.default_provider = "anthropic"
        self._initialize_providers()
        
    def _initialize_providers(self):
        """Initialize available providers"""
        try:
            # Anthropic (Claude)
            if os.getenv("ANTHROPIC_API_KEY"):
                self.providers["anthropic"] = AnthropicProvider()
                
            # OpenAI (GPT)
            if os.getenv("OPENAI_API_KEY"):
                self.providers["openai"] = OpenAIProvider()
                
            # Vertex AI
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                self.providers["vertexai"] = VertexAIProvider()
                
            logger.info(
                "Providers initialized",
                extra={
                    "available": list(self.providers.keys()),
                    "default": self.default_provider
                }
            )
            
        except Exception as e:
            logger.error(
                "Failed to initialize providers",
                extra={"error": str(e)},
                exc_info=True
            )
            raise
            
    def get(self, provider_name: str) -> Provider:
        """Get provider by name"""
        if provider_name not in self.providers:
            raise KeyError(f"Provider {provider_name} not found")
        return self.providers[provider_name]
        
    def get_default(self) -> Provider:
        """Get default provider"""
        return self.get(self.default_provider)