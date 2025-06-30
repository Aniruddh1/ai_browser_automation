"""Debug CDP functionality."""

from playwright.async_api import async_playwright
import asyncio


async def test_cdp_debug():
    """Test CDP session directly."""
    print("Testing CDP Session...\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            await page.goto("https://example.com")
        except Exception as e:
            print(f"Navigation error (continuing): {e}")
        await page.wait_for_load_state("domcontentloaded")
        
        # Create CDP session
        print("Creating CDP session...")
        try:
            cdp_session = await context.new_cdp_session(page)
            print("✓ CDP session created successfully")
            
            # Test basic CDP commands
            print("\nTesting CDP commands:")
            
            # Enable Accessibility
            try:
                await cdp_session.send("Accessibility.enable")
                print("✓ Accessibility.enable succeeded")
            except Exception as e:
                print(f"✗ Accessibility.enable failed: {e}")
            
            # Enable DOM
            try:
                await cdp_session.send("DOM.enable")
                print("✓ DOM.enable succeeded")
            except Exception as e:
                print(f"✗ DOM.enable failed: {e}")
            
            # Get accessibility tree
            try:
                ax_tree = await cdp_session.send("Accessibility.getFullAXTree")
                nodes = ax_tree.get("nodes", [])
                print(f"✓ Got accessibility tree with {len(nodes)} nodes")
                
                # Print first few nodes
                for i, node in enumerate(nodes[:5]):
                    print(f"  Node {i}: role={node.get('role', {}).get('value', 'unknown')}, "
                          f"name={node.get('name', {}).get('value', '')[:30]}")
            except Exception as e:
                print(f"✗ Accessibility.getFullAXTree failed: {e}")
            
            # Cleanup
            await cdp_session.detach()
            print("\n✓ CDP session detached")
            
        except Exception as e:
            print(f"✗ Failed to create CDP session: {e}")
        
        await browser.close()


async def main():
    """Run the test."""
    await test_cdp_debug()
    print("\n✓ CDP debug completed!")


if __name__ == "__main__":
    asyncio.run(main())