"""Test CDP XPath with debugging output."""

from ai_browser_automation import AIBrowserAutomation
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_cdp_xpath_debug():
    """Test CDP XPath with detailed debugging."""
    print("Testing CDP XPath with Debug Output...\n")
    
    async with AIBrowserAutomation(
        headless=False,
        verbose=1,  # Less verbose
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        # Test on example.com
        await page.goto("https://example.com")
        await page.wait_for_load_state("domcontentloaded")
        
        # Get accessibility tree to see what we have
        from ai_browser_automation.a11y import get_accessibility_tree
        
        print("1. Getting accessibility tree:")
        simplified_tree, xpath_map, url_map = await get_accessibility_tree(page)
        
        # Find the link node
        link_nodes = []
        for node in simplified_tree:
            if node.get('role') == 'link' or node.get('tagName') == 'a':
                link_nodes.append(node)
                
        print(f"\nFound {len(link_nodes)} link nodes:")
        for node in link_nodes:
            print(f"  - encodedId: {node.get('encodedId')}, name: {node.get('name')}")
            if node.get('encodedId') in xpath_map:
                print(f"    XPath: {xpath_map[node.get('encodedId')]}")
        
        # Now observe
        print("\n2. Observing page:")
        observe_results = await page.observe("Find the 'More information' link")
        
        if observe_results:
            for i, result in enumerate(observe_results):
                print(f"\nObserve Result {i+1}:")
                print(f"  Selector: {result.selector}")
                print(f"  Encoded ID: {result.encoded_id}")
                print(f"  Method: {result.method}")
                print(f"  Arguments: {result.arguments}")
                
                # Check if this encoded ID has an XPath
                if result.encoded_id in xpath_map:
                    print(f"  XPath in map: {xpath_map[result.encoded_id]}")
                else:
                    print(f"  No XPath found for encoded ID: {result.encoded_id}")


async def main():
    """Run the test."""
    if not os.getenv("OPENAI_API_KEY"):
        print("No OpenAI API key found. Set OPENAI_API_KEY environment variable.")
        return
    
    await test_cdp_xpath_debug()
    print("\n✓ CDP XPath debug completed!")


if __name__ == "__main__":
    asyncio.run(main())