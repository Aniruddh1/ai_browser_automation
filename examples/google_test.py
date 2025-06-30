"""Test OpenAI provider with detailed output."""

from ai_browser_automation import AIBrowserAutomation
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()


class WebsiteData(BaseModel):
    title: str
    main_heading: str
    paragraph_count: int
    link_texts: list[str]
    is_example_domain: bool


async def test_openai_detailed():
    """Test OpenAI with detailed output."""
    print("Testing OpenAI Provider in Detail...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=1,  # Show some logs
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as browser:
        page = await browser.page()
        await page.goto("https://www.google.com")

        print("1. Testing Observe with OpenAI:")
        print("-" * 50)
        elements = await page.observe("Find all interactive elements on the page")
        print(f"Found {len(elements)} elements:")
        for elem in elements:
            print(f"  - {elem.selector}: {elem.description}")
            if elem.action:
                print(f"    Suggested action: {elem.action}")

        print("\n2. Testing Extract with OpenAI:")
        print("-" * 50)
        result = await page.extract(
            WebsiteData,
            instruction="Extract detailed information about this website"
        )
        print(f"Extracted data:")
        print(f"  Title: {result.data.title}")
        print(f"  Main heading: {result.data.main_heading}")
        print(f"  Paragraph count: {result.data.paragraph_count}")
        print(f"  Links: {result.data.link_texts}")
        print(f"  Is example domain: {result.data.is_example_domain}")

        print("\n3. Testing Act with OpenAI:")
        print("-" * 50)
        act_result = await page.act("Fill the search box with 'AIBrowserAutomation Python' and click the search button")
        print(f"Action result: {act_result.success}")
        print(f"Action type: {act_result.action}")
        print(f"Description: {act_result.description}")

        # Check new page
        await page.wait_for_load_state("domcontentloaded")
        new_url = page.url
        print(f"New URL: {new_url}")

        print("\n4. Testing Observe on new page:")
        print("-" * 50)
        new_elements = await page.observe("Find the main content sections")
        print(f"Found {len(new_elements)} elements on the new page")


async def main():
    """Run the test."""
    if not os.getenv("OPENAI_API_KEY"):
        print("No OpenAI API key found. Please set OPENAI_API_KEY environment variable.")
        return

    await test_openai_detailed()
    print("\n[OK] Google test completed!")


if __name__ == "__main__":
    asyncio.run(main())
