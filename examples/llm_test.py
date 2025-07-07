"""Test LLM providers."""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

from playwright_ai import PlaywrightAI


async def test_with_api_key():
    """Test with real API key if available."""
    # Check for API keys
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_google = bool(os.getenv("GOOGLE_API_KEY"))
    
    print("API Key Status:")
    print(f"  OpenAI: {'[OK]' if has_openai else '[FAIL]'}")
    print(f"  Anthropic: {'[OK]' if has_anthropic else '[FAIL]'}")
    print(f"  Google: {'[OK]' if has_google else '[FAIL]'}")
    print()
    
    # Test with available providers
    if has_openai:
        print("Testing with OpenAI...")
        async with PlaywrightAI(
            headless=True,
            verbose=0,
            model_name="gpt-4o-mini",
            model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
        ) as browser:
            page = await browser.page()
            await page.goto("https://example.com")
            elements = await page.observe("Find links on the page")
            print(f"[OK] OpenAI found {len(elements)} elements")
    
    if has_anthropic:
        print("\nTesting with Anthropic...")
        async with PlaywrightAI(
            headless=True,
            verbose=0,
            model_name="claude-3-haiku",
            model_client_options={"api_key": os.getenv("ANTHROPIC_API_KEY")}
        ) as browser:
            page = await browser.page()
            await page.goto("https://example.com")
            elements = await page.observe("Find links on the page")
            print(f"[OK] Anthropic found {len(elements)} elements")
    
    if has_google:
        print("\nTesting with Google AI...")
        async with PlaywrightAI(
            headless=True,
            verbose=0,
            model_name="gemini-1.5-flash",
            model_client_options={"api_key": os.getenv("GOOGLE_API_KEY")}
        ) as browser:
            page = await browser.page()
            await page.goto("https://example.com")
            elements = await page.observe("Find links on the page")
            print(f"[OK] Google AI found {len(elements)} elements")
    
    if not (has_openai or has_anthropic or has_google):
        print("No API keys found. Testing with mock client...")
        async with PlaywrightAI(headless=True, verbose=0) as browser:
            page = await browser.page()
            await page.goto("https://example.com")
            elements = await page.observe("Find links on the page")
            print(f"[OK] Mock client found {len(elements)} elements")


async def test_mock_fallback():
    """Test that mock fallback works when no API key is provided."""
    print("\nTesting mock fallback (no API key)...")
    
    async with PlaywrightAI(
        headless=True,
        verbose=1,
        model_name="gpt-4o"  # Will use mock since no API key
    ) as browser:
        page = await browser.page()
        await page.goto("https://example.com")
        
        # Test observe
        elements = await page.observe()
        print(f"[OK] Mock observe: Found {len(elements)} elements")
        
        # Test act
        result = await page.act("Click the More information link")
        print(f"[OK] Mock act: {result.success}")
        
        # Test extract
        from pydantic import BaseModel
        
        class TestData(BaseModel):
            title: str
            url: str
        
        data = await page.extract(TestData)
        print(f"[OK] Mock extract: {data.data.title}")


async def main():
    """Run all tests."""
    print("Testing LLM Providers...\n")
    
    # Test with real API keys
    await test_with_api_key()
    
    # Test mock fallback
    await test_mock_fallback()
    
    print("\n[OK] All LLM provider tests completed!")


if __name__ == "__main__":
    asyncio.run(main())