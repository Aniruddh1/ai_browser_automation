#!/usr/bin/env python3
"""Debug iframe tree snapshots."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from playwright_ai import PlaywrightAI
from playwright_ai.a11y import get_accessibility_tree

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')


async def test_iframe_tree_snapshots():
    """Debug individual frame snapshots."""
    print("Testing iframe tree snapshots...")
    
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
        
        # Get main frame tree
        print("\n1. Main frame accessibility tree:")
        main_tree = await get_accessibility_tree(page)
        print(f"   Tree nodes: {len(main_tree['tree'])}")
        print(f"   Simplified tree preview:\n{main_tree['simplified'][:500]}...")
        
        # Get iframe element
        iframe_frame = page._page.main_frame.child_frames[0]
        print(f"\n2. Iframe URL: {iframe_frame.url}")
        
        # Get iframe tree
        print("\n3. Iframe accessibility tree:")
        iframe_tree = await get_accessibility_tree(page, target_frame=iframe_frame)
        print(f"   Tree nodes: {len(iframe_tree['tree'])}")
        print(f"   Simplified tree:\n{iframe_tree['simplified']}")
        
        # Compare the trees
        print("\n4. Comparison:")
        print(f"   Main tree == Iframe tree: {main_tree['simplified'] == iframe_tree['simplified']}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\nPress Enter to close browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_iframe_tree_snapshots())