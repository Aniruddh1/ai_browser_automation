#!/usr/bin/env python3
"""Test iframe button detection clearly."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from playwright_ai import PlaywrightAI, ObserveOptions

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')


async def test_iframe_buttons():
    """Test iframe button detection."""
    print("Testing iframe button detection...\n")
    
    # Initialize browser
    browser = PlaywrightAI(
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.environ.get("OPENAI_API_KEY")},
        headless=False,
        verbose=1
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        # Create test page with buttons in both main frame and iframe
        test_html = """
        <html>
        <body>
            <h1>Main Frame</h1>
            <button id="main-button-1">Main Button 1</button>
            <button id="main-button-2">Main Button 2</button>
            
            <iframe src="data:text/html,
                <html><body>
                    <h2>Iframe Content</h2>
                    <button id='iframe-button-1'>Iframe Button 1</button>
                    <button id='iframe-button-2'>Iframe Button 2</button>
                    <button id='iframe-button-3'>Iframe Button 3</button>
                </body></html>" 
                width="400" height="200" style="border: 2px solid blue;">
            </iframe>
        </body>
        </html>
        """
        
        await page.goto(f"data:text/html,{test_html}")
        await page.wait_for_timeout(2000)
        
        # Test without iframe support
        print("1. Observing WITHOUT iframe support:")
        observations = await page.observe("Find all buttons")
        print(f"   Found {len(observations)} buttons:")
        for obs in observations:
            if "button" in obs.description.lower():
                print(f"   - {obs.description}")
        
        print("\n2. Observing WITH iframe support:")
        observations = await page.observe(
            ObserveOptions(
                instruction="Find all buttons",
                iframes=True
            )
        )
        print(f"   Found {len(observations)} buttons:")
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
    asyncio.run(test_iframe_buttons())