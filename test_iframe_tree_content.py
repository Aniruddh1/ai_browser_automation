#!/usr/bin/env python3
"""Debug iframe tree content."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from playwright_ai import PlaywrightAI, ObserveOptions
from playwright_ai.a11y import get_accessibility_tree_with_frames

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')


async def test_iframe_tree_content():
    """Debug iframe tree content."""
    print("Testing iframe tree content...")
    
    # Initialize browser
    browser = PlaywrightAI(
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.environ.get("OPENAI_API_KEY")},
        headless=False,
        verbose=2
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        # Create test page with iframe
        iframe_html = """
        <html>
        <body>
            <h1>Main Page</h1>
            <button id="main-button">Main Button</button>
            <iframe id="test-iframe" src="data:text/html,
                <html><body>
                    <h2>Iframe Content</h2>
                    <button id='iframe-button'>Iframe Button</button>
                    <input type='text' placeholder='Type in iframe'>
                </body></html>" 
                width="400" height="200" style="border: 2px solid blue;">
            </iframe>
        </body>
        </html>
        """
        
        await page.goto(f"data:text/html,{iframe_html}")
        await page.wait_for_timeout(2000)  # Give iframe time to load
        
        # Get the combined tree with frames
        print("\nGetting accessibility tree with frames...")
        result = await get_accessibility_tree_with_frames(page)
        
        # Print the full combined tree
        print("\n=== FULL COMBINED TREE ===")
        print(result.get("combinedTree", ""))
        print("========================\n")
        
        # Print XPath mappings
        print("=== XPATH MAPPINGS ===")
        for encoded_id, xpath in result.get("combinedXpathMap", {}).items():
            print(f"  {encoded_id} -> {xpath}")
        print("========================\n")
        
        # Use observe with iframes to see what LLM gets
        print("\nRunning observe with iframes=True...")
        from playwright_ai.handlers.observe import ObserveHandler
        handler = ObserveHandler(
            playwright_ai=browser,
            ai_browser_automation_page=page,
            logger=browser._logger,
            options={}
        )
        
        # Get page info that would be sent to LLM
        page_info = await handler._gather_page_info(page, include_iframes=True)
        
        print("\n=== PAGE INFO SIMPLIFIED TREE ===")
        print(page_info.get("simplified", ""))
        print("========================\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\nPress Enter to close browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_iframe_tree_content())