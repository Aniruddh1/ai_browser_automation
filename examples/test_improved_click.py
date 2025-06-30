"""Test improved click handling on complex sites."""

from ai_browser_automation import AIBrowserAutomation
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_improved_clicks():
    """Test click actions on various sites with improved handling."""
    print("Testing Improved Click Handling...\n")
    
    async with AIBrowserAutomation(
        headless=False,
        verbose=2,
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        # Test 1: Simple site (should still work)
        print("1. Testing on simple site (example.com):")
        print("-" * 50)
        
        await page.goto("https://example.com")
        await page.wait_for_load_state("domcontentloaded")
        
        click_result = await page.act("Click the 'More information' link")
        print(f"Click result: {click_result.success}")
        if click_result.metadata:
            print(f"Method used: {click_result.metadata.get('method')}")
        print(f"Current URL: {page.url}")
        
        # Test 2: DuckDuckGo (previously problematic)
        print("\n2. Testing on DuckDuckGo:")
        print("-" * 50)
        
        await page.goto("https://duckduckgo.com")
        await page.wait_for_load_state("domcontentloaded")
        
        # Fill search
        fill_result = await page.act("Type 'Python programming' in the search box")
        print(f"Fill result: {fill_result.success}")
        
        await page.wait_for_timeout(1000)
        
        # Try clicking search button
        search_result = await page.act("Click the search button")
        print(f"Search click result: {search_result.success}")
        
        await page.wait_for_load_state("networkidle")
        print(f"New URL: {page.url}")
        
        # Test 3: Wikipedia (complex page structure)
        print("\n3. Testing on Wikipedia:")
        print("-" * 50)
        
        await page.goto("https://en.wikipedia.org/wiki/Python_(programming_language)")
        await page.wait_for_load_state("domcontentloaded")
        
        # Try clicking a link in the article
        link_result = await page.act("Click the 'object-oriented' link in the first paragraph")
        print(f"Link click result: {link_result.success}")
        
        await page.wait_for_load_state("networkidle")
        print(f"New URL: {page.url}")
        
        # Test 4: GitHub (dynamic content)
        print("\n4. Testing on GitHub:")
        print("-" * 50)
        
        await page.goto("https://github.com")
        await page.wait_for_load_state("domcontentloaded")
        
        # Try clicking Sign in
        signin_result = await page.act("Click the Sign in button")
        print(f"Sign in click result: {signin_result.success}")
        
        await page.wait_for_load_state("networkidle")
        print(f"New URL: {page.url}")
        
        # Test 5: Complex interactive site
        print("\n5. Testing on MDN Web Docs:")
        print("-" * 50)
        
        await page.goto("https://developer.mozilla.org")
        await page.wait_for_load_state("domcontentloaded")
        
        # Try interacting with the search
        search_click = await page.act("Click on the search box")
        print(f"Search box click result: {search_click.success}")
        
        if search_click.success:
            # Type in search
            type_result = await page.act("Type 'JavaScript arrays'")
            print(f"Type result: {type_result.success}")


async def main():
    """Run the improved click test."""
    if not os.getenv("OPENAI_API_KEY"):
        print("No OpenAI API key found. Set OPENAI_API_KEY environment variable.")
        return
    
    await test_improved_clicks()
    print("\n✓ Improved click test completed!")


if __name__ == "__main__":
    asyncio.run(main())