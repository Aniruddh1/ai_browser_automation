"""Google AI (Gemini) LLM client implementation."""

import json
from typing import Any, List, Optional, TYPE_CHECKING
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from pydantic import BaseModel
import uuid

from .client import LLMClient
from ..types import LLMMessage, LLMResponse, LLMChoice, LLMUsageMetrics
from ..utils.logger import PlaywrightAILogger

if TYPE_CHECKING:
    from ..cache import LLMCache


class GoogleClient(LLMClient):
    """
    Google AI LLM client implementation.
    
    Supports Gemini models with multimodal capabilities.
    """
    
    def __init__(
        self,
        model_name: str,
        api_key: Optional[str],
        logger: PlaywrightAILogger,
        cache: Optional['LLMCache'] = None,
        **kwargs: Any
    ):
        """Initialize Google AI client."""
        super().__init__(model_name, api_key, logger, cache=cache)
        
        # Configure Google AI
        genai.configure(api_key=api_key)
        
        # Map model names
        self.google_model = self._map_model_name(model_name)
        
        # Initialize model
        self.model = genai.GenerativeModel(
            model_name=self.google_model,
            safety_settings=self._get_safety_settings(),
            **kwargs
        )
    
    def _map_model_name(self, model_name: str) -> str:
        """Map common model names to Google model IDs."""
        model_map = {
            # Legacy models (for backward compatibility)
            "gemini-pro": "gemini-pro",
            "gemini-pro-vision": "gemini-pro-vision",
            
            # Stable Gemini 2.5 models
            "gemini-2.5-pro": "gemini-2.5-pro",
            "gemini-2.5-flash": "gemini-2.5-flash",
            
            # Stable Gemini 2.0 models
            "gemini-2.0-flash": "gemini-2.0-flash",
            "gemini-2.0-flash-lite": "gemini-2.0-flash-lite",
            
            # Stable Gemini 1.5 models
            "gemini-1.5-pro": "gemini-1.5-pro",
            "gemini-1.5-flash": "gemini-1.5-flash",
            "gemini-1.5-flash-8b": "gemini-1.5-flash-8b",
            
            # Preview/Experimental models
            "gemini-2.5-flash-lite-preview-06-17": "gemini-2.5-flash-lite-preview-06-17",
            "gemini-2.5-flash-preview-native-audio-dialog": "gemini-2.5-flash-preview-native-audio-dialog",
            "gemini-2.5-flash-exp-native-audio-thinking-dialog": "gemini-2.5-flash-exp-native-audio-thinking-dialog",
            "gemini-2.5-flash-preview-tts": "gemini-2.5-flash-preview-tts",
            "gemini-2.5-pro-preview-tts": "gemini-2.5-pro-preview-tts",
            "gemini-2.0-flash-preview-image-generation": "gemini-2.0-flash-preview-image-generation",
            "gemini-2.0-flash-exp": "gemini-2.0-flash-exp",
            "gemini-live-2.5-flash-preview": "gemini-live-2.5-flash-preview",
            "gemini-2.0-flash-live-001": "gemini-2.0-flash-live-001",
            
            # Embedding models
            "text-embedding-004": "text-embedding-004",
            "embedding-001": "embedding-001",
            "gemini-embedding-exp-03-07": "gemini-embedding-exp-03-07",
        }
        return model_map.get(model_name, model_name)
    
    def _get_safety_settings(self):
        """Get permissive safety settings."""
        return {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
    
    async def create_chat_completion(
        self,
        messages: List[LLMMessage],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        response_model: Optional[BaseModel] = None,
        **kwargs: Any  # noqa: ARG002
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
            self.logger.debug("llm:google", "Using cached response")
            # Convert cached dict back to LLMResponse
            return LLMResponse(**cached_response)
        
        try:
            # Convert messages to Google format
            google_messages = self._convert_messages(messages)
            
            # Add schema hint if needed
            if response_model:
                schema_hint = f"\n\nYou must respond with valid JSON matching this schema: {self._get_schema_hint(response_model)}"
                if google_messages:
                    # Add to last user message
                    for i in range(len(google_messages) - 1, -1, -1):
                        if google_messages[i]["role"] == "user":
                            if isinstance(google_messages[i]["parts"], list):
                                google_messages[i]["parts"][-1] += schema_hint
                            else:
                                google_messages[i]["parts"] += schema_hint
                            break
            
            # Create chat session
            chat = self.model.start_chat(history=google_messages[:-1] if len(google_messages) > 1 else [])
            
            # Get the last message
            last_message = google_messages[-1] if google_messages else {"parts": "Hello"}
            
            # Configure generation
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            # Send message
            self.logger.debug(
                "llm",
                "Making Google AI API call",
                model=self.google_model,
                message_count=len(messages)
            )
            
            response = await chat.send_message_async(
                last_message["parts"],
                generation_config=generation_config
            )
            
            # Convert to our format
            llm_response = LLMResponse(
                id=f"google-{id(response)}",
                object="chat.completion",
                created=0,  # Google doesn't provide timestamp
                model=self.google_model,
                choices=[
                    LLMChoice(
                        index=0,
                        message=LLMMessage(
                            role="assistant",
                            content=response.text
                        ),
                        finish_reason="stop"
                    )
                ],
                usage=LLMUsageMetrics(
                    prompt_tokens=response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
                    completion_tokens=response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
                    total_tokens=(response.usage_metadata.prompt_token_count + response.usage_metadata.candidates_token_count) if hasattr(response, 'usage_metadata') else 0
                ) if hasattr(response, 'usage_metadata') else None
            )
            
            # Cache the response
            await self._save_to_cache(cache_key, llm_response.model_dump(), request_id)
            
            return llm_response
            
        except Exception as e:
            self.logger.error("llm", f"Google AI API error: {e}")
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
        
        # Extract JSON from response
        json_str = self._extract_json(content)
        
        try:
            data = json.loads(json_str)
            return schema(**data)
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error("llm", f"Failed to parse Google AI response as {schema.__name__}: {e}")
            raise
    
    def _convert_messages(self, messages: List[LLMMessage]) -> List[dict]:
        """Convert our message format to Google format."""
        google_messages = []
        
        for msg in messages:
            # Google uses "user" and "model" roles
            role = "model" if msg.role == "assistant" else "user"
            
            if isinstance(msg.content, str):
                google_messages.append({
                    "role": role,
                    "parts": msg.content
                })
            elif isinstance(msg.content, list):
                # Handle multimodal content
                parts = []
                for part in msg.content:
                    if part["type"] == "text":
                        parts.append(part["text"])
                    elif part["type"] == "image":
                        # Handle image content
                        image_data = part.get("image")
                        if isinstance(image_data, str):
                            # Base64 encoded image
                            import base64
                            import io
                            from PIL import Image
                            
                            # Decode base64 to PIL Image
                            image_bytes = base64.b64decode(image_data)
                            image = Image.open(io.BytesIO(image_bytes))
                            parts.append(image)
                
                if parts:
                    google_messages.append({
                        "role": role,
                        "parts": parts
                    })
        
        return google_messages
    
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