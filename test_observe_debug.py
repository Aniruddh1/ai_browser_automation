#!/usr/bin/env python3
"""Debug script to test observe functionality."""

import asyncio
from playwright_ai import PlaywrightAI


async def test_observe_debug():
    """Debug observe functionality."""
    print("Starting observe debug test...")
    
    # Initialize browser
    browser = PlaywrightAI(
        model_name="gpt-4o-mini",
        headless=False,
        verbose=2  # Enable debug logging
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        # Test on a simple page
        print("\n1. Testing on example.com...")
        await page.goto("https://example.com")
        await page.wait_for_timeout(2000)  # Wait for page to settle
        
        # Try basic observe
        print("\n2. Running basic observe...")
        observations = await page.observe("Find all links and headings")
        
        print(f"\nFound {len(observations)} observations:")
        for i, obs in enumerate(observations):
            print(f"{i+1}. Role: {obs.role}")
            print(f"   Name: {obs.name}")
            print(f"   Selector: {obs.selector}")
            print(f"   Description: {obs.description}")
            print()
        
        # Test with a page that has more elements
        print("\n3. Testing on wikipedia.org...")
        await page.goto("https://www.wikipedia.org")
        await page.wait_for_timeout(2000)
        
        observations = await page.observe("Find the search input")
        print(f"\nFound {len(observations)} search-related elements")
        
        for obs in observations:
            print(f"- {obs.role}: {obs.name} ({obs.selector})")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        print("\nTest completed.")


if __name__ == "__main__":
    asyncio.run(test_observe_debug())