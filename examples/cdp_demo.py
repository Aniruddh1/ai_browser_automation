"""
Demonstration of CDP and XPath functionality in PlaywrightAI.

This example shows:
1. How CDP builds accessibility trees
2. How XPath mappings are created
3. How elements are identified and clicked
"""

from playwright_ai import PlaywrightAI
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def demonstrate_cdp():
    """Demonstrate CDP and XPath functionality."""
    print("=== CDP and XPath Demonstration ===\n")
    
    # Initialize with verbose logging to see CDP in action
    async with PlaywrightAI(
        headless=False,
        verbose=2,  # Verbose logging shows CDP details
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as browser:
        page = await browser.page()
        
        # Navigate to a simple page
        print("1. Navigating to example.com...")
        await page.goto("https://example.com")
        await page.wait_for_load_state("domcontentloaded")
        
        # Demonstrate observation with CDP
        print("\n2. Observing page elements using CDP...")
        print("   CDP will:")
        print("   - Connect to Chrome DevTools Protocol")
        print("   - Get accessibility tree")
        print("   - Build XPath mappings")
        print("   - Return precise selectors\n")
        
        results = await page.observe("Find all links and the main heading")
        
        print(f"\n3. Found {len(results)} elements:")
        for i, result in enumerate(results, 1):
            print(f"\n   Element {i}:")
            print(f"   - Description: {result.description}")
            print(f"   - Selector: {result.selector}")
            print(f"   - Encoded ID: {result.encoded_id}")
            if result.attributes:
                print(f"   - Role: {result.attributes.get('role', 'N/A')}")
                print(f"   - Name: {result.attributes.get('name', 'N/A')}")
        
        # Demonstrate action with CDP
        print("\n4. Performing action using CDP-generated XPath...")
        action_result = await page.act("Click the 'More information' link")
        
        if action_result.success:
            print(f"\n   [OK] Successfully clicked!")
            print(f"   - Action: {action_result.action}")
            print(f"   - Selector used: {action_result.selector}")
            print(f"   - New URL: {page.url}")
        else:
            print(f"\n   [FAIL] Action failed: {action_result.error}")
        
        # Show CDP internals (if you want to see raw data)
        print("\n5. CDP Internals (for debugging):")
        
        # Get accessibility tree directly
        from playwright_ai.a11y import get_accessibility_tree
        
        try:
            nodes, xpath_map, url_map = await get_accessibility_tree(page)
            print(f"   - Total accessibility nodes: {len(nodes)}")
            print(f"   - Total XPath mappings: {len(xpath_map)}")
            print(f"   - Frame URLs: {url_map}")
            
            # Show sample XPath mappings
            print("\n   Sample XPath mappings:")
            for encoded_id, xpath in list(xpath_map.items())[:3]:
                print(f"   - {encoded_id} → {xpath}")
                
        except Exception as e:
            print(f"   - Error accessing CDP: {e}")


async def demonstrate_cdp_vs_traditional():
    """Show difference between CDP and traditional approaches."""
    print("\n\n=== CDP vs Traditional Approach ===\n")
    
    print("Traditional CSS/XPath approach:")
    print("- Selector: 'a:contains(\"More information\")'")
    print("- Problem: Not valid XPath, might miss dynamic content")
    print("- Relies on: Visible text, CSS classes\n")
    
    print("CDP approach:")
    print("- Selector: 'xpath=/html[1]/body[1]/div[1]/p[2]/a[1]'")
    print("- Benefits: Precise, works with dynamic content")
    print("- Based on: Actual DOM structure + accessibility info")


async def main():
    """Run all demonstrations."""
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: Please set OPENAI_API_KEY environment variable")
        return
    
    # Run demonstrations
    await demonstrate_cdp()
    await demonstrate_cdp_vs_traditional()
    
    print("\n\n=== Demo Complete ===")
    print("CDP provides more reliable element identification!")


if __name__ == "__main__":
    asyncio.run(main())