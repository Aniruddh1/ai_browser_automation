"""OpenAI LLM client implementation."""

import json
from typing import Any, List, Optional, TYPE_CHECKING
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel
import uuid

from .client import LLMClient
from ..types import LLMMessage, LLMResponse, LLMChoice, LLMUsageMetrics
from ..utils.logger import AIBrowserAutomationLogger

if TYPE_CHECKING:
    from ..cache import LLMCache


class OpenAIClient(LLMClient):
    """
    OpenAI LLM client implementation.
    
    Supports GPT-4, GPT-4 Vision, and other OpenAI models.
    """
    
    def __init__(
        self,
        model_name: str,
        api_key: Optional[str],
        logger: AIBrowserAutomationLogger,
        cache: Optional['LLMCache'] = None,
        **kwargs: Any
    ):
        """Initialize OpenAI client."""
        super().__init__(model_name, api_key, logger, cache=cache)
        
        # Initialize OpenAI client
        self.client = AsyncOpenAI(
            api_key=api_key,
            **kwargs
        )
        
        # Vision model support
        self.supports_vision = any(vision_model in model_name for vision_model in [
            "gpt-4-vision", "gpt-4o", "gpt-4-turbo"
        ])
    
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
            self.logger.debug("llm:openai", "Using cached response")
            # Convert cached dict back to LLMResponse
            return LLMResponse(**cached_response)
        
        try:
            # Convert messages to OpenAI format
            openai_messages = self._convert_messages(messages)
            
            # Prepare request parameters
            request_params = {
                "model": self.model_name,
                "messages": openai_messages,
                "temperature": temperature,
            }
            
            if max_tokens:
                request_params["max_tokens"] = max_tokens
            
            # Add response format if specified
            if response_model:
                request_params["response_format"] = {"type": "json_object"}
                # Add schema hint to system message
                schema_hint = self._get_schema_hint(response_model)
                if schema_hint:
                    request_params["messages"].insert(0, {
                        "role": "system",
                        "content": f"You must respond with valid JSON matching this schema: {schema_hint}"
                    })
            
            # Add any additional parameters
            request_params.update(kwargs)
            
            # Make API call
            self.logger.debug(
                "llm:openai",
                "Making OpenAI API call",
                model=self.model_name,
                message_count=len(messages)
            )
            
            response = await self.client.chat.completions.create(**request_params)
            
            # Convert to our format
            llm_response = LLMResponse(
                id=response.id,
                object=response.object,
                created=response.created,
                model=response.model,
                choices=[
                    LLMChoice(
                        index=choice.index,
                        message=LLMMessage(
                            role=choice.message.role,
                            content=choice.message.content or ""
                        ),
                        finish_reason=choice.finish_reason
                    )
                    for choice in response.choices
                ],
                usage=LLMUsageMetrics(
                    prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                    completion_tokens=response.usage.completion_tokens if response.usage else 0,
                    total_tokens=response.usage.total_tokens if response.usage else 0
                ) if response.usage else None
            )
            
            # Cache the response
            await self._save_to_cache(cache_key, llm_response.model_dump(), request_id)
            
            return llm_response
            
        except Exception as e:
            self.logger.error("llm:openai", f"OpenAI API error: {e}")
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
                role="system",
                content=f"You are a helpful assistant that returns valid JSON matching the provided schema."
            ),
            LLMMessage(
                role="user",
                content=f"{prompt}\n\nReturn a JSON object matching this schema: {self._get_schema_hint(schema)}"
            )
        ]
        
        # Get completion
        response = await self.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_model=schema,
            **kwargs
        )
        
        # Parse response
        content = response.choices[0].message.content
        try:
            data = json.loads(content)
            return schema(**data)
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error("llm:openai", f"Failed to parse OpenAI response as {schema.__name__}: {e}")
            raise
    
    def _convert_messages(self, messages: List[LLMMessage]) -> List[ChatCompletionMessageParam]:
        """Convert our message format to OpenAI format."""
        openai_messages = []
        
        for msg in messages:
            if isinstance(msg.content, str):
                openai_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            elif isinstance(msg.content, list):
                # Handle multimodal content
                content_parts = []
                for part in msg.content:
                    if part["type"] == "text":
                        content_parts.append({
                            "type": "text",
                            "text": part["text"]
                        })
                    elif part["type"] == "image" and self.supports_vision:
                        # Handle image content
                        image_data = part.get("image")
                        if isinstance(image_data, str):
                            # Base64 encoded image
                            content_parts.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            })
                        elif isinstance(image_data, dict) and "url" in image_data:
                            # Image URL
                            content_parts.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": image_data["url"]
                                }
                            })
                
                if content_parts:
                    openai_messages.append({
                        "role": msg.role,
                        "content": content_parts
                    })
        
        return openai_messages
    
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