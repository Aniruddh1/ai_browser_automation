"""Basic test of AIBrowserAutomation Python implementation."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_browser_automation import AIBrowserAutomation


async def main():
    """Test basic AIBrowserAutomation functionality."""
    print("Testing AIBrowserAutomation Python implementation...")
    
    try:
        # Create AIBrowserAutomation instance
        async with AIBrowserAutomation(
            headless=False,
            verbose=2,
            enable_caching=True,
        ) as browser:
            print(f"[OK] AIBrowserAutomation created with session ID: {browser.session_id}")
            
            # Initialize browser
            init_result = await browser.init()
            print(f"[OK] Browser initialized: {init_result.debugger_url}")
            
            # Create a page
            page = await browser.page()
            print(f"[OK] Page created: {page}")
            
            # Navigate to example.com
            await page.goto("https://example.com")
            print(f"[OK] Navigated to: {page.url}")
            
            # Get page title
            title = await page.title()
            print(f"[OK] Page title: {title}")
            
            # Test act (placeholder for now)
            try:
                act_result = await page.act("Click the More information link")
                print(f"[OK] Act result: {act_result}")
            except Exception as e:
                print(f"[FAIL] Act failed (expected with placeholder): {e}")
            
            # Test observe (placeholder for now)
            try:
                observe_results = await page.observe()
                print(f"[OK] Observe found {len(observe_results)} elements")
            except Exception as e:
                print(f"[FAIL] Observe failed (expected with placeholder): {e}")
            
            # Test extract (placeholder for now)
            from pydantic import BaseModel
            
            class PageInfo(BaseModel):
                title: str
                has_links: bool
            
            try:
                extract_result = await page.extract(PageInfo)
                print(f"[OK] Extract result: {extract_result}")
            except Exception as e:
                print(f"[FAIL] Extract failed (expected with placeholder): {e}")
            
            # Wait a bit before closing
            await asyncio.sleep(2)
            
        print("\n[OK] All basic tests completed successfully!")
        
    except Exception as e:
        print(f"\n[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())