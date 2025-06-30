"""Test XPath click handling."""

from ai_browser_automation import AIBrowserAutomation
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_xpath_click():
    """Test XPath-based click handling."""
    print("Testing XPath Click Handling...\n")
    
    async with AIBrowserAutomation(
        headless=False,
        verbose=2,
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        # Test on a simple page
        print("Testing on example.com:")
        print("-" * 50)
        
        await page.goto("https://example.com")
        await page.wait_for_load_state("domcontentloaded")
        
        # First, let's observe what elements are found
        observe_result = await page.observe("Find the 'More information' link")
        print(f"Found {len(observe_result)} elements")
        if observe_result:
            print(f"First element selector: {observe_result[0].selector}")
            print(f"First element method: {observe_result[0].method}")
            print(f"First element arguments: {observe_result[0].arguments}")
        
        # Now try to click
        click_result = await page.act("Click the 'More information' link")
        print(f"Click result: {click_result.success}")
        if not click_result.success:
            print(f"Error: {click_result.error}")
        
        await page.wait_for_timeout(2000)
        print(f"Current URL: {page.url}")


async def main():
    """Run the XPath test."""
    if not os.getenv("OPENAI_API_KEY"):
        print("No OpenAI API key found. Set OPENAI_API_KEY environment variable.")
        return
    
    await test_xpath_click()
    print("\n✓ XPath test completed!")


if __name__ == "__main__":
    asyncio.run(main())