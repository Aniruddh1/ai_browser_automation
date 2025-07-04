"""Test to verify XPath generation and text node handling."""

from ai_browser_automation import AIBrowserAutomation
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
load_dotenv()


async def test_xpath_generation():
    """Test that XPaths are generated correctly and text nodes are handled properly."""

    # Create test HTML with text nodes
    test_html = """
    <!DOCTYPE html>
    <html>
    <head><title>XPath Test</title></head>
    <body>
        <div id="container">
            <p id="paragraph1">This is some text content</p>
            <p onclick="alert('Clicked paragraph!')" style="cursor: pointer; color: blue; text-decoration: underline;">Click this paragraph</p>
            <div>
                <span>Nested text</span>
                <button>Click me</button>
            </div>
            <form>
                <input type="text" name="username" placeholder="Username">
                <div>
                    <p>Form paragraph with <strong>bold text</strong></p>
                </div>
            </form>
        </div>
    </body>
    </html>
    """

    print("Testing XPath generation and text node handling...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=2,
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as browser:
        page = await browser.page()

        # Set the HTML content
        await page.goto(f"data:text/html,{test_html}")
        await page.wait_for_timeout(500)

        # Get the page's internal AIBrowserAutomationPage object
        ai_page = page

        # Get the accessibility tree info
        from ai_browser_automation.a11y.utils import AccessibilityTreeBuilder

        async with AccessibilityTreeBuilder(ai_page) as builder:
            tag_name_map, xpath_map = await builder._build_backend_id_maps()

            print("=== XPath Map ===")
            print("BackendID -> XPath mappings:")

            # Sort by XPath for easier reading
            sorted_mappings = sorted(xpath_map.items(), key=lambda x: x[1])
            for backend_id, xpath in sorted_mappings:
                tag_name = tag_name_map.get(backend_id, "unknown")
                print(f"  {backend_id}: {xpath} (tag: {tag_name})")

            print("\n=== Checking for text() nodes ===")
            text_node_count = 0
            element_node_count = 0

            for xpath in xpath_map.values():
                if "/text()[" in xpath:
                    text_node_count += 1
                    print(f"  Text node XPath: {xpath}")
                else:
                    element_node_count += 1

            print(f"\nTotal element nodes: {element_node_count}")
            print(f"Total text nodes: {text_node_count}")

            # Get the accessibility tree
            tree, xpath_map_2, url_map = await builder.get_accessibility_tree_with_frames()

            print("\n=== Simplified Tree (what LLM sees) ===")
            print(f"Total elements in simplified tree: {len(tree)}")

            # Check if any text nodes made it to the simplified tree
            text_nodes_in_tree = 0
            for node in tree:
                node_id = node.get('nodeId')
                xpath = xpath_map.get(node_id, '')
                if "/text()[" in xpath:
                    text_nodes_in_tree += 1
                    print(f"  WARNING: Text node in tree: {node}")

            if text_nodes_in_tree == 0:
                print("  ✓ No text nodes in simplified tree (correct)")
            else:
                print(
                    f"  ✗ Found {text_nodes_in_tree} text nodes in simplified tree (incorrect)")

            # Test specific XPaths
            print("\n=== Testing Specific Elements ===")

            # Check body element
            body_xpath = None
            for backend_id, tag in tag_name_map.items():
                if tag == 'body':
                    body_xpath = xpath_map.get(backend_id)
                    break

            if body_xpath:
                print(f"Body XPath: {body_xpath}")
                if body_xpath == "/html[1]/body[0]":
                    print("  ✓ Body XPath matches TypeScript pattern")
                else:
                    print(f"  ✗ Body XPath doesn't match expected pattern")
                    print(f"    Expected: /html[1]/body[0]")
                    print(f"    Got:      {body_xpath}")

            # Find form paragraph
            form_p_xpaths = []
            for backend_id, tag in tag_name_map.items():
                if tag == 'p':
                    xpath = xpath_map.get(backend_id)
                    if xpath and "/form[" in xpath and "/text()[" not in xpath:
                        form_p_xpaths.append((backend_id, xpath))

            if form_p_xpaths:
                for backend_id, xpath in form_p_xpaths:
                    print(f"\nForm paragraph XPath: {xpath}")

                    # Check expected pattern
                    if xpath == "/html[1]/body[0]/div[1]/form[1]/div[1]/p[1]":
                        print("  ✓ Form paragraph XPath matches TypeScript pattern")
                    else:
                        print(
                            f"  ✗ Form paragraph XPath doesn't match expected pattern")
                        print(
                            f"    Expected: /html[1]/body[0]/div[1]/form[1]/div[1]/p[1]")
                        print(f"    Got:      {xpath}")

        # Test observe functionality
        print("\n=== Testing Observe Functionality ===")

        # Run observe
        try:
            observe_results = await page.observe("Find all clickable elements")

            print(f"Observe returned {len(observe_results)} results")

            has_text_node_selector = False
            for result in observe_results:
                print(f"\n  Selector: {result.selector}")
                print(f"  Description: {result.description}")

                # Check if any selector contains text()
                if "/text()[" in result.selector:
                    print("  ✗ WARNING: Selector contains text() node!")
                    has_text_node_selector = True
                else:
                    print("  ✓ Selector is for element node")

            if not has_text_node_selector:
                print("\n✓ No text node selectors returned by observe (correct)")
            else:
                print("\n✗ Found text node selectors in observe results (incorrect)")

        except Exception as e:
            print(f"Error during observe: {e}")
        
        # Test click functionality on text inside elements
        print("\n=== Testing Click Functionality on Text ===")
        
        # Test 1: Click on text inside the clickable paragraph
        print("\n1. Testing click on 'Click this paragraph' text:")
        try:
            click_result = await page.act("Click on the text 'Click this paragraph'")
            
            print(f"Click result: {click_result.success}")
            print(f"Selector: {click_result.selector}")
            
            # Check if the selector contains text()
            if click_result.selector and "/text()[" in click_result.selector:
                print("✗ ERROR: Click selector contains text() node - this won't work!")
            elif click_result.selector:
                print("✓ Click selector is for element node (correct)")
                # Check if it's the paragraph element
                if "/p[" in click_result.selector:
                    print("✓ Correctly selected the paragraph element containing the text")
                else:
                    print("⚠ Selected element but not the expected paragraph")
            else:
                print("✗ No selector returned")
                
        except Exception as e:
            print(f"Error during clickable paragraph test: {e}")
        
        # Test 2: Click on text inside the first paragraph
        print("\n2. Testing click on 'This is some text content':")
        try:
            click_result = await page.act("Click on 'This is some text content'")
            
            print(f"Click result: {click_result.success}")
            print(f"Selector: {click_result.selector}")
            
            # Check if the selector contains text()
            if click_result.selector and "/text()[" in click_result.selector:
                print("✗ ERROR: Click selector contains text() node - this won't work!")
            elif click_result.selector:
                print("✓ Click selector is for element node (correct)")
                # Check if it's the paragraph element
                if "/p[" in click_result.selector and "paragraph1" in (click_result.description or ""):
                    print("✓ Correctly selected the paragraph element containing the text")
                else:
                    print(f"Selected: {click_result.selector}")
            else:
                print("✗ No selector returned")
                
        except Exception as e:
            print(f"Error during text click test: {e}")


async def main():
    """Run the test."""
    await test_xpath_generation()
    print("\n[OK] XPath test completed!")


if __name__ == "__main__":
    asyncio.run(main())
