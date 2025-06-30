"""Test Google search with fill and click actions."""

from ai_browser_automation import AIBrowserAutomation
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()


async def test_google_search():
    """Test Google search functionality."""
    print("Testing Google Search with AIBrowserAutomation...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=1,  # Show some logs
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as browser:
        page = await browser.page()
        await page.goto("https://www.youtube.com")

        print("1. Testing fill action with quoted text:")
        print("-" * 50)

        # Test 1: Fill with quoted text
        fill_result = await page.act("Fill the search box with 'AIBrowserAutomation Python automation'")
        print(f"Fill result: {fill_result.success}")
        print(f"Action: {fill_result.action}")
        print(f"Description: {fill_result.description}")
        if hasattr(fill_result, 'metadata') and fill_result.metadata:
            print(f"Method used: {fill_result.metadata.get('method')}")
            print(f"Arguments: {fill_result.metadata.get('arguments')}")

        # Wait a bit to see the result
        await page.wait_for_timeout(1000)

        print("\n2. Testing click action on search button:")
        print("-" * 50)

        # Test 2: Click search button or press Enter
        click_result = await page.act("Click the search button or press Enter")
        print(f"Click result: {click_result.success}")
        print(f"Action: {click_result.action}")
        if hasattr(click_result, 'metadata') and click_result.metadata:
            print(f"Method used: {click_result.metadata.get('method')}")

        # Wait for search results
        await page.wait_for_load_state("networkidle")

        print(f"\nNew URL: {page.url}")

        print("\n3. Testing another search:")
        print("-" * 50)

        # Go back to Google
        await page.goto("https://www.google.com")

        # Test 3: Another fill action
        fill_result2 = await page.act("Type 'Playwright Python tutorial' in the search field")
        print(f"Fill result: {fill_result2.success}")
        print(f"Action: {fill_result2.action}")

        # Press Enter instead of clicking
        enter_result = await page.act("Press Enter")
        print(f"Enter result: {enter_result.success}")

        await page.wait_for_load_state("networkidle")
        print(f"Final URL: {page.url}")


async def main():
    """Run the test."""
    if not os.getenv("OPENAI_API_KEY"):
        print("No OpenAI API key found. Using mock LLM client.")
        print("Set OPENAI_API_KEY environment variable for real testing.")

    await test_google_search()
    print("\n[OK] YouTube search test completed!")


if __name__ == "__main__":
    asyncio.run(main())
