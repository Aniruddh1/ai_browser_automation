#!/usr/bin/env python3
"""Test with real LLM to verify observe functionality."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from ai_browser_automation import AIBrowserAutomation, ObserveOptions

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')


async def test_with_real_llm():
    """Test observe with real OpenAI API."""
    print("Testing with real LLM...")
    print(f"OpenAI API key loaded: {'OPENAI_API_KEY' in os.environ}")
    
    # Initialize browser with OpenAI
    browser = AIBrowserAutomation(
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.environ.get("OPENAI_API_KEY")},
        headless=False,
        verbose=1  # Show some logs but not all
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        # Test 1: Simple page observation
        print("\n1. Testing on example.com...")
        await page.goto("https://example.com")
        await page.wait_for_timeout(2000)
        
        observations = await page.observe("Find all clickable elements and headings")
        print(f"\nFound {len(observations)} observations on example.com:")
        
        for i, obs in enumerate(observations[:5]):  # Show first 5
            print(f"\n{i+1}. Element")
            print(f"   Description: {obs.description}")
            print(f"   Selector: {obs.selector}")
            if hasattr(obs, 'method') and obs.method:
                print(f"   Method: {obs.method}")
            
            # Verify selector format
            if not obs.selector.startswith("xpath="):
                print(f"   ⚠️  WARNING: Selector doesn't start with 'xpath=': {obs.selector}")
        
        # Test 2: Page with forms
        print("\n\n2. Testing on a form page...")
        form_html = """
        <html>
        <head><title>Test Form</title></head>
        <body>
            <h1>Contact Form</h1>
            <form>
                <label for="name">Name:</label>
                <input type="text" id="name" name="name" placeholder="Enter your name">
                
                <label for="email">Email:</label>
                <input type="email" id="email" name="email" placeholder="Enter your email">
                
                <label for="message">Message:</label>
                <textarea id="message" name="message" rows="4" placeholder="Enter your message"></textarea>
                
                <button type="submit">Submit</button>
                <button type="reset">Clear</button>
            </form>
        </body>
        </html>
        """
        
        await page.goto(f"data:text/html,{form_html}")
        await page.wait_for_timeout(1000)
        
        observations = await page.observe("Find all form inputs and buttons")
        print(f"\nFound {len(observations)} form elements:")
        
        for obs in observations:
            print(f"- {obs.description} ({obs.selector})")
        
        # Test 3: Page with scrollable content
        print("\n\n3. Testing scrollable elements...")
        scroll_html = """
        <html>
        <head><title>Scrollable Test</title></head>
        <body>
            <h1>Scrollable Elements Test</h1>
            <div style="height: 200px; overflow-y: scroll; border: 1px solid #ccc; padding: 10px;">
                <h2>Scrollable Section 1</h2>
                <p>Line 1</p><p>Line 2</p><p>Line 3</p><p>Line 4</p><p>Line 5</p>
                <p>Line 6</p><p>Line 7</p><p>Line 8</p><p>Line 9</p><p>Line 10</p>
            </div>
            
            <div style="width: 300px; overflow-x: auto; border: 1px solid #ccc; margin-top: 20px;">
                <div style="width: 600px; padding: 10px;">
                    <h2>Wide content that requires horizontal scrolling</h2>
                </div>
            </div>
        </body>
        </html>
        """
        
        await page.goto(f"data:text/html,{scroll_html}")
        await page.wait_for_timeout(1000)
        
        observations = await page.observe("Find all scrollable divs")
        print(f"\nFound {len(observations)} elements (checking for scrollable):")
        
        scrollable_count = 0
        for obs in observations:
            if "scrollable" in obs.description.lower():
                scrollable_count += 1
                print(f"- SCROLLABLE: {obs.description}")
        
        print(f"\nTotal scrollable elements found: {scrollable_count}")
        
        # Test 4: Iframe support
        print("\n\n4. Testing iframe support...")
        iframe_html = """
        <html>
        <body>
            <h1>Main Page</h1>
            <p>This is the main frame content.</p>
            <iframe src="data:text/html,<html><body><h2>Iframe Title</h2><button>Click me in iframe</button></body></html>" 
                    width="400" height="200" style="border: 2px solid blue;"></iframe>
        </body>
        </html>
        """
        
        await page.goto(f"data:text/html,{iframe_html}")
        await page.wait_for_timeout(1500)  # Give iframe time to load
        
        # First without iframe support
        observations_no_iframe = await page.observe("Find all buttons")
        print(f"\nWithout iframe support: {len(observations_no_iframe)} buttons found")
        
        # Then with iframe support
        observations_with_iframe = await page.observe(
            ObserveOptions(
                instruction="Find all buttons",
                iframes=True
            )
        )
        print(f"With iframe support: {len(observations_with_iframe)} buttons found")
        
        for obs in observations_with_iframe:
            if "button" in obs.description.lower():
                print(f"- Button: {obs.description} ({obs.selector})")
        
        # Test 5: Real website
        print("\n\n5. Testing on Wikipedia...")
        await page.goto("https://www.wikipedia.org")
        await page.wait_for_timeout(2000)
        
        observations = await page.observe("Find the main search input field and search button")
        print(f"\nFound {len(observations)} search-related elements:")
        
        for obs in observations:
            print(f"\n- Element:")
            print(f"  Description: {obs.description}")
            print(f"  Selector: {obs.selector}")
            if hasattr(obs, 'method') and obs.method:
                print(f"  Method: {obs.method}")
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_with_real_llm())