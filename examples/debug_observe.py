"""Debug observe results."""

from playwright_ai import PlaywrightAI
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def debug_observe():
    """Debug what observe returns."""
    print("Debugging Observe Results...\n")
    
    async with PlaywrightAI(
        headless=False,
        verbose=0,  # Less verbose for cleaner output
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as browser:
        page = await browser.page()
        
        await page.goto("https://example.com")
        await page.wait_for_load_state("domcontentloaded")
        
        # Observe with return_action=True and from_act=True to simulate act behavior
        print("1. Observing for 'More information' link (act mode):")
        print("-" * 50)
        
        observe_results = await page.observe(
            instruction="Click the 'More information' link",
            return_action=True,
            from_act=True
        )
        
        if observe_results:
            for i, result in enumerate(observe_results):
                print(f"\nResult {i+1}:")
                print(f"  Selector: {result.selector}")
                print(f"  Method: {result.method}")
                print(f"  Arguments: {result.arguments}")
                print(f"  Description: {result.description}")
                print(f"  Action: {result.action}")
        else:
            print("No results found")
        
        # Also test with a regular observe
        print("\n\n2. Regular observe:")
        print("-" * 50)
        
        regular_results = await page.observe("Find the 'More information' link")
        
        if regular_results:
            for i, result in enumerate(regular_results):
                print(f"\nResult {i+1}:")
                print(f"  Selector: {result.selector}")
                print(f"  Description: {result.description}")
        else:
            print("No results found")


async def main():
    """Run the debug."""
    if not os.getenv("OPENAI_API_KEY"):
        print("No OpenAI API key found. Set OPENAI_API_KEY environment variable.")
        return
    
    await debug_observe()
    print("\n[OK] Debug completed!")


if __name__ == "__main__":
    asyncio.run(main())