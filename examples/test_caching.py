"""Test caching functionality."""

from ai_browser_automation import AIBrowserAutomation
import asyncio
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()


async def test_caching():
    """Test caching functionality with repeated actions."""
    print("Testing Caching System...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=2,  # More logs to see caching
        enable_caching=True,  # Enable caching
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        await page.goto("https://www.google.com")

        print("1. First action - should call LLM:")
        print("-" * 50)
        
        start_time = time.time()
        result1 = await page.act("Click on the search box")
        end_time = time.time()
        
        print(f"Result: {result1.success}")
        print(f"Time taken: {end_time - start_time:.2f}s")
        print(f"Action: {result1.action}")
        
        # Wait a bit
        await page.wait_for_timeout(1000)

        print("\n2. Same action again - should use cache:")
        print("-" * 50)
        
        # Navigate back to same state
        await page.goto("https://www.google.com")
        
        start_time = time.time()
        result2 = await page.act("Click on the search box")
        end_time = time.time()
        
        print(f"Result: {result2.success}")
        print(f"Time taken: {end_time - start_time:.2f}s (should be faster)")
        print(f"Action: {result2.action}")

        print("\n3. Testing observe with caching:")
        print("-" * 50)
        
        start_time = time.time()
        elements1 = await page.observe()
        end_time = time.time()
        
        print(f"Found {len(elements1)} elements")
        print(f"Time taken: {end_time - start_time:.2f}s")
        
        print("\n4. Same observe again - should use cache:")
        print("-" * 50)
        
        start_time = time.time()
        elements2 = await page.observe()
        end_time = time.time()
        
        print(f"Found {len(elements2)} elements")
        print(f"Time taken: {end_time - start_time:.2f}s (should be faster)")

        print("\n5. Testing extract with caching:")
        print("-" * 50)
        
        from pydantic import BaseModel
        
        class PageInfo(BaseModel):
            title: str
            has_search_box: bool
            button_count: int
        
        start_time = time.time()
        info1 = await page.extract(PageInfo)
        end_time = time.time()
        
        print(f"Extracted: {info1.data}")
        print(f"Time taken: {end_time - start_time:.2f}s")
        
        print("\n6. Same extract again - should use cache:")
        print("-" * 50)
        
        start_time = time.time()
        info2 = await page.extract(PageInfo)
        end_time = time.time()
        
        print(f"Extracted: {info2.data}")
        print(f"Time taken: {end_time - start_time:.2f}s (should be faster)")


async def test_caching_disabled():
    """Test that caching can be disabled."""
    print("\n\nTesting with caching disabled...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=1,
        enable_caching=False,  # Disable caching
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        await page.goto("https://www.google.com")

        print("1. First action - should call LLM:")
        print("-" * 50)
        
        start_time = time.time()
        result1 = await page.act("Click on the search box")
        end_time = time.time()
        
        print(f"Time taken: {end_time - start_time:.2f}s")

        print("\n2. Same action again - should call LLM again (no cache):")
        print("-" * 50)
        
        await page.goto("https://www.google.com")
        
        start_time = time.time()
        result2 = await page.act("Click on the search box")
        end_time = time.time()
        
        print(f"Time taken: {end_time - start_time:.2f}s (should be similar to first time)")


async def main():
    """Run the tests."""
    if not os.getenv("OPENAI_API_KEY"):
        print("No OpenAI API key found. Using mock LLM client.")
        print("Set OPENAI_API_KEY environment variable for real testing.")
        print("Note: Mock client won't demonstrate real caching benefits.\n")

    await test_caching()
    await test_caching_disabled()
    
    print("\n✓ Caching tests completed!")
    
    # Check cache files
    cache_dir = Path.cwd() / "tmp" / ".cache"
    if cache_dir.exists():
        cache_files = list(cache_dir.glob("*.json"))
        print(f"\nCache files created: {len(cache_files)}")
        for f in cache_files:
            print(f"  - {f.name}")


if __name__ == "__main__":
    asyncio.run(main())