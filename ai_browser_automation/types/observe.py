"""Schema definitions for observe functionality."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class ObserveElementSchema(BaseModel):
    """Schema for observed element from LLM response."""
    
    elementId: str = Field(..., description="The encoded ID from the page (e.g., 0-15)")
    description: str = Field(..., description="Human-readable description of the element")
    
    @validator('elementId')
    def validate_element_id(cls, v):
        """Ensure elementId follows expected format."""
        if not v or not isinstance(v, str):
            raise ValueError("elementId must be a non-empty string")
        return v
    
    @validator('description')
    def validate_description(cls, v):
        """Ensure description is non-empty."""
        if not v or not v.strip():
            raise ValueError("description must be non-empty")
        return v.strip()


class ObserveResponseSchema(BaseModel):
    """Schema for complete observe response."""
    
    elements: List[ObserveElementSchema] = Field(..., description="List of observed elements")
    
    @validator('elements')
    def validate_elements(cls, v):
        """Ensure at least one element is returned."""
        if not v:
            raise ValueError("At least one element must be returned")
        return v


class ActObserveElementSchema(BaseModel):
    """Schema for act observe element with method and arguments."""
    
    elementId: str = Field(..., description="The encoded ID from the page")
    description: str = Field(..., description="Human-readable description")
    method: str = Field(..., description="Playwright method to use")
    arguments: List[Any] = Field(default_factory=list, description="Arguments for the method")
    
    @validator('elementId')
    def validate_element_id(cls, v):
        """Ensure elementId follows expected format."""
        if not v or not isinstance(v, str):
            raise ValueError("elementId must be a non-empty string")
        return v
    
    @validator('description')
    def validate_description(cls, v):
        """Ensure description is non-empty."""
        if not v or not v.strip():
            raise ValueError("description must be non-empty")
        return v.strip()
    
    @validator('method')
    def validate_method(cls, v):
        """Validate Playwright method."""
        supported_methods = [
            'click', 'fill', 'type', 'press', 'hover', 'selectOption',
            'check', 'uncheck', 'focus', 'blur', 'scrollIntoView'
        ]
        if v not in supported_methods:
            raise ValueError(f"method must be one of {supported_methods}")
        return v


class ActObserveResponseSchema(BaseModel):
    """Schema for act-specific observe response."""
    
    elements: List[ActObserveElementSchema] = Field(..., description="List of observed elements with actions")