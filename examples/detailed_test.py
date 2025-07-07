"""Detailed test to debug the observe handler."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright_ai import PlaywrightAI
from playwright_ai.llm.mock_client import MockLLMClient
from playwright_ai.types import LLMMessage
from playwright_ai.utils.logger import configure_logging, PlaywrightAILogger


async def main():
    """Test handlers in detail."""
    print("Detailed handler testing...\n")
    
    # First test the mock client directly
    logger = PlaywrightAILogger(configure_logging(0), 0)  # Quiet logging
    mock_client = MockLLMClient("gpt-4o", None, logger)
    
    print("1. Testing Mock LLM Client directly:")
    print("-" * 50)
    
    # Test observe-like prompt
    prompt = "Analyze the following web page and identify interactive elements."
    response = await mock_client.create_chat_completion([
        LLMMessage(role="user", content=prompt)
    ])
    content = response.choices[0].message.content
    print(f"Prompt: {prompt[:50]}...")
    print(f"Response type: {type(content)}")
    print(f"Response content: {content[:200]}")
    print()
    
    # Now test with PlaywrightAI
    print("\n2. Testing with PlaywrightAI:")
    print("-" * 50)
    
    async with PlaywrightAI(headless=True, verbose=1) as browser:
        page = await browser.page()
        await page.goto("https://example.com")
        
        # Test observe
        print("\nTesting observe():")
        elements = await page.observe()
        print(f"Found {len(elements)} elements")
        
        if elements:
            for i, elem in enumerate(elements[:3]):
                print(f"  {i+1}. {elem.selector} - {elem.description}")
        else:
            # Let's debug what's happening
            print("\nDebugging: Let's check what the handler is doing...")
            
            # Get the handler directly
            from playwright_ai.handlers import ObserveHandler
            handler = ObserveHandler(
                logger=browser.logger.child(component="page"),
                llm_provider=browser.llm_provider
            )
            
            # Get page info
            from playwright_ai.dom import get_clickable_elements
            clickable = await get_clickable_elements(page._page)
            print(f"\nActual clickable elements on page: {len(clickable)}")
            for elem in clickable[:3]:
                print(f"  - {elem['tagName']} | {elem.get('text', '')[:30]}")


if __name__ == "__main__":
    asyncio.run(main())