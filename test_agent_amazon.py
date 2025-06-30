"""Test multi-step agent with complex Amazon shopping task."""

import asyncio
from ai_browser_automation import AIBrowserAutomation


async def main():
    """Test agent with complex multi-step task."""
    print("\n=== Testing Multi-Step Agent with Complex Task ===\n")

    # Initialize AIBrowserAutomation
    browser_automation = AIBrowserAutomation(
        env="LOCAL",
        verbose=1,  # Moderate logging
        headless=False,  # Show browser for demo
    )

    await browser_automation.init()

    # Create a page
    page = await browser_automation.page()

    # # Start at Amazon
    # print("Navigating to Amazon...")
    # await page.goto("https://www.amazon.com")

    # Create agent
    agent = page.agent(
        model_name="gpt-4o",  # Will use demo client
        client_options={
            "wait_between_actions": 1000  # 1 second between actions for visibility
        }
    )

    result2 = await agent.execute(
        "Go to google, search for playwright, and click on the first result"
    )

    print(f"\nResult:")
    print(f"  Success: {result2.success}")
    print(f"  Completed: {result2.completed}")
    print(f"  Total Actions: {len(result2.actions)}")

    # Wait a bit to see the result
    await asyncio.sleep(5)

    await browser_automation.close()
    print("\n=== Test Complete ===\n")


if __name__ == "__main__":
    asyncio.run(main())
