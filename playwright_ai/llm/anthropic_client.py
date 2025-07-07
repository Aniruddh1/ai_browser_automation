"""Anthropic LLM client implementation."""

import json
from typing import Any, List, Optional, TYPE_CHECKING
from anthropic import AsyncAnthropic
from pydantic import BaseModel
import uuid

from .client import LLMClient
from ..types import LLMMessage, LLMResponse, LLMChoice, LLMUsageMetrics
from ..utils.logger import PlaywrightAILogger

if TYPE_CHECKING:
    from ..cache import LLMCache


class AnthropicClient(LLMClient):
    """
    Anthropic LLM client implementation.
    
    Supports Claude 3 models with tool use capabilities.
    """
    
    def __init__(
        self,
        model_name: str,
        api_key: Optional[str],
        logger: PlaywrightAILogger,
        cache: Optional['LLMCache'] = None,
        **kwargs: Any
    ):
        """Initialize Anthropic client."""
        super().__init__(model_name, api_key, logger, cache=cache)
        
        # Initialize Anthropic client
        self.client = AsyncAnthropic(
            api_key=api_key,
            **kwargs
        )
        
        # Map model names
        self.anthropic_model = self._map_model_name(model_name)
    
    def _map_model_name(self, model_name: str) -> str:
        """Map common model names to Anthropic model IDs."""
        model_map = {
            "claude-3-opus": "claude-3-opus-20240229",
            "claude-3-sonnet": "claude-3-sonnet-20240229",
            "claude-3-haiku": "claude-3-haiku-20240307",
            "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
            "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
        }
        return model_map.get(model_name, model_name)
    
    async def create_chat_completion(
        self,
        messages: List[LLMMessage],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        response_model: Optional[BaseModel] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Create a chat completion."""
        # Build cache key
        cache_key = self._build_cache_key(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_model=response_model.__name__ if response_model else None,
            **kwargs
        )
        
        # Check cache first
        request_id = str(uuid.uuid4())
        cached_response = await self._get_from_cache(cache_key, request_id)
        if cached_response:
            self.logger.debug("llm:anthropic", "Using cached response")
            # Convert cached dict back to LLMResponse
            return LLMResponse(**cached_response)
        
        try:
            # Convert messages to Anthropic format
            anthropic_messages = self._convert_messages(messages)
            
            # Extract system message if present
            system_message = None
            if anthropic_messages and anthropic_messages[0]["role"] == "system":
                system_message = anthropic_messages.pop(0)["content"]
            
            # Add schema hint to system message if needed
            if response_model:
                schema_hint = f"You must respond with valid JSON matching this schema: {self._get_schema_hint(response_model)}"
                if system_message:
                    system_message = f"{system_message}\n\n{schema_hint}"
                else:
                    system_message = schema_hint
            
            # Prepare request parameters
            request_params = {
                "model": self.anthropic_model,
                "messages": anthropic_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,  # Anthropic requires max_tokens
            }
            
            if system_message:
                request_params["system"] = system_message
            
            # Add any additional parameters
            request_params.update(kwargs)
            
            # Make API call
            self.logger.debug(
                "llm",
                "Making Anthropic API call",
                model=self.anthropic_model,
                message_count=len(messages)
            )
            
            response = await self.client.messages.create(**request_params)
            
            # Convert to our format
            llm_response = LLMResponse(
                id=response.id,
                object="chat.completion",  # Anthropic doesn't have this field
                created=0,  # Anthropic doesn't provide creation timestamp
                model=response.model,
                choices=[
                    LLMChoice(
                        index=0,
                        message=LLMMessage(
                            role="assistant",
                            content=response.content[0].text if response.content else ""
                        ),
                        finish_reason=response.stop_reason or "stop"
                    )
                ],
                usage=LLMUsageMetrics(
                    prompt_tokens=response.usage.input_tokens,
                    completion_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.input_tokens + response.usage.output_tokens
                ) if response.usage else None
            )
            
            # Cache the response
            await self._save_to_cache(cache_key, llm_response.model_dump(), request_id)
            
            return llm_response
            
        except Exception as e:
            self.logger.error("llm", f"Anthropic API error: {e}")
            raise
    
    async def generate_object(
        self,
        prompt: str,
        schema: BaseModel,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> Any:
        """Generate a structured object."""
        # Create message with schema hint
        messages = [
            LLMMessage(
                role="user",
                content=f"{prompt}\n\nReturn a JSON object matching this schema: {self._get_schema_hint(schema)}"
            )
        ]
        
        # Get completion with JSON mode hint
        response = await self.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_model=schema,
            **kwargs
        )
        
        # Parse response
        content = response.choices[0].message.content
        
        # Extract JSON from response (Anthropic sometimes includes explanation)
        json_str = self._extract_json(content)
        
        try:
            data = json.loads(json_str)
            return schema(**data)
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error("llm", f"Failed to parse Anthropic response as {schema.__name__}: {e}")
            raise
    
    def _convert_messages(self, messages: List[LLMMessage]) -> List[dict]:
        """Convert our message format to Anthropic format."""
        anthropic_messages = []
        
        for msg in messages:
            message_dict = {
                "role": msg.role if msg.role != "system" else "user",
                "content": []
            }
            
            if isinstance(msg.content, str):
                message_dict["content"] = msg.content
            elif isinstance(msg.content, list):
                # Handle multimodal content
                content_parts = []
                for part in msg.content:
                    if part["type"] == "text":
                        content_parts.append({
                            "type": "text",
                            "text": part["text"]
                        })
                    elif part["type"] == "image":
                        # Handle image content
                        image_data = part.get("image")
                        if isinstance(image_data, str):
                            # Base64 encoded image
                            content_parts.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_data
                                }
                            })
                
                message_dict["content"] = content_parts
            
            anthropic_messages.append(message_dict)
        
        return anthropic_messages
    
    def _get_schema_hint(self, schema: type[BaseModel]) -> str:
        """Get a JSON schema hint for the model."""
        try:
            # Get Pydantic schema
            schema_dict = schema.model_json_schema()
            # Simplify for LLM
            return json.dumps(schema_dict, indent=2)
        except Exception:
            # Fallback to field names
            fields = list(schema.model_fields.keys())
            return f"Object with fields: {', '.join(fields)}"
    
    def _extract_json(self, content: str) -> str:
        """Extract JSON from content that might include explanation."""
        # Look for JSON block
        import re
        
        # Try to find JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', content, re.DOTALL)
        if json_match:
            return json_match.group(1)
        
        # Try to find raw JSON
        json_match = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
        if json_match:
            return json_match.group(1)
        
        # Return original content as fallback
        return content