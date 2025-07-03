"""Test self-healing functionality for act() method."""

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


async def test_self_healing():
    """Test self-healing functionality with intentionally failing actions."""
    print("Testing Self-Healing Functionality...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=2,  # More verbose logging
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as browser:
        page = await browser.page()
        
        print("1. Testing self-healing with a dynamic page:")
        print("-" * 50)
        
        # Go to a page with dynamic content
        await page.goto("https://example.com")
        
        # Test 1: Try to click something that doesn't exist (should trigger self-healing)
        result1 = await page.act("Click the 'Sign Up' button")
        print(f"Result 1 - Success: {result1.success}")
        if not result1.success:
            print(f"Error: {result1.error}")
        if hasattr(result1, 'metadata') and result1.metadata:
            print(f"Self-healing attempted: {result1.metadata.get('self_healing_attempted', False)}")
            print(f"Retry count: {result1.metadata.get('retry_count', 0)}")
        
        print("\n2. Testing navigation with new tab detection:")
        print("-" * 50)
        
        # Go to a page with links that open in new tabs
        await page.goto("https://www.w3schools.com")
        
        # Click a link that typically opens in a new tab
        result2 = await page.act("Click on 'Try it Yourself' or any example link")
        print(f"Result 2 - Success: {result2.success}")
        print(f"Current URL: {page.url}")
        
        print("\n3. Testing advanced click handling:")
        print("-" * 50)
        
        # Go back to example.com
        await page.goto("https://example.com")
        
        # Try to click the main link
        result3 = await page.act("Click on 'More information...' link")
        print(f"Result 3 - Success: {result3.success}")
        print(f"New URL: {page.url}")
        
        print("\n4. Testing with element that might be covered:")
        print("-" * 50)
        
        # Go to a more complex page
        await page.goto("https://github.com")
        
        # Try to click something that might be covered by overlays
        result4 = await page.act("Click the 'Sign in' button")
        print(f"Result 4 - Success: {result4.success}")
        if result4.success:
            print(f"Action: {result4.action}")
            print(f"Current URL: {page.url}")


async def test_click_methods():
    """Test different click methods."""
    print("\n\nTesting Different Click Methods...\n")
    
    async with AIBrowserAutomation(
        headless=False,
        verbose=1,
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as browser:
        page = await browser.page()
        
        # Create a test page with different click scenarios
        test_html = """
        <html>
        <body>
            <h1>Click Test Page</h1>
            
            <!-- Normal button -->
            <button id="normal-btn" onclick="document.getElementById('result').innerText='Normal button clicked'">
                Normal Button
            </button>
            
            <!-- Hidden button -->
            <button id="hidden-btn" style="display: none" onclick="document.getElementById('result').innerText='Hidden button clicked'">
                Hidden Button
            </button>
            
            <!-- Covered button -->
            <div style="position: relative">
                <button id="covered-btn" onclick="document.getElementById('result').innerText='Covered button clicked'">
                    Covered Button
                </button>
                <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.1);">
                    Overlay
                </div>
            </div>
            
            <!-- Link that opens in new tab -->
            <a href="https://example.com" target="_blank" id="new-tab-link">Open in New Tab</a>
            
            <p id="result">No button clicked yet</p>
        </body>
        </html>
        """
        
        await page.goto("data:text/html," + test_html)
        
        print("1. Testing normal button click:")
        result1 = await page.act("Click the 'Normal Button'")
        print(f"Success: {result1.success}")
        
        result_text = await page.locator("#result").inner_text()
        print(f"Result text: {result_text}")
        
        print("\n2. Testing hidden button click (should use advanced methods):")
        result2 = await page.act("Click the 'Hidden Button'")
        print(f"Success: {result2.success}")
        
        print("\n3. Testing covered button click:")
        result3 = await page.act("Click the 'Covered Button'")
        print(f"Success: {result3.success}")
        
        print("\n4. Testing new tab link:")
        initial_url = page.url
        result4 = await page.act("Click the 'Open in New Tab' link")
        print(f"Success: {result4.success}")
        print(f"URL changed: {page.url != initial_url}")
        print(f"New URL: {page.url}")


async def main():
    """Run all tests."""
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: No OpenAI API key found. Set OPENAI_API_KEY environment variable.")
        return
    
    await test_self_healing()
    await test_click_methods()
    
    print("\n[OK] Self-healing tests completed!")


if __name__ == "__main__":
    asyncio.run(main())