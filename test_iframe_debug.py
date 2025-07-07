#!/usr/bin/env python3
"""Debug iframe support."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from playwright_ai import PlaywrightAI, ObserveOptions

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')


async def test_iframe_debug():
    """Debug iframe support."""
    print("Testing iframe support...")
    
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
        
        # Test 1: Get accessibility tree without frames
        print("\n1. Testing without iframe support...")
        from playwright_ai.a11y import get_accessibility_tree
        tree_result = await get_accessibility_tree(page)
        print(f"   Tree nodes: {len(tree_result['tree'])}")
        print(f"   Iframes found: {len(tree_result.get('iframes', []))}")
        
        # Test 2: Get accessibility tree with frames
        print("\n2. Testing with iframe support...")
        from playwright_ai.a11y import get_accessibility_tree_with_frames
        try:
            frames_result = await get_accessibility_tree_with_frames(page)
            print(f"   Combined tree length: {len(frames_result.get('combinedTree', ''))}")
            print(f"   Combined XPath map entries: {len(frames_result.get('combinedXpathMap', {}))}")
            
            # Print part of the combined tree
            print("\n   Combined tree preview:")
            tree_lines = frames_result.get('combinedTree', '').split('\n')[:10]
            for line in tree_lines:
                print(f"   {line}")
                
        except Exception as e:
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 3: Observe without iframe support
        print("\n3. Observing without iframe support...")
        observations = await page.observe("Find all buttons")
        print(f"   Found {len(observations)} buttons")
        for obs in observations:
            if "button" in obs.description.lower():
                print(f"   - {obs.description}")
        
        # Test 4: Observe with iframe support
        print("\n4. Observing with iframe support...")
        observations = await page.observe(
            ObserveOptions(
                instruction="Find all buttons including in iframes",
                iframes=True
            )
        )
        print(f"   Found {len(observations)} buttons")
        for obs in observations:
            if "button" in obs.description.lower():
                print(f"   - {obs.description}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\nPress Enter to close browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_iframe_debug())