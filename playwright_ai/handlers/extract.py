"""ExtractHandler implementation for data extraction."""

import json
from typing import Any, Dict, List, Optional, get_type_hints, get_origin, get_args
from pydantic import BaseModel, create_model

from .base import BaseHandler
from ..types import ExtractOptions, ExtractResult, LLMMessage
from ..dom import get_page_text, clean_text
from ..core.errors import ExtractionFailedError, SchemaValidationError


class ExtractHandler(BaseHandler[ExtractResult]):
    """
    Handler for extracting structured data from web pages.
    
    Transforms schemas to handle URL fields and extracts data
    matching Pydantic models.
    """
    
    async def handle(
        self,
        page: 'PlaywrightAIPage',
        options: ExtractOptions
    ) -> ExtractResult:
        """
        Extract structured data from the page.
        
        Args:
            page: PlaywrightAIPage instance
            options: Extraction options
            
        Returns:
            ExtractResult with extracted data
        """
        self._log_info(
            "Starting extraction",
            schema=options.response_schema.__name__ if hasattr(options.response_schema, '__name__') else 'dict',
            instruction=options.instruction,
        )
        
        # Wait for DOM to settle before extracting (matching observe handler)
        await page._wait_for_settled_dom()
        
        # Get page content based on content type
        page_content = await self._get_page_content(page, options.content_type)
        
        # Transform schema if needed (URL to ID mapping)
        transformed_schema, url_mappings = self._transform_schema(options.response_schema)
        
        # Build extraction prompt
        prompt = self._build_extract_prompt(
            page_content,
            transformed_schema,
            options.instruction
        )
        
        # Get LLM response
        try:
            # Get LLM client
            client = self.llm_provider.get_client(options.model_name)
            
            # Use generate_object for structured extraction
            extracted_data = await client.generate_object(
                prompt=prompt,
                schema=transformed_schema,
                temperature=0.1,  # Low temperature for consistent extraction
            )
            
            # Restore URLs if we did transformation
            if url_mappings:
                extracted_data = self._restore_urls(extracted_data, url_mappings)
            
            # Validate with original schema
            if hasattr(options.response_schema, 'model_validate'):
                validated_data = options.response_schema.model_validate(extracted_data)
            else:
                validated_data = extracted_data
            
            self._log_info("Extraction completed successfully")
            
            return ExtractResult(
                data=validated_data,
                metadata={
                    "url": page.url,
                    "content_type": options.content_type,
                    "had_url_transformation": bool(url_mappings),
                }
            )
            
        except Exception as e:
            self._log_error(f"Extraction failed: {e}", error=str(e))
            raise ExtractionFailedError(str(e), options.response_schema)
    
    async def _get_page_content(
        self,
        page: 'PlaywrightAIPage',
        content_type: str
    ) -> Dict[str, Any]:
        """Get page content based on content type."""
        self._log_debug(f"Getting page content with type: {content_type}")
        
        content = {
            "url": page.url,
            "title": await page.title(),
        }
        
        if content_type in ["text", "all"]:
            # Get visible text
            text = await get_page_text(page._page)
            content["text"] = clean_text(text)
        
        if content_type in ["dom", "all"]:
            # Get simplified DOM structure
            # For now, we'll use the page HTML
            html = await page.content()
            # In a real implementation, we'd build an accessibility tree
            content["html"] = html[:5000]  # Limit size
        
        return content
    
    def _transform_schema(
        self,
        schema: Any
    ) -> tuple[Any, Dict[int, str]]:
        """
        Transform schema to replace URL fields with numeric IDs.
        
        Args:
            schema: Original Pydantic schema
            
        Returns:
            Tuple of (transformed_schema, url_mappings)
        """
        # For now, return schema as-is
        # TODO: Implement URL transformation logic
        return schema, {}
    
    def _restore_urls(
        self,
        data: Any,
        url_mappings: Dict[int, str]
    ) -> Any:
        """Restore URLs from numeric IDs."""
        # TODO: Implement URL restoration
        return data
    
    def _build_extract_prompt(
        self,
        page_content: Dict[str, Any],
        schema: Any,
        instruction: Optional[str]
    ) -> str:
        """Build prompt for data extraction."""
        prompt = f"""Extract structured data from the following web page content.

Page URL: {page_content['url']}
Page Title: {page_content['title']}

"""
        
        # Add content based on what we have
        if "text" in page_content:
            prompt += f"Page Text Content:\n{page_content['text'][:2000]}\n\n"
        
        if "html" in page_content:
            prompt += f"HTML Structure (truncated):\n{page_content['html'][:1000]}\n\n"
        
        # Add instruction if provided
        if instruction:
            prompt += f"Extraction Instruction: {instruction}\n\n"
        
        # Add schema information
        if hasattr(schema, 'model_json_schema'):
            schema_info = schema.model_json_schema()
            prompt += f"Extract data matching this schema:\n{json.dumps(schema_info, indent=2)}\n\n"
        else:
            prompt += f"Extract data matching the schema: {schema}\n\n"
        
        prompt += """Extract the requested information from the page content. If a field cannot be found or determined from the content, use null or an appropriate default value.

Return the data as a valid JSON object matching the schema."""
        
        return prompt