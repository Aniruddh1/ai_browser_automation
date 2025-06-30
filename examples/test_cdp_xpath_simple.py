"""Test CDP XPath generation in detail."""

from ai_browser_automation import AIBrowserAutomation
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_cdp_xpath_simple():
    """Test CDP XPath generation step by step."""
    print("Testing CDP XPath Generation...\n")
    
    async with AIBrowserAutomation(
        headless=False,
        verbose=2,
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        # Test on example.com
        print("Testing on example.com:")
        print("-" * 50)
        
        await page.goto("https://example.com")
        await page.wait_for_load_state("domcontentloaded")
        
        # Get accessibility tree directly
        print("\n1. Getting accessibility tree directly:")
        from ai_browser_automation.a11y import get_accessibility_tree
        
        try:
            simplified_tree, xpath_map, url_map = await get_accessibility_tree(page)
            
            print(f"\nGot {len(simplified_tree)} nodes")
            print(f"Got {len(xpath_map)} XPath mappings")
            print(f"URL map: {url_map}")
            
            # Print first few nodes
            print("\nFirst 5 nodes:")
            for i, node in enumerate(simplified_tree[:5]):
                print(f"  Node {i}: {node}")
            
            # Print first few XPath mappings
            print("\nFirst 5 XPath mappings:")
            for i, (encoded_id, xpath) in enumerate(list(xpath_map.items())[:5]):
                print(f"  {encoded_id}: {xpath}")
                
        except Exception as e:
            print(f"Error getting accessibility tree: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Run the test."""
    if not os.getenv("OPENAI_API_KEY"):
        print("No OpenAI API key found. Set OPENAI_API_KEY environment variable.")
        return
    
    await test_cdp_xpath_simple()
    print("\n✓ CDP XPath test completed!")


if __name__ == "__main__":
    asyncio.run(main())