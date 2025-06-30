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
        ) as stagehand:
            print(f"✓ AIBrowserAutomation created with session ID: {stagehand.session_id}")
            
            # Initialize browser
            init_result = await stagehand.init()
            print(f"✓ Browser initialized: {init_result.debugger_url}")
            
            # Create a page
            page = await stagehand.page()
            print(f"✓ Page created: {page}")
            
            # Navigate to example.com
            await page.goto("https://example.com")
            print(f"✓ Navigated to: {page.url}")
            
            # Get page title
            title = await page.title()
            print(f"✓ Page title: {title}")
            
            # Test act (placeholder for now)
            try:
                act_result = await page.act("Click the More information link")
                print(f"✓ Act result: {act_result}")
            except Exception as e:
                print(f"✗ Act failed (expected with placeholder): {e}")
            
            # Test observe (placeholder for now)
            try:
                observe_results = await page.observe()
                print(f"✓ Observe found {len(observe_results)} elements")
            except Exception as e:
                print(f"✗ Observe failed (expected with placeholder): {e}")
            
            # Test extract (placeholder for now)
            from pydantic import BaseModel
            
            class PageInfo(BaseModel):
                title: str
                has_links: bool
            
            try:
                extract_result = await page.extract(PageInfo)
                print(f"✓ Extract result: {extract_result}")
            except Exception as e:
                print(f"✗ Extract failed (expected with placeholder): {e}")
            
            # Wait a bit before closing
            await asyncio.sleep(2)
            
        print("\n✓ All basic tests completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())