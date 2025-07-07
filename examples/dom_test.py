"""Test DOM utilities directly."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright_ai import PlaywrightAI
from playwright_ai.dom import get_clickable_elements, get_input_elements, get_page_text


async def main():
    """Test DOM utilities."""
    print("Testing DOM utilities...")
    
    try:
        # Create PlaywrightAI instance
        async with PlaywrightAI(headless=False, verbose=1) as browser:
            # Create a page
            page = await browser.page()
            
            # Navigate to example.com
            await page.goto("https://example.com")
            await page.wait_for_load_state("domcontentloaded")
            
            print(f"\nPage loaded: {page.url}")
            
            # Test clickable elements
            print("\n--- Clickable Elements ---")
            clickable = await get_clickable_elements(page._page)
            print(f"Found {len(clickable)} clickable elements")
            for elem in clickable[:5]:
                print(f"  - {elem['tagName']} | {elem.get('text', '')[:50]} | {elem.get('selector', '')}")
            
            # Test input elements
            print("\n--- Input Elements ---")
            inputs = await get_input_elements(page._page)
            print(f"Found {len(inputs)} input elements")
            for elem in inputs[:5]:
                print(f"  - {elem['tagName']} | type={elem.get('type', '')} | {elem.get('selector', '')}")
            
            # Test page text
            print("\n--- Page Text (first 500 chars) ---")
            text = await get_page_text(page._page)
            print(text[:500])
            
            # Wait before closing
            await asyncio.sleep(2)
            
        print("\n[OK] DOM utility tests completed!")
        
    except Exception as e:
        print(f"\n[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())