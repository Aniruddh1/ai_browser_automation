"""Test search functionality on a simpler site."""

from playwright_ai import PlaywrightAI
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()


async def test_simple_search():
    """Test search on a site without anti-automation measures."""
    print("Testing Search Functionality...\n")

    async with PlaywrightAI(
        headless=False,
        verbose=1,
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as browser:
        page = await browser.page()
        
        # Test on DuckDuckGo instead of Google
        print("1. Testing on DuckDuckGo:")
        print("-" * 50)
        
        await page.goto("https://duckduckgo.com")
        await page.wait_for_load_state("domcontentloaded")
        
        # Fill search box
        fill_result = await page.act("Fill the search box with 'PlaywrightAI browser automation'")
        print(f"Fill result: {fill_result.success}")
        if fill_result.metadata:
            print(f"Method: {fill_result.metadata.get('method')}")
            print(f"Arguments: {fill_result.metadata.get('arguments')}")
        
        await page.wait_for_timeout(1000)
        
        # Click search or press Enter
        search_result = await page.act("Click the search button or press Enter")
        print(f"Search result: {search_result.success}")
        
        await page.wait_for_load_state("networkidle")
        print(f"New URL: {page.url}")
        
        # Test on Wikipedia
        print("\n2. Testing on Wikipedia:")
        print("-" * 50)
        
        await page.goto("https://en.wikipedia.org")
        await page.wait_for_load_state("domcontentloaded")
        
        # Fill Wikipedia search
        wiki_fill = await page.act("Type 'Python programming language' in the search box")
        print(f"Fill result: {wiki_fill.success}")
        
        await page.wait_for_timeout(1000)
        
        # Submit search
        wiki_search = await page.act("Press Enter or click search")
        print(f"Search result: {wiki_search.success}")
        
        await page.wait_for_load_state("networkidle")
        print(f"New URL: {page.url}")
        
        # Test extraction on the result page
        print("\n3. Testing data extraction:")
        print("-" * 50)
        
        from pydantic import BaseModel
        
        class ArticleInfo(BaseModel):
            title: str
            first_paragraph: str
            has_infobox: bool
        
        extract_result = await page.extract(
            ArticleInfo,
            instruction="Extract the article title, first paragraph, and whether there's an infobox"
        )
        
        if extract_result.data:
            print(f"Title: {extract_result.data.title}")
            print(f"First paragraph: {extract_result.data.first_paragraph[:100]}...")
            print(f"Has infobox: {extract_result.data.has_infobox}")


async def main():
    """Run the test."""
    if not os.getenv("OPENAI_API_KEY"):
        print("No OpenAI API key found. Using mock LLM client.")
        print("Set OPENAI_API_KEY environment variable for real testing.")
        return
    
    await test_simple_search()
    print("\n[OK] Search test completed!")


if __name__ == "__main__":
    asyncio.run(main())