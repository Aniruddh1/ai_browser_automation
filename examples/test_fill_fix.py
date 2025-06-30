"""Quick test to verify fill action fix."""

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


async def test_fill_fix():
    """Test that fill actions work correctly."""
    print("Testing Fill Action Fix...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=2,  # Show detailed logs
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()

        # Test on a simple form page
        await page.goto("https://www.w3schools.com/html/html_forms.asp")
        await page.wait_for_load_state("domcontentloaded")

        print("Testing fill with specific text:")
        print("-" * 50)

        # Test fill action
        result = await page.act("Fill the first name field with 'Aniruddh'")
        print(f"Success: {result.success}")
        print(f"Action: {result.action}")
        print(f"Description: {result.description}")
        if result.metadata:
            print(f"Method: {result.metadata.get('method')}")
            print(f"Arguments: {result.metadata.get('arguments')}")

        # Wait to see the result
        await page.wait_for_timeout(2000)

        # Test another fill
        print("\nTesting another fill:")
        print("-" * 50)

        result2 = await page.act("Type 'Doe' in the last name field")
        print(f"Success: {result2.success}")
        print(f"Action: {result2.action}")
        if result2.metadata:
            print(f"Method: {result2.metadata.get('method')}")
            print(f"Arguments: {result2.metadata.get('arguments')}")

        await page.wait_for_timeout(2000)


async def main():
    """Run the test."""
    if not os.getenv("OPENAI_API_KEY"):
        print("No OpenAI API key found. Using mock LLM client.")
        print("Set OPENAI_API_KEY environment variable for real testing.")
        return

    await test_fill_fix()
    print("\n✓ Fill action test completed!")


if __name__ == "__main__":
    asyncio.run(main())
