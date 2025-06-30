#!/usr/bin/env python3
"""Debug observe functionality with detailed logging."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from ai_browser_automation import AIBrowserAutomation

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')


async def debug_observe():
    """Debug observe with detailed logging."""
    print("Debugging observe functionality...")
    print(f"OpenAI API key loaded: {'OPENAI_API_KEY' in os.environ}")
    print(f"API key starts with: {os.environ.get('OPENAI_API_KEY', '')[:20]}...")
    
    # Initialize browser with OpenAI
    browser = AIBrowserAutomation(
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.environ.get("OPENAI_API_KEY")},
        headless=False,
        verbose=2  # Maximum verbosity
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        # Navigate to a simple page
        print("\nLoading example.com...")
        await page.goto("https://example.com")
        await page.wait_for_timeout(2000)
        
        # Check if LLM provider is configured
        print(f"\nLLM Provider: {browser.llm_provider}")
        print(f"LLM Provider type: {type(browser.llm_provider)}")
        
        # Simple observation
        print("\nRunning simple observe...")
        observations = await page.observe("Find the main heading")
        
        print(f"\nObservations found: {len(observations)}")
        if len(observations) == 0:
            print("No observations found - checking page content...")
            
            # Try to get page content
            content = await page.content()
            print(f"Page content length: {len(content)}")
            print("Page title:", await page.title())
            
            # Check accessibility tree directly
            from ai_browser_automation.a11y import get_accessibility_tree
            tree_result = await get_accessibility_tree(page)
            print(f"\nAccessibility tree nodes: {len(tree_result['tree'])}")
            print(f"Simplified tree length: {len(tree_result['simplified'])}")
            print("\nFirst 500 chars of simplified tree:")
            print(tree_result['simplified'][:500])
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_observe())