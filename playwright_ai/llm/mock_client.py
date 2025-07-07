"""Mock LLM client for testing."""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from .client import LLMClient
from ..types import LLMMessage, LLMResponse, LLMChoice, LLMUsageMetrics
from pydantic import BaseModel


class MockLLMClient(LLMClient):
    """
    Mock LLM client for testing and development.
    
    Returns predefined responses for common queries.
    """
    
    async def create_chat_completion(
        self,
        messages: List[LLMMessage],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        response_model: Optional[BaseModel] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Create a mock chat completion."""
        # Get the last user message
        last_message = ""
        for msg in reversed(messages):
            if msg.role == "user":
                last_message = msg.content if isinstance(msg.content, str) else str(msg.content)
                break
        
        # Generate mock response based on content
        response_content = self._generate_mock_response(last_message, response_model)
        
        # Build response
        return LLMResponse(
            id=f"mock-{uuid.uuid4()}",
            object="chat.completion",
            created=int(datetime.now().timestamp()),
            model=self.model_name,
            choices=[
                LLMChoice(
                    index=0,
                    message=LLMMessage(
                        role="assistant",
                        content=response_content
                    ),
                    finish_reason="stop"
                )
            ],
            usage=LLMUsageMetrics(
                prompt_tokens=len(last_message.split()),
                completion_tokens=len(response_content.split()) if isinstance(response_content, str) else 10,
                total_tokens=len(last_message.split()) + (len(response_content.split()) if isinstance(response_content, str) else 10)
            )
        )
    
    async def generate_object(
        self,
        prompt: str,
        schema: BaseModel,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> Any:
        """Generate a mock object matching the schema."""
        # Create a simple mock object
        mock_data = self._generate_mock_object(schema)
        
        # Validate with schema
        return schema(**mock_data)
    
    def _generate_mock_response(self, prompt: str, response_model: Optional[BaseModel] = None) -> str:
        """Generate mock response based on prompt content."""
        prompt_lower = prompt.lower()
        
        # Check for observe/analyze/find patterns first (higher priority)
        if any(word in prompt_lower for word in ["observe", "find", "analyze", "identify", "interactive elements"]):
            # Check if looking for specific elements
            if "link" in prompt_lower:
                return json.dumps([
                    {
                        "selector": "a[href='https://www.iana.org/domains/example']",
                        "description": "More information... link",
                        "action": "click",
                        "encodedId": "0-1"
                    }
                ])
            elif "button" in prompt_lower:
                return json.dumps([
                    {
                        "selector": "button.submit",
                        "description": "Submit button",
                        "action": "click",
                        "encodedId": "0-1"
                    }
                ])
            else:
                # General elements - using actual page data
                return json.dumps([
                    {
                        "selector": "h1",
                        "description": "Main heading - Example Domain",
                        "action": "click",
                        "encodedId": "0-1"
                    },
                    {
                        "selector": "p",
                        "description": "Paragraph with domain information",
                        "encodedId": "0-2"
                    },
                    {
                        "selector": "a[href='https://www.iana.org/domains/example']",
                        "description": "More information... link",
                        "action": "click",
                        "encodedId": "0-3"
                    }
                ], default=str)
        
        # Mock responses for other patterns
        elif "click" in prompt_lower and "observe" not in prompt_lower:
            if response_model:
                return json.dumps({"action": "click", "selector": "button", "success": True})
            return "I would click on the specified element."
        
        elif "extract" in prompt_lower:
            if response_model:
                return json.dumps(self._generate_mock_object(response_model))
            return "Here is the extracted data: {\"title\": \"Example Page\", \"content\": \"Sample content\"}"
        
        else:
            return "Mock response for: " + prompt[:100]
    
    def _generate_mock_object(self, schema: type[BaseModel]) -> Dict[str, Any]:
        """Generate mock data for a Pydantic schema."""
        mock_data = {}
        
        # Get schema fields
        for field_name, field_info in schema.model_fields.items():
            field_type = field_info.annotation
            
            # Generate contextual mock values based on field name
            if field_name == "title":
                mock_data[field_name] = "Example Domain"
            elif field_name == "main_heading":
                mock_data[field_name] = "Example Domain"
            elif field_name == "description":
                mock_data[field_name] = "This domain is for use in illustrative examples in documents."
            elif field_name == "links_count":
                mock_data[field_name] = 1
            elif field_name == "has_form":
                mock_data[field_name] = False
            # Generic type-based values
            elif field_type == str:
                mock_data[field_name] = f"mock_{field_name}"
            elif field_type == int:
                mock_data[field_name] = 42
            elif field_type == float:
                mock_data[field_name] = 3.14
            elif field_type == bool:
                mock_data[field_name] = True
            elif field_type == list:
                mock_data[field_name] = []
            elif field_type == dict:
                mock_data[field_name] = {}
            else:
                # For optional fields, we can skip
                if not field_info.is_required():
                    continue
                # Default to string
                mock_data[field_name] = f"mock_{field_name}"
        
        return mock_data