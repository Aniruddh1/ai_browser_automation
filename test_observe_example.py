#!/usr/bin/env python3
"""Test observe functionality on example.com."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from playwright_ai import PlaywrightAI

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')


async def test_observe_example():
    """Test observe on example.com."""
    print("Testing observe on example.com...\n")
    
    # Initialize browser
    browser = PlaywrightAI(
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.environ.get("OPENAI_API_KEY")},
        headless=False,
        verbose=2
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        # Navigate to example.com
        print("1. Navigating to example.com...")
        await page.goto("https://example.com")
        await page.wait_for_timeout(2000)
        
        # Get accessibility tree info
        from playwright_ai.a11y import get_accessibility_tree
        tree_result = await get_accessibility_tree(page)
        print(f"\n2. Accessibility tree info:")
        print(f"   Tree nodes: {len(tree_result['tree'])}")
        print(f"   Simplified tree:\n{tree_result['simplified']}")
        
        # Test observe with no arguments
        print("\n3. Testing observe() with no arguments...")
        results = await page.observe()
        print(f"   Found {len(results)} elements:")
        for i, result in enumerate(results):
            print(f"   [{i}] {result.selector} - {result.description}")
        
        # Test observe with specific instruction
        print("\n4. Testing observe('Find all links')...")
        results = await page.observe("Find all links")
        print(f"   Found {len(results)} links:")
        for i, result in enumerate(results):
            print(f"   [{i}] {result.selector} - {result.description}")
            
        # Test observe with broader instruction
        print("\n5. Testing observe('Find all interactive elements')...")
        results = await page.observe("Find all interactive elements including links, headings, and any other elements")
        print(f"   Found {len(results)} elements:")
        for i, result in enumerate(results):
            print(f"   [{i}] {result.selector} - {result.description}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\nPress Enter to close browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_observe_example())