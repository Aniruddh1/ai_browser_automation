"""Test direct XPath functionality."""

from playwright.async_api import async_playwright
import asyncio


async def test_direct_xpath():
    """Test XPath selectors directly with Playwright."""
    print("Testing Direct XPath...\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Navigate to example.com
        await page.goto("https://example.com")
        await page.wait_for_load_state("domcontentloaded")
        
        # Test different XPath selectors
        print("1. Testing XPath with full path:")
        xpath1 = "/html/body/div/p[2]/a"
        try:
            element1 = await page.wait_for_selector(f"xpath={xpath1}", timeout=5000)
            print(f"✓ Found element with XPath: {xpath1}")
            text = await element1.text_content()
            print(f"  Text: {text}")
        except Exception as e:
            print(f"✗ Failed to find element: {e}")
        
        print("\n2. Testing XPath with href attribute:")
        xpath2 = "//a[@href='https://www.iana.org/domains/example']"
        try:
            element2 = await page.wait_for_selector(f"xpath={xpath2}", timeout=5000)
            print(f"✓ Found element with XPath: {xpath2}")
            text = await element2.text_content()
            print(f"  Text: {text}")
        except Exception as e:
            print(f"✗ Failed to find element: {e}")
        
        print("\n3. Testing XPath with text content:")
        xpath3 = "//a[contains(text(), 'More information')]"
        try:
            element3 = await page.wait_for_selector(f"xpath={xpath3}", timeout=5000)
            print(f"✓ Found element with XPath: {xpath3}")
            
            # Try to click it
            await element3.click()
            print("✓ Click succeeded!")
            await page.wait_for_timeout(2000)
            print(f"  New URL: {page.url}")
        except Exception as e:
            print(f"✗ Failed: {e}")
        
        await browser.close()


async def main():
    """Run the test."""
    await test_direct_xpath()
    print("\n✓ Direct XPath test completed!")


if __name__ == "__main__":
    asyncio.run(main())