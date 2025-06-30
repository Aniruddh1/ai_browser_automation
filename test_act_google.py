#!/usr/bin/env python3
"""Test act functionality on Google search."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from ai_browser_automation import AIBrowserAutomation

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')


async def test_act_google():
    """Test act functionality on Google search."""
    print("Testing act functionality on Google search...\n")
    
    # Initialize browser
    browser = AIBrowserAutomation(
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.environ.get("OPENAI_API_KEY")},
        headless=False,
        verbose=1
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        # Navigate to Google
        print("1. Navigating to Google...")
        await page.goto("https://www.google.com")
        await page.wait_for_timeout(2000)
        
        # Test filling search box
        print("\n2. Testing fill action...")
        result = await page.act('fill the search box with "OpenAI GPT-4"')
        print(f"   Fill successful: {result.success}")
        if result.success:
            print(f"   Action: {result.action}")
            print(f"   Description: {result.description}")
            print(f"   Selector: {result.selector}")
        
        await page.wait_for_timeout(2000)
        
        # Test clicking search button
        print("\n3. Testing click action...")
        result = await page.act("click the search button")
        print(f"   Click successful: {result.success}")
        if result.success:
            print(f"   Action: {result.action}")
            print(f"   Description: {result.description}")
        
        await page.wait_for_timeout(3000)
        
        print(f"\n4. Final URL: {page.url}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\nPress Enter to close browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_act_google())