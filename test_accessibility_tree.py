#!/usr/bin/env python3
"""Test accessibility tree extraction directly."""

import asyncio
from playwright_ai import PlaywrightAI
from playwright_ai.a11y import get_accessibility_tree


async def test_accessibility_tree():
    """Test accessibility tree extraction."""
    print("Testing accessibility tree extraction...")
    
    # Initialize browser
    browser = PlaywrightAI(
        headless=False,
        verbose=2
    )
    
    await browser.init()
    page = await browser.page()
    
    try:
        # Navigate to a simple page
        print("\n1. Loading example.com...")
        await page.goto("https://example.com")
        await page.wait_for_timeout(2000)
        
        # Get accessibility tree directly
        print("\n2. Getting accessibility tree...")
        try:
            tree_result = await get_accessibility_tree(page)
            tree = tree_result["tree"]
            xpath_map = tree_result.get("xpathMap", {})
            url_map = tree_result.get("idToUrl", {})
            
            print(f"\nTree has {len(tree)} nodes")
            print(f"XPath map has {len(xpath_map)} entries")
            print(f"URL map: {url_map}")
            
            # Print first few nodes
            print("\nFirst few tree nodes:")
            for i, node in enumerate(tree[:5]):
                print(f"\nNode {i+1}:")
                print(f"  Role: {node.get('role')}")
                print(f"  Name: {node.get('name')}")
                print(f"  EncodedId: {node.get('encodedId')}")
                print(f"  NodeId: {node.get('nodeId')}")
                
            # Print a few XPath mappings
            print("\nSample XPath mappings:")
            for i, (encoded_id, xpath) in enumerate(list(xpath_map.items())[:3]):
                print(f"  {encoded_id} -> {xpath}")
                
        except Exception as e:
            print(f"Error getting accessibility tree: {e}")
            import traceback
            traceback.print_exc()
        
        # Test with a page that has iframes
        print("\n\n3. Testing with iframe page...")
        iframe_html = """
        <html>
        <body>
            <h1>Main Page</h1>
            <iframe src="data:text/html,<h2>Iframe Content</h2>"></iframe>
        </body>
        </html>
        """
        await page.goto(f"data:text/html,{iframe_html}")
        await page.wait_for_timeout(1000)
        
        tree_result = await get_accessibility_tree(page)
        tree = tree_result["tree"]
        xpath_map = tree_result.get("xpathMap", {})
        url_map = tree_result.get("idToUrl", {})
        print(f"\nWith iframe - Tree nodes: {len(tree)}, XPath entries: {len(xpath_map)}")
        print(f"URL map: {url_map}")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        print("\nTest completed.")


if __name__ == "__main__":
    asyncio.run(test_accessibility_tree())