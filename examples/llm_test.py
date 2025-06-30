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

from ai_browser_automation import AIBrowserAutomation


async def test_with_api_key():
    """Test with real API key if available."""
    # Check for API keys
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_google = bool(os.getenv("GOOGLE_API_KEY"))
    
    print("API Key Status:")
    print(f"  OpenAI: {'✓' if has_openai else '✗'}")
    print(f"  Anthropic: {'✓' if has_anthropic else '✗'}")
    print(f"  Google: {'✓' if has_google else '✗'}")
    print()
    
    # Test with available providers
    if has_openai:
        print("Testing with OpenAI...")
        async with AIBrowserAutomation(
            headless=True,
            verbose=0,
            model_name="gpt-4o-mini",
            model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
        ) as stagehand:
            page = await stagehand.page()
            await page.goto("https://example.com")
            elements = await page.observe("Find links on the page")
            print(f"✓ OpenAI found {len(elements)} elements")
    
    if has_anthropic:
        print("\nTesting with Anthropic...")
        async with AIBrowserAutomation(
            headless=True,
            verbose=0,
            model_name="claude-3-haiku",
            model_client_options={"api_key": os.getenv("ANTHROPIC_API_KEY")}
        ) as stagehand:
            page = await stagehand.page()
            await page.goto("https://example.com")
            elements = await page.observe("Find links on the page")
            print(f"✓ Anthropic found {len(elements)} elements")
    
    if has_google:
        print("\nTesting with Google AI...")
        async with AIBrowserAutomation(
            headless=True,
            verbose=0,
            model_name="gemini-1.5-flash",
            model_client_options={"api_key": os.getenv("GOOGLE_API_KEY")}
        ) as stagehand:
            page = await stagehand.page()
            await page.goto("https://example.com")
            elements = await page.observe("Find links on the page")
            print(f"✓ Google AI found {len(elements)} elements")
    
    if not (has_openai or has_anthropic or has_google):
        print("No API keys found. Testing with mock client...")
        async with AIBrowserAutomation(headless=True, verbose=0) as stagehand:
            page = await stagehand.page()
            await page.goto("https://example.com")
            elements = await page.observe("Find links on the page")
            print(f"✓ Mock client found {len(elements)} elements")


async def test_mock_fallback():
    """Test that mock fallback works when no API key is provided."""
    print("\nTesting mock fallback (no API key)...")
    
    async with AIBrowserAutomation(
        headless=True,
        verbose=1,
        model_name="gpt-4o"  # Will use mock since no API key
    ) as stagehand:
        page = await stagehand.page()
        await page.goto("https://example.com")
        
        # Test observe
        elements = await page.observe()
        print(f"✓ Mock observe: Found {len(elements)} elements")
        
        # Test act
        result = await page.act("Click the More information link")
        print(f"✓ Mock act: {result.success}")
        
        # Test extract
        from pydantic import BaseModel
        
        class TestData(BaseModel):
            title: str
            url: str
        
        data = await page.extract(TestData)
        print(f"✓ Mock extract: {data.data.title}")


async def main():
    """Run all tests."""
    print("Testing LLM Providers...\n")
    
    # Test with real API keys
    await test_with_api_key()
    
    # Test mock fallback
    await test_mock_fallback()
    
    print("\n✓ All LLM provider tests completed!")


if __name__ == "__main__":
    asyncio.run(main())