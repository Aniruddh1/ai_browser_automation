"""Test CDP-based XPath functionality."""

from ai_browser_automation import AIBrowserAutomation
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_cdp_xpath():
    """Test CDP-based XPath handling."""
    print("Testing CDP-based XPath Handling...\n")
    
    async with AIBrowserAutomation(
        headless=False,
        verbose=2,
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        # Test on example.com
        print("Testing on example.com:")
        print("-" * 50)
        
        await page.goto("https://example.com")
        await page.wait_for_load_state("domcontentloaded")
        
        # First observe to see what we get
        print("\n1. Observing page:")
        observe_results = await page.observe("Find the 'More information' link")
        
        if observe_results:
            for i, result in enumerate(observe_results):
                print(f"\nResult {i+1}:")
                print(f"  Selector: {result.selector}")
                print(f"  Description: {result.description}")
                print(f"  Encoded ID: {result.encoded_id}")
                print(f"  Attributes: {result.attributes}")
        else:
            print("No results found")
        
        # Now try to click
        print("\n2. Testing click action:")
        click_result = await page.act("Click the 'More information' link")
        print(f"Click result: {click_result.success}")
        if not click_result.success:
            print(f"Error: {click_result.error}")
        else:
            await page.wait_for_timeout(2000)
            print(f"Current URL: {page.url}")


async def main():
    """Run the CDP test."""
    if not os.getenv("OPENAI_API_KEY"):
        print("No OpenAI API key found. Set OPENAI_API_KEY environment variable.")
        return
    
    await test_cdp_xpath()
    print("\n✓ CDP XPath test completed!")


if __name__ == "__main__":
    asyncio.run(main())