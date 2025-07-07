#!/usr/bin/env python3
"""
Test script to verify CDP and DOM alignment with TypeScript implementation.
"""

import asyncio
import os
from playwright_ai import PlaywrightAI
from playwright_ai.a11y.utils_v2 import (
    get_accessibility_tree,
    build_backend_id_maps,
)


async def test_cdp_session_management():
    """Test CDP session management features."""
    print("\n=== Testing CDP Session Management ===")
    
    browser = PlaywrightAI(
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")},
        headless=False,
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        # Navigate to a test page
        await page.goto("https://example.com")
        await page._wait_for_settled_dom()
        
        print("✓ Page loaded and DOM settled")
        
        # Test CDP session creation
        cdp_client = await page.get_cdp_client()
        print(f"✓ CDP client created: {type(cdp_client)}")
        
        # Test CDP commands
        version_info = await page.send_cdp("Browser.getVersion")
        print(f"✓ Browser version: {version_info.get('product', 'Unknown')}")
        
        # Test enabling/disabling domains
        await page.enable_cdp("Network")
        print("✓ Network domain enabled")
        
        await page.disable_cdp("Network")
        print("✓ Network domain disabled")
        
        # Test frame ordinal functions
        ordinal = page.ordinal_for_frame_id(None)
        print(f"✓ Main frame ordinal: {ordinal}")
        
        encoded = page.encode_with_frame_id(None, 123)
        print(f"✓ Encoded ID: {encoded}")
        
        page.reset_frame_ordinals()
        print("✓ Frame ordinals reset")
        
    finally:
        await browser.close()


async def test_dom_scripts():
    """Test DOM script injection and XPath generation."""
    print("\n=== Testing DOM Scripts ===")
    
    browser = PlaywrightAI(
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")},
        headless=False,
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        
        # Navigate to a test page
        await page.goto("https://example.com")
        await page._wait_for_settled_dom()
        
        # Inject DOM scripts
        from playwright_ai.dom.scripts import DOM_SCRIPTS
        await page.evaluate(DOM_SCRIPTS)
        print("✓ DOM scripts injected")
        
        # Test XPath generation
        result = await page.evaluate("""
            (async () => {
                const h1 = document.querySelector('h1');
                if (!h1) return null;
                
                // Test basic XPath
                const xpath = window.generateXPath(h1);
                
                // Test XPath generation with strategies
                const xpaths = await window.generateXPathsForElement(h1);
                
                // Test scrollable elements
                const scrollables = await window.getScrollableElementXpaths(5);
                
                return {
                    basicXPath: xpath,
                    xpathStrategies: xpaths,
                    scrollableCount: scrollables.length
                };
            })()
        """)
        
        if result:
            print(f"✓ Basic XPath: {result['basicXPath']}")
            print(f"✓ XPath strategies: {len(result['xpathStrategies'])} found")
            print(f"✓ Scrollable elements: {result['scrollableCount']} found")
        else:
            print("✗ No h1 element found for testing")
            
    finally:
        await browser.close()


async def test_accessibility_tree():
    """Test accessibility tree building."""
    print("\n=== Testing Accessibility Tree ===")
    
    browser = PlaywrightAI(
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")},
        headless=False,
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        # Navigate to a test page
        await page.goto("https://example.com")
        await page._wait_for_settled_dom()
        
        # Build backend ID maps
        print("Building backend ID maps...")
        backend_maps = await build_backend_id_maps(page)
        print(f"✓ Tag name map entries: {len(backend_maps['tagNameMap'])}")
        print(f"✓ XPath map entries: {len(backend_maps['xpathMap'])}")
        
        # Get accessibility tree
        print("Getting accessibility tree...")
        tree_result = await get_accessibility_tree(page)
        print(f"✓ Tree nodes: {len(tree_result['tree'])}")
        print(f"✓ Iframes found: {len(tree_result['iframes'])}")
        print(f"✓ URL mappings: {len(tree_result['idToUrl'])}")
        
        # Print simplified tree (first few lines)
        simplified_lines = tree_result['simplified'].split('\n')[:5]
        print("\nSimplified tree preview:")
        for line in simplified_lines:
            print(f"  {line}")
            
    except Exception as e:
        print(f"✗ Error building accessibility tree: {e}")
            
    finally:
        await browser.close()


async def test_observe_method():
    """Test the observe method with new implementation."""
    print("\n=== Testing Observe Method ===")
    
    browser = PlaywrightAI(
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")},
        headless=False,
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        # Navigate to a test page
        await page.goto("https://example.com")
        await page._wait_for_settled_dom()
        
        # Test observe with no arguments
        print("Testing observe() with no arguments...")
        results = await page.observe()
        print(f"✓ Found {len(results)} elements")
        
        # Show first few results
        for i, result in enumerate(results[:3]):
            print(f"  [{i}] {result.selector} - {result.description}")
        
        # Test observe with string instruction
        print("\nTesting observe with instruction...")
        results = await page.observe("Find all links")
        print(f"✓ Found {len(results)} link elements")
        
    except Exception as e:
        print(f"✗ Error in observe method: {e}")
        import traceback
        traceback.print_exc()
            
    finally:
        await browser.close()


async def main():
    """Run all tests."""
    print("Starting CDP and DOM alignment tests...")
    
    try:
        await test_cdp_session_management()
        await test_dom_scripts()
        await test_accessibility_tree()
        await test_observe_method()
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())