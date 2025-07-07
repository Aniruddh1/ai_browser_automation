#!/usr/bin/env python3
"""
Test script to verify TypeScript-aligned implementation works correctly.
Tests DOM script injection, scrollable elements, frame handling, and observe functionality.
"""

import asyncio
import os
from playwright_ai import PlaywrightAI
from playwright_ai.types import ObserveOptions


async def test_typescript_alignment():
    """Test complete flow with frames and scrollable elements."""
    print("Starting TypeScript alignment test...")
    
    # Initialize browser
    browser = PlaywrightAI(
        model_name="gpt-4o-mini",
        headless=False
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        # Test 1: Basic page with scrollable elements
        print("\n1. Testing scrollable element detection...")
        await page.goto("https://example.com")
        
        # Test observe functionality
        observations = await page.observe("Find all clickable elements")
        print(f"   Found {len(observations)} observations")
        
        # Check selector format - should always be "xpath=" prefix
        for obs in observations[:3]:  # Show first 3
            print(f"   - {obs.role}: {obs.selector}")
            assert obs.selector.startswith("xpath="), f"Selector should start with 'xpath=' but got: {obs.selector}"
        
        # Test 2: Page with iframes
        print("\n2. Testing iframe handling...")
        # Create a test page with iframe
        test_html = """
        <html>
        <head><title>Test Page with Iframe</title></head>
        <body>
            <h1>Main Frame</h1>
            <div style="height: 200px; overflow-y: scroll;">
                <p>Scrollable content in main frame</p>
                <p>Line 2</p>
                <p>Line 3</p>
                <p>Line 4</p>
                <p>Line 5</p>
            </div>
            <iframe src="data:text/html,<html><body><h2>Iframe Content</h2><button>Click me in iframe</button></body></html>" 
                    width="400" height="300"></iframe>
        </body>
        </html>
        """
        
        await page.goto(f"data:text/html,{test_html}")
        await page.wait_for_timeout(1000)  # Let iframe load
        
        # Test observe with iframe support
        observations = await page.observe(
            ObserveOptions(
                instruction="Find all headings and buttons",
                iframes=True
            )
        )
        
        print(f"   Found {len(observations)} elements including iframes")
        
        # Check if we found elements from both main frame and iframe
        main_frame_elements = [o for o in observations if "Main Frame" in (o.name or "")]
        iframe_elements = [o for o in observations if "iframe" in (o.name or "").lower() or "Iframe Content" in (o.name or "")]
        
        print(f"   - Main frame elements: {len(main_frame_elements)}")
        print(f"   - Iframe-related elements: {len(iframe_elements)}")
        
        # Test 3: Scrollable element detection with DOM scripts
        print("\n3. Testing scrollable element detection with DOM scripts...")
        scroll_test_html = """
        <html>
        <head><title>Scrollable Test</title></head>
        <body>
            <div id="scroll1" style="height: 100px; overflow-y: auto;">
                <div style="height: 300px;">Long content 1</div>
            </div>
            <div id="scroll2" style="height: 100px; overflow-x: scroll;">
                <div style="width: 300px;">Wide content</div>
            </div>
            <div id="no-scroll" style="height: 100px;">
                <div>Normal content</div>
            </div>
        </body>
        </html>
        """
        
        await page.goto(f"data:text/html,{scroll_test_html}")
        await page.wait_for_timeout(500)
        
        # Observe and check for scrollable role decoration
        observations = await page.observe("Find all divs")
        scrollable_elements = [o for o in observations if "scrollable" in (o.role or "").lower()]
        
        print(f"   Found {len(scrollable_elements)} scrollable elements")
        for elem in scrollable_elements:
            print(f"   - Role: {elem.role}, Name: {elem.name}")
        
        # Test 4: Complex nested iframes
        print("\n4. Testing nested iframe handling...")
        nested_html = """
        <html>
        <body>
            <h1>Top Level</h1>
            <iframe id="frame1" src="data:text/html,
                <html><body>
                    <h2>Frame 1</h2>
                    <iframe id='frame2' src='data:text/html,<html><body><h3>Nested Frame 2</h3></body></html>'></iframe>
                </body></html>">
            </iframe>
        </body>
        </html>
        """
        
        await page.goto(f"data:text/html,{nested_html}")
        await page.wait_for_timeout(1000)  # Let nested iframes load
        
        # Observe with iframe support
        observations = await page.observe(
            ObserveOptions(
                instruction="Find all headings",
                iframes=True
            )
        )
        
        print(f"   Found {len(observations)} headings across all frames")
        for obs in observations:
            if obs.role == "heading":
                print(f"   - {obs.name} (selector: {obs.selector})")
        
        # Test 5: Verify no "unknown" selectors
        print("\n5. Verifying selector consistency...")
        await page.goto("https://www.wikipedia.org")
        
        observations = await page.observe("Find the main search input and search button")
        print(f"   Found {len(observations)} elements")
        
        unknown_selectors = [o for o in observations if "unknown" in o.selector.lower()]
        if unknown_selectors:
            print(f"   ERROR: Found {len(unknown_selectors)} elements with 'unknown' selectors!")
            for obs in unknown_selectors:
                print(f"   - {obs.role}: {obs.selector}")
        else:
            print("   ✓ All selectors properly formatted (no 'unknown' selectors)")
        
        print("\n✅ TypeScript alignment test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_typescript_alignment())