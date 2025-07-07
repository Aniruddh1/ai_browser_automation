#!/usr/bin/env python3
"""Test observe with real page and real LLM."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from playwright_ai import PlaywrightAI

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')


async def test_real_observe():
    """Test observe with real page."""
    print("Testing real observe functionality...")
    
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
        # Test on a real page with clear elements
        print("\nLoading a page with clear elements...")
        test_html = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Main Heading</h1>
            <p>This is a paragraph of text.</p>
            <button id="submit-btn">Submit</button>
            <a href="https://example.com">Example Link</a>
            <input type="text" placeholder="Enter text here">
        </body>
        </html>
        """
        
        await page.goto(f"data:text/html,{test_html}")
        await page.wait_for_timeout(1000)
        
        # Get the accessibility tree directly first
        from playwright_ai.a11y import get_accessibility_tree
        tree_result = await get_accessibility_tree(page)
        print(f"\nAccessibility tree has {len(tree_result['tree'])} nodes")
        print("\nSimplified tree:")
        print(tree_result['simplified'])
        
        # Now test observe
        print("\n\nTesting observe('Find the heading')...")
        observations = await page.observe("Find the heading")
        print(f"Found {len(observations)} observations")
        
        for i, obs in enumerate(observations):
            print(f"\n{i+1}. Observation:")
            print(f"   Type: {type(obs)}")
            print(f"   Selector: {obs.selector if hasattr(obs, 'selector') else 'No selector'}")
            print(f"   Description: {obs.description if hasattr(obs, 'description') else 'No description'}")
            if hasattr(obs, 'role'):
                print(f"   Role: {obs.role}")
            if hasattr(obs, 'name'):
                print(f"   Name: {obs.name}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\nPress Enter to close browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_real_observe())